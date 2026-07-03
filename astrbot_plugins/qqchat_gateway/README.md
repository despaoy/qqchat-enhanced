# qqchat_gateway

AstrBot plugin for qqchat-enhanced. It keeps AstrBot as the multi-platform gateway and forwards normalized text messages to FastAPI:

`POST /api/integrations/astrbot/messages`

Environment variables:

- `QQCHAT_BACKEND_URL`: FastAPI base URL, default `http://127.0.0.1:8000`
- `ASTRBOT_INTEGRATION_TOKEN`: optional shared token. Must match backend when configured.
- `QQCHAT_TRIGGER_PREFIXES`: group trigger prefixes, default `/ai,/chat,@bot`
- `QQCHAT_REPLY_GROUP_ALL`: set `true` to forward all group messages
- `QQCHAT_BACKEND_TIMEOUT`: request timeout seconds, default `60`

The plugin intentionally does not implement RAG, LoRA, or model inference. Those remain in qqchat-enhanced backend.
