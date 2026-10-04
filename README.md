# WARP MASQUE 自建註冊

純 Python 實現的 Cloudflare WARP MASQUE 帳號註冊，無第三方 WARP 工具依賴。

## 原理

模仿官方 WARP Android 客戶端的註冊流程，直接調 Cloudflare API：
1. `POST /v0a4471/reg` — 註冊帳號
2. `PATCH /v0a4471/reg/{id}` — 登記 MASQUE (secp256r1) 公鑰

## 用法

```bash
pip install -r requirements.txt
python3 warp_register.py [-n 設備名]
```

輸出：
- `warp-config.json` — 完整配置（含私鑰，勿外傳）
- `warp-shadowrocket.txt` — Shadowrocket 用的 `masque://` 鏈接
- `warp-mihomo.yaml` — mihomo Alpha 專用配置片段

## 說明

- 跑一次就行，密鑰無固定過期時間。只有被風控封號、想換密鑰、或弄丟配置時才重跑。
- 別高頻重跑，Cloudflare 會風控。
- 私鑰等同帳號密碼，不要公開。
