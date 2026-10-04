#!/usr/bin/env python3
"""
WARP MASQUE 註冊腳本（純 Python，無第三方 WARP 工具依賴）

原理：模仿官方 WARP Android 客戶端的註冊流程，直接調 Cloudflare API。
  1. POST /v0a4471/reg          註冊帳號（帶隨機 WireGuard 公鑰做掩護）
  2. PATCH /v0a4471/reg/{id}    登記 MASQUE (secp256r1) 公鑰，切換到 MASQUE 模式
  3. 生成 Shadowrocket masque:// 鏈接 和 mihomo 配置片段

依賴：pip install requests cryptography
用法：python3 warp_register.py [-n 設備名]
輸出：warp-config.json / warp-shadowrocket.txt / warp-mihomo.yaml
"""

import argparse
import base64
import json
import secrets
import sys
import urllib.parse
from datetime import datetime

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

API_URL = "https://api.cloudflareclient.com"
API_VERSION = "v0a4471"

HEADERS = {
    "User-Agent": "WARP for Android",
    "CF-Client-Version": "a-6.35-4471",
    "Content-Type": "application/json; charset=UTF-8",
}

# 精簡接入點：1 個最穩的 IP × 4 個官方 MASQUE 端口（避免高頻測試觸發風控）
V4 = ["162.159.198.1"]
PORTS = (443, 4443, 8443, 8095)


def cf_time():
    """Cloudflare 時間格式：2006-01-02T15:04:05.000-07:00"""
    s = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S.000%z")
    return s[:-2] + ":" + s[-2:]  # +0800 -> +08:00


def gen_masque_keypair():
    """生成 P-256 密鑰對。私鑰 SEC1 DER（mihomo 要的格式），公鑰 PKIX DER（API 要的格式）。"""
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_der = priv.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.TraditionalOpenSSL,  # SEC1
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_der = priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,  # PKIX
    )
    return base64.b64encode(priv_der).decode(), base64.b64encode(pub_der).decode()


def register(device_name="warp"):
    # 1. 生成掩護用的隨機 WireGuard 公鑰（私鑰直接丟掉，只為模仿官方 App）
    wg_pub = base64.b64encode(secrets.token_bytes(32)).decode()
    serial = secrets.token_hex(8)  # 16 位 hex

    # 2. 生成真正的 MASQUE 密鑰對
    masque_priv_b64, masque_pub_b64 = gen_masque_keypair()

    # 3. POST 註冊
    reg_body = {
        "key": wg_pub,
        "install_id": "",
        "fcm_token": "",
        "tos": cf_time(),
        "model": "PC",
        "serial_number": serial,
        "os_version": "",
        "key_type": "curve25519",
        "tunnel_type": "wireguard",
        "locale": "en_US",
    }
    r = requests.post(f"{API_URL}/{API_VERSION}/reg", headers=HEADERS, json=reg_body, timeout=30)
    if r.status_code != 200:
        sys.exit(f"註冊失敗 HTTP {r.status_code}: {r.text[:200]}")
    account = r.json()
    device_id = account["id"]
    token = account["token"]
    print(f"註冊成功，device id: {device_id[:8]}...")

    # 4. PATCH 登記 MASQUE 公鑰
    enroll_body = {
        "key": masque_pub_b64,
        "key_type": "secp256r1",
        "tunnel_type": "masque",
        "name": device_name,
    }
    h2 = dict(HEADERS)
    h2["Authorization"] = "Bearer " + token
    r = requests.patch(f"{API_URL}/{API_VERSION}/reg/{device_id}", headers=h2, json=enroll_body, timeout=30)
    if r.status_code != 200:
        sys.exit(f"登記 MASQUE 密鑰失敗 HTTP {r.status_code}: {r.text[:200]}")
    updated = r.json()
    print("MASQUE 密鑰登記成功")

    # 5. 組裝配置（兼容 byJoey gen_masque.py 的輸入格式）
    peer = updated["config"]["peers"][0]
    cfg = {
        "private_key": masque_priv_b64,
        "endpoint_pub_key": peer["public_key"],
        "ipv4": updated["config"]["interface"]["addresses"]["v4"],
        "ipv6": updated["config"]["interface"]["addresses"]["v6"],
        "endpoint_v4": peer["endpoint"]["v4"],
        "endpoint_v6": peer["endpoint"]["v6"],
        "device_id": device_id,
        # token 不存文件，用完即焚（如需管理設備再手動處理）
    }
    return cfg


