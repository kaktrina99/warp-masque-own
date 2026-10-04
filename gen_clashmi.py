#!/usr/bin/env python3
"""生成 ClashMi (mihomo) 用的鏈式配置：WARP MASQUE -> Opera 美國出口。

用法：
  python3 gen_clashmi.py <opera_login> <opera_password> <opera_host> <opera_ip>

例如：
  python3 gen_clashmi.py 4177774B06E88381A0A3130AA3AEC12C6429A4F0 eyJhbGci... am0.sec-tunnel.com 77.111.246.33

讀取同目錄下的 warp-config.json（由 warp_register.py 生成），
輸出 clashmi.yaml，可直接導入 ClashMi。
"""
import json
import sys
import base64


def load_warp_config():
    with open("warp-config.json") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)

    opera_login, opera_password, opera_host, opera_ip = sys.argv[1:5]

    wc = load_warp_config()

    # warp-config.json 由 warp_register.py 生成
    # 兼容多種可能的鍵名
    priv = wc.get("private_key") or wc.get("privateKey") or wc.get("masque_private_key")
    pub = wc.get("public_key") or wc.get("publicKey") or wc.get("masque_public_key")
    v4 = wc.get("ip") or wc.get("ipv4") or wc.get("warp_ip")
    v6 = wc.get("ipv6") or wc.get("warp_ipv6")

    missing = []
    if not priv:
        missing.append("private_key")
    if not pub:
        missing.append("public_key")
    if not v4:
        missing.append("ip")
    if not v6:
        missing.append("ipv6")
    if missing:
        print(f"錯誤：warp-config.json 裡找不到：{', '.join(missing)}", file=sys.stderr)
        print("可用的鍵：", list(wc.keys()), file=sys.stderr)
        sys.exit(1)

    # MASQUE 節點：沿用 warp_register.py 的接入點
    masque_ip = "162.159.198.1"
    masque_port = 443

    yaml_content = f"""# ClashMi 配置：WARP MASQUE -> Opera 美國出口 -> 目標
# 由 gen_clashmi.py 自動生成
# 用法：導入 ClashMi，選擇 "ai-us" 節點

proxies:
  - name: warp-masque
    type: masque
    server: {masque_ip}
    port: {masque_port}
    private-key: {priv}
    public-key: {pub}
    ip: {v4}
    ipv6: {v6}
    mtu: 1280
    udp: true
    remote-dns-resolve: true
    dns: [1.1.1.1, 2606:4700:4700::1111]

  - name: ai-us
    type: http
    server: {opera_ip}
    port: 443
    username: {opera_login}
    password: {opera_password}
    tls: true
    sni: {opera_host}
    skip-cert-verify: false
    dialer-proxy: warp-masque

proxy-groups:
  - name: PROXY
    type: select
    proxies:
      - ai-us
      - warp-masque
      - DIRECT

rules:
  - DOMAIN-SUFFIX,openai.com,ai-us
  - DOMAIN-SUFFIX,chatgpt.com,ai-us
  - DOMAIN-SUFFIX,oaistatic.com,ai-us
  - DOMAIN-SUFFIX,oaiusercontent.com,ai-us
  - MATCH,PROXY
"""

    with open("clashmi.yaml", "w") as f:
        f.write(yaml_content)

    print("已生成 clashmi.yaml")
    print("導入到 ClashMi，選擇 'ai-us' 節點，ChatGPT 流量走美國出口，其他走 PROXY 規則。")


if __name__ == "__main__":
    main()
