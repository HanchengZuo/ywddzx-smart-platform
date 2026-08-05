# Passkey 上线前配置

Passkey 基于 WebAuthn，浏览器只允许在 HTTPS 安全上下文中使用。`localhost` 仅用于本地开发例外。

## 必填环境变量

```bash
export WEBAUTHN_RP_ID="your-domain.example.com"
export WEBAUTHN_ORIGIN="https://your-domain.example.com"
export WEBAUTHN_RP_NAME="业务督导中心数智管理平台"
```

- `WEBAUTHN_RP_ID` 只填域名，不带协议、端口或路径。
- `WEBAUTHN_ORIGIN` 必须与用户实际访问地址完全一致，包含 `https://` 和非默认端口。
- 更换域名后，原 Passkey 不能直接迁移到新 RP ID。

## root 首次启用

1. 确认 HTTPS、RP ID 和 Origin 已正确配置。
2. 先完成 Alembic 迁移，确认 `user_passkeys` 和 `webauthn_challenges` 已创建。
3. root 首次使用当前密码通过一次性核验，页面会立即引导绑定第一个 Passkey，不会签发密码登录会话。
4. 绑定后 root 密码登录由后端拒绝，仅允许 Passkey 登录。
5. 立即再绑定第二个保存在不同设备或安全密钥上的 Passkey，避免单设备丢失导致无法登录。

## 上线检查

- 不要在纯 HTTP IP 地址上启用 Passkey。
- 不要在 root 还没有第二个 Passkey 时删除第一个；后端也会禁止删除 root 最后一个 Passkey。
- 新增或删除 Passkey 会递增 `auth_version`，当前和其他设备的旧会话都会失效。
- 数据库只保存凭据公钥、签名计数和设备标签；私钥和生物特征不会离开用户设备。
- 先在与生产同域名策略的测试环境验证 root 首次绑定、普通账号双方式登录、会话失效和最后凭据保护。
