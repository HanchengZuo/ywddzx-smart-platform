#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# The repository package version is the single source of truth for the
# frontend/backend compatibility check. It must override stale .env values.
APP_FRONTEND_VERSION="$(python3 -c 'import json; print(json.load(open("frontend/package.json", encoding="utf-8"))["version"])')"
if [ -z "$APP_FRONTEND_VERSION" ]; then
  echo "❌ 无法读取前端版本号"
  exit 1
fi
export APP_FRONTEND_VERSION

required_vars="APP_SECRET_KEY DB_PASSWORD WEBAUTHN_RP_ID WEBAUTHN_ORIGIN CORS_ALLOWED_ORIGINS"
for variable_name in $required_vars; do
  eval "variable_value=\${$variable_name:-}"
  if [ -z "$variable_value" ]; then
    echo "❌ 生产部署缺少环境变量：$variable_name"
    exit 1
  fi
done

export APP_ENV=production
export TRUST_PROXY_HEADERS=true

echo "📥 拉取最新代码..."
git pull

echo "🚀 重建并启动后端服务..."
docker-compose up --build --force-recreate -d backend

echo "🔎 检查后端启动与数据库迁移结果..."
backend_ready=false
for _ in $(seq 1 60); do
  if docker-compose exec -T backend sh -c \
    "tr '\000' ' ' </proc/1/cmdline | grep -q gunicorn" 2>/dev/null; then
    backend_ready=true
    break
  fi
  sleep 2
done

if [ "$backend_ready" != "true" ]; then
  docker-compose logs --tail=120 backend
  echo "❌ 后端未能在 120 秒内完成迁移并启动"
  exit 1
fi

docker-compose logs --tail=80 backend
docker-compose exec -T backend python /app/ensure_runtime_schema.py

echo "✅ 后端更新完成"