def strip_pem(pem):
    """去掉 PEM 頭尾，只留 base64 DER。"""
    lines = [ln.strip() for ln in pem.strip().splitlines() if ln.strip() and not ln.startswith("-----")]
    return "".join(lines)


def gen_shadowrocket_links(cfg):
    """生成 Shadowrocket 用的 masque:// 鏈接。"""
    def enc(v):
        return urllib.parse.quote(str(v), safe="").replace("%2C", ",")

    pub = strip_pem(cfg["endpoint_pub_key"])

    lines = []
    for ip in V4:
        for port in PORTS:
            params = "&".join([
                "publicKey=" + enc(pub),
                "privateKey=" + enc(cfg["private_key"]),
                "ip=" + enc(cfg["ipv4"]),
                "dns=" + enc("1.1.1.1,8.8.8.8"),
                "udp=1",
                "cc=",
                "flag=" + enc("WARP"),
            ])
            name = f"WARP-{ip.split('.')[2]}.{ip.split('.')[3]}-{port}"
            lines.append(f"masque://{ip}:{port}?{params}#{enc(name)}")
    return lines


def gen_mihomo_yaml(cfg, links):
    """生成最小 mihomo 配置片段。"""
    pub = strip_pem(cfg["endpoint_pub_key"])
    proxies = []
    for ip in V4:
        for port in PORTS:
            name = f"WARP-{ip.split('.')[2]}.{ip.split('.')[3]}-{port}"
            proxies.append(
                f'  - name: "{name}"\n'
                f"    type: masque\n"
                f"    server: {ip}\n"
                f"    port: {port}\n"
                f"    private-key: {cfg['private_key']}\n"
                f"    public-key: {pub}\n"
                f"    ip: {cfg['ipv4']}\n"
                f"    ipv6: {cfg['ipv6']}\n"
                f"    udp: true"
            )
    names = [f'"WARP-{ip.split(".")[2]}.{ip.split(".")[3]}-{port}"' for ip in V4 for port in PORTS]
    return (
        "# WARP MASQUE (mihomo Alpha required)\n"
        "proxies:\n" + "\n".join(proxies) + "\n"
        "proxy-groups:\n"
        "  - name: WARP\n"
        "    type: url-test\n"
        "    url: http://www.gstatic.com/generate_204\n"
        "    interval: 300\n"
        "    proxies:\n" + "\n".join(f"      - {n}" for n in names) + "\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--name", default="warp", help="設備名")
    args = ap.parse_args()

    print("正在註冊 WARP 帳號...")
    cfg = register(args.name)

    with open("warp-config.json", "w") as f:
        json.dump(cfg, f, indent=2)
    print("已保存 warp-config.json（私鑰在內，勿外傳）")

    links = gen_shadowrocket_links(cfg)
    with open("warp-shadowrocket.txt", "w") as f:
        f.write("\n".join(links) + "\n")
    print(f"已生成 warp-shadowrocket.txt（{len(links)} 條 masque:// 鏈接）")

    yaml_text = gen_mihomo_yaml(cfg, links)
    with open("warp-mihomo.yaml", "w") as f:
        f.write(yaml_text)
    print("已生成 warp-mihomo.yaml（mihomo Alpha 專用）")

    print("\n完成。Shadowrocket 用戶：從 warp-shadowrocket.txt 複製一行 masque:// 鏈接導入即可。")


if __name__ == "__main__":
    main()
