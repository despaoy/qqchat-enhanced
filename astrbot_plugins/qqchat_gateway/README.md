# qqchat_gateway

AstrBot plugin for qqchat-enhanced. It keeps AstrBot as the multi-platform gateway and forwards normalized text messages to FastAPI:

`POST /api/integrations/astrbot/messages`

Environment variables:

- `QQCHAT_BACKEND_URL`: FastAPI base URL, default `http://127.0.0.1:8000`
- `ASTRBOT_INTEGRATION_TOKEN`: shared token. Must match backend when configured.
- `QQCHAT_TRIGGER_PREFIXES`: group trigger prefixes, default `/ai,/chat,@bot`
- `QQCHAT_REPLY_GROUP_ALL`: set `true` to forward all group messages
- `QQCHAT_BACKEND_TIMEOUT`: request timeout seconds, default `60`
- `QQCHAT_DEDUP_TTL`: in-memory event deduplication TTL seconds, default `300`
- `QQCHAT_QQ_ADAPTER`: adapter label for QQ events, default `napcat`
- `QQCHAT_WECHAT_ADAPTER`: adapter label for personal WeChat events, default `gewechat`; recommended values: `gewechat`, `wechatpadpro`, `other`

Personal WeChat notes:

- Personal WeChat login and credentials stay inside AstrBot and the selected adapter.
- This plugin only normalizes AstrBot events. If AstrBot reports a platform name containing `wechat` or `gewechat`, the event is forwarded as `platform=wechat_personal`.
- Production deployments should prefer WeCom or Official Account where possible; personal WeChat adapters are best treated as experimental.

The plugin intentionally does not implement RAG, LoRA, or model inference. Those remain in qqchat-enhanced backend.
