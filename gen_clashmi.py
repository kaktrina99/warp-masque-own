#!/usr/bin/env python3
"""生成 ClashMi (mihomo) 用的鏈式配置：WARP MASQUE -> Opera 美國出口。

用法：
  python3 gen_clashmi.py <opera_login> <opera_password>

例如：
  python3 gen_clashmi.py 4177774B06E88381A0A3130AA3AEC12C6429A4F0 eyJhbGci...

讀取同目錄下的 warp-config.json（由 warp_register.py 生成），
輸出 clashmi.yaml，可直接導入 ClashMi。
內置 4 個 Opera 美洲出口，生成 ai-us-0 ~ ai-us-3 四個節點。
"""
import json
import sys


# Opera 美洲區出口（由 opera-proxy -country AM -list-proxies 獲得）
OPERA_SERVERS = [
    ("am0.sec-tunnel.com", "77.111.246.33"),
    ("am1.sec-tunnel.com", "77.111.246.40"),
    ("am2.sec-tunnel.com", "77.111.246.126"),
    ("am3.sec-tunnel.com", "77.111.246.62"),
]


def load_warp_config():
    with open("warp-config.json") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    opera_login, opera_password = sys.argv[1:3]

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

    # 生成 4 個 Opera 節點
    opera_nodes = []
    for i, (host, ip) in enumerate(OPERA_SERVERS):
        opera_nodes.append(f"""  - name: ai-us-{i}
    type: http
    server: {ip}
    port: 443
    username: {opera_login}
    password: {opera_password}
    tls: true
    sni: {host}
    skip-cert-verify: false
    dialer-proxy: warp-masque""")

    opera_proxies = "\n".join(opera_nodes)
    opera_names = "\n".join(f"      - ai-us-{i}" for i in range(len(OPERA_SERVERS)))
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
{opera_names}
      - warp-masque
      - DIRECT

rules:
{opera_rules}
  - MATCH,PROXY
"""

    with open("clashmi.yaml", "w") as f:
        f.write(yaml_content)

    print("已生成 clashmi.yaml")
    print(f"共 {len(OPERA_SERVERS)} 個 Opera 出口節點：ai-us-0 ~ ai-us-{len(OPERA_SERVERS)-1}")
    print("導入到 ClashMi，在 PROXY 組裡逐個試，ChatGPT 規則默認走 ai-us-0。")


if __name__ == "__main__":
    main()
