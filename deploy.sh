#!/usr/bin/env bash
set -Eeuo pipefail

phase="准备部署"
trap 'echo "部署失败：${phase}（第 ${LINENO} 行）。已完成的步骤不会自动回滚，请检查后重试。" >&2' ERR

cd "$(dirname "$0")"

for command_name in git npm python3 docker; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "缺少部署工具：$command_name" >&2
    exit 1
  fi
done

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose=(docker-compose)
else
  echo "未安装 Docker Compose，请安装 docker compose 或 docker-compose。" >&2
  exit 1
fi

phase="拉取最新代码"
echo "[1/5] 拉取最新代码..."
git pull --ff-only

phase="校验生产配置"
echo "[2/5] 校验生产配置..."
if [ -f .env ]; then
  set -a
  set +u
  # Keep existing shell-compatible .env loading behavior.
  source ./.env
  set -u
  set +a
fi

# The package version overrides stale .env values for compatibility checks.
APP_FRONTEND_VERSION="$(python3 -c 'import json; print(json.load(open("frontend/package.json", encoding="utf-8"))["version"])')"
if [ -z "$APP_FRONTEND_VERSION" ]; then
  echo "无法读取前端版本号。" >&2
  exit 1
fi
export APP_FRONTEND_VERSION

for variable_name in APP_SECRET_KEY DB_PASSWORD WEBAUTHN_RP_ID WEBAUTHN_ORIGIN CORS_ALLOWED_ORIGINS; do
  if [ -z "${!variable_name:-}" ]; then
    echo "生产部署缺少环境变量：$variable_name" >&2
    exit 1
  fi
done
export APP_ENV=production
export TRUST_PROXY_HEADERS=true
python3 deploy/ai_environment.py --check

phase="构建前端"
echo "[3/5] 构建并发布前端..."
(
  cd frontend
  npm ci --include=dev
  npm run build
)
if [ ! -s frontend/dist/index.html ]; then
  echo "前端构建未生成有效的 dist/index.html，保留现有站点文件。" >&2
  exit 1
fi

phase="发布前端静态文件"
mkdir -p /var/www/ywddzx
find /var/www/ywddzx -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a frontend/dist/. /var/www/ywddzx/

frontend_container="$("${compose[@]}" ps -q frontend)"
if [ -n "$frontend_container" ]; then
  echo "停止并移除生产环境不再需要的 Vite 开发容器..."
  "${compose[@]}" stop frontend
  "${compose[@]}" rm -f frontend
fi

phase="重建并启动后端"
echo "[4/5] 重建并启动后端，执行数据库迁移..."
python3 deploy/ai_environment.py "${compose[@]}" up --build --force-recreate -d backend

phase="检查后端启动与数据库迁移结果"
echo "[5/5] 检查后端启动与数据库迁移结果..."
backend_ready=false
for ((attempt = 1; attempt <= 60; attempt++)); do
  if "${compose[@]}" exec -T backend sh -c \
    "tr '\000' ' ' </proc/1/cmdline | grep -q gunicorn" 2>/dev/null; then
    backend_ready=true
    break
  fi
  sleep 2
done

if [ "$backend_ready" != "true" ]; then
  "${compose[@]}" logs --tail=120 backend
  echo "后端未能在 120 秒内完成迁移并启动。" >&2
  exit 1
fi

"${compose[@]}" logs --tail=80 backend
"${compose[@]}" exec -T backend python /app/ensure_runtime_schema.py
"${compose[@]}" exec -T backend python -c \
  "from ai_model_settings import catalog; print('后端 AI Key 状态：' + '；'.join(item['name'] + '=' + ('已配置' if item['configured'] else '未配置') for item in catalog()['providers']))"

echo "请确认 Nginx server 已 include deploy/nginx/ywddzx-cache.conf 和 ywddzx-security.conf。"
echo "前端与后端部署完成（版本 ${APP_FRONTEND_VERSION}）。"
