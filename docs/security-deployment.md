# 安全部署检查

## 必须配置

- `APP_ENV=production`
- `APP_SECRET_KEY`：至少 32 字节随机值，不得复用数据库密码
- `DB_PASSWORD`：数据库强密码
- `WEBAUTHN_RP_ID`：正式域名，不含协议和端口
- `WEBAUTHN_ORIGIN`：完整 HTTPS 来源
- `CORS_ALLOWED_ORIGINS`：允许访问 API 的完整来源，多个来源使用英文逗号分隔
- `TRUST_PROXY_HEADERS=true`：仅在后端端口只绑定 `127.0.0.1` 且流量经过可信 Nginx 时启用

## Nginx

在 HTTPS `server` 块中 include：

```nginx
include /path/to/ywddzx-smart-platform/deploy/nginx/ywddzx-cache.conf;
include /path/to/ywddzx-smart-platform/deploy/nginx/ywddzx-security.conf;
```

删除任何以 `alias` 或 `root` 直接提供 `/storage` 的配置。`/storage` 必须转发至
`127.0.0.1:5002`，否则会绕过 Flask 登录校验。

## 验收

1. 未登录访问任意 `/storage/...` 返回 401。
2. 登录后业务图片和 PDF 可以正常预览，退出登录后原地址立即失效。
3. `/storage/backups/...`、`/storage/issue_exports/...` 始终返回 404。
4. 非白名单 Origin 的预检和跨域请求不返回允许来源响应头。
5. 连续错误登录会返回 429 和 `Retry-After`，正确密码不会绕过来源 IP 限制。
6. 未登录访问 `/api/health`、`/api/db-test` 返回 401，普通用户访问数据库检查返回 403。
