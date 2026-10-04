#!/usr/bin/env python3
"""生成 ClashMi (mihomo) 用的鏈式配置：WARP MASQUE -> Opera 出口。

用法：
  python3 gen_clashmi.py <am_login> <am_password> <eu_login> <eu_password>

讀取同目錄下的 warp-config.json（由 warp_register.py 生成），
輸出 clashmi.yaml，可直接導入 ClashMi。
生成 ai-us-0~3（美洲）、ai-eu-0~3（歐洲）共 8 個節點。
"""
import json
import sys


# Opera 出口（由 opera-proxy -country AM/EU -list-proxies 獲得）
OPERA_AM = [
    ("am0.sec-tunnel.com", "77.111.246.33"),
    ("am1.sec-tunnel.com", "77.111.246.40"),
    ("am2.sec-tunnel.com", "77.111.246.126"),
    ("am3.sec-tunnel.com", "77.111.246.62"),
]
OPERA_EU = [
    ("eu0.sec-tunnel.com", "77.111.247.27"),
    ("eu1.sec-tunnel.com", "77.111.247.79"),
    ("eu2.sec-tunnel.com", "77.111.244.209"),
    ("eu3.sec-tunnel.com", "77.111.247.28"),
]


def load_warp_config():
    with open("warp-config.json") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)

    am_login, am_password, eu_login, eu_password = sys.argv[1:5]

    wc = load_warp_config()

    # warp-config.json 由 warp_register.py 生成
    # private-key: 用戶私鑰；public-key: Cloudflare 接入點公鑰（endpoint_pub_key 去 PEM 頭尾）
    priv = wc.get("private_key") or wc.get("privateKey") or wc.get("masque_private_key")
    endpoint_pub = wc.get("endpoint_pub_key") or wc.get("endpointPubKey")
    v4 = wc.get("ip") or wc.get("ipv4") or wc.get("warp_ip")
    v6 = wc.get("ipv6") or wc.get("warp_ipv6")

    missing = []
    if not priv:
        missing.append("private_key")
    if not endpoint_pub:
        missing.append("endpoint_pub_key")
    if not v4:
        missing.append("ipv4")
    if not v6:
        missing.append("ipv6")
    if missing:
        print(f"錯誤：warp-config.json 裡找不到：{', '.join(missing)}", file=sys.stderr)
        print("可用的鍵：", list(wc.keys()), file=sys.stderr)
        sys.exit(1)

    # 去掉 PEM 頭尾，只留 base64 DER
    pub = "".join(
        ln.strip() for ln in endpoint_pub.strip().splitlines()
        if ln.strip() and not ln.startswith("-----")
    )

    # MASQUE 節點：沿用 warp_register.py 的接入點
    masque_ip = "162.159.198.1"
    masque_port = 443

    # 生成 Opera 節點：美洲 ai-us-0~3，歐洲 ai-eu-0~3
    opera_nodes = []
    for i, (host, ip) in enumerate(OPERA_AM):
        opera_nodes.append(f"""  - name: ai-us-{i}
    type: http
    server: {ip}
    port: 443
    username: {am_login}
    password: {am_password}
    tls: true
    sni: {host}
    skip-cert-verify: false
    dialer-proxy: warp-masque""")
    for i, (host, ip) in enumerate(OPERA_EU):
        opera_nodes.append(f"""  - name: ai-eu-{i}
    type: http
    server: {ip}
    port: 443
    username: {eu_login}
    password: {eu_password}
    tls: true
    sni: {host}
    skip-cert-verify: false
    dialer-proxy: warp-masque""")

    opera_proxies = "\n".join(opera_nodes)
    us_names = "\n".join(f"      - ai-us-{i}" for i in range(len(OPERA_AM)))
    eu_names = "\n".join(f"      - ai-eu-{i}" for i in range(len(OPERA_EU)))
    opera_rules = "\n".join(
        f"  - DOMAIN-SUFFIX,{d},ai-us-0"
        for d in ["openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com"]
    )

    yaml_content = f"""# ClashMi 配置：WARP MASQUE -> Opera 美國出口 -> 目標
# 由 gen_clashmi.py 自動生成

proxies:
  - name: warp-masque
    type: masque
    server: {masque_ip}
    port: {masque_port}
    private-key: {priv}
    public-key: {pub}
    ip: {v4}
    ipv6: {v6}
    udp: true

{opera_proxies}

proxy-groups:
  - name: PROXY
    type: select
    proxies:
{us_names}
{eu_names}
      - warp-masque
      - DIRECT

rules:
{opera_rules}
  - MATCH,PROXY
"""

    with open("clashmi.yaml", "w") as f:
        f.write(yaml_content)

    print("已生成 clashmi.yaml")
    print(f"美國節點：ai-us-0 ~ ai-us-{len(OPERA_AM)-1}，歐洲節點：ai-eu-0 ~ ai-eu-{len(OPERA_EU)-1}")
    print("導入到 ClashMi，在 PROXY 組裡逐個試。")


if __name__ == "__main__":
    main()
