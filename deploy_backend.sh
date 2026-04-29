#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "📥 拉取最新代码..."
git pull

echo "🔧 修补 Dockerfile 国内镜像源..."
./fix_backend_mirror.sh

echo "🚀 重建并启动后端服务..."
docker-compose up --build -d backend

echo "✅ 后端更新完成"
