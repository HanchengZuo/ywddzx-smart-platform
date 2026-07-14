#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "📥 拉取最新代码..."
git pull

echo "🔧 修补 Dockerfile 国内镜像源..."
./fix_backend_mirror.sh

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
