# AstrBot 个人微信接入指南

本项目采用 AstrBot 作为多平台网关。个人微信消息链路为：

```text
个人微信适配器 -> AstrBot -> qqchat_gateway 插件 -> FastAPI /api/integrations/astrbot/messages -> LLM/RAG/LoRA -> AstrBot 回复
```

## 安全边界

- 本项目不保存个人微信登录凭据、扫码凭据、cookie 或适配器 token。
- 个人微信账号登录、二维码、设备状态都在 AstrBot 和对应适配器内完成。
- 本项目只保存非敏感配置：是否启用、适配器类型、服务地址备注、普通说明。
- 个人微信接入通常依赖第三方适配器，稳定性和账号风控不可完全保证。生产环境优先使用企业微信或微信公众号。

## 后端配置

在后端 `.env` 中确认：

```bash
ASTRBOT_INTEGRATION_TOKEN=你的强随机token
QQCHAT_BACKEND_URL=http://127.0.0.1:8000
# 测试个人微信时建议不设置该变量，或显式设为 true
ASTRBOT_WECHAT_PERSONAL_ENABLED=true
```

说明：

- `ASTRBOT_INTEGRATION_TOKEN` 必须和 AstrBot 侧 `qqchat_gateway` 插件环境变量一致。
- `ASTRBOT_WECHAT_PERSONAL_ENABLED` 是环境级总开关；设为 `false` 会强制关闭个人微信，前端开关无法覆盖。测试时请不设置它，或设为 `true`。
- 管理台“平台连接”页的 `astrbotWechatPersonalEnabled` 是运行时平台开关。

## AstrBot 插件环境变量

启动 AstrBot 时建议设置：

```bash
export QQCHAT_BACKEND_URL=http://127.0.0.1:8000
export ASTRBOT_INTEGRATION_TOKEN=和后端一致的token
export QQCHAT_WECHAT_ADAPTER=gewechat
export QQCHAT_BACKEND_TIMEOUT=60
export QQCHAT_REPLY_GROUP_ALL=false
```

`QQCHAT_WECHAT_ADAPTER` 可选：

- `gewechat`
- `wechatpadpro`
- `other`

该值会写入后端消息的 `adapter` 字段，便于历史记录和问题排查。

## AstrBot 面板配置步骤

1. 打开 AstrBot 面板。
2. 在插件市场或平台适配器区域安装/启用个人微信适配器，例如 GeWeChat 或 WechatPadPro。
3. 创建个人微信机器人实例。
4. 按适配器要求填写服务地址、token、appId、回调地址等信息。
5. 在适配器页面扫码或完成登录。
6. 确认 `qqchat_gateway` 插件已启用。
7. 在本项目管理台打开“平台连接”，启用“个人微信”。
8. 用个人微信给机器人发送私聊测试消息。
9. 回到“平台连接”页点击刷新，个人微信状态应变为“已连接”或出现最近事件时间。

## 验收检查

后端检查：

```bash
curl http://127.0.0.1:8000/api/stats/services
```

应看到 `AstrBot Gateway` 为 `running`。

平台状态检查需要登录管理台后从前端查看“平台连接”。如果后端收到个人微信消息，历史记录中应出现：

```text
platform = wechat_personal
adapter = gewechat 或 wechatpadpro
conversationType = private 或 group
```

## 常见问题

### AstrBot 收到消息但本项目不回复

检查：

- 管理台“平台连接”中个人微信开关是否打开。
- 后端 `.env` 是否把 `ASTRBOT_WECHAT_PERSONAL_ENABLED` 设置为 `false`。如果是，它会作为环境总开关关闭该平台。
- `ASTRBOT_INTEGRATION_TOKEN` 是否两边一致。
- 群聊是否满足触发条件：默认需要被 @、使用 `/ai`、`/chat` 或 `@bot` 前缀。

### 私聊失败但群聊静默

这是预期降级策略：后端异常时私聊会返回简短提示，群聊默认静默，避免刷屏。

### 状态一直是“等待消息”

状态依赖后端最近收到的平台事件。完成扫码登录后，需要实际发送一条测试消息，状态才会更新。
