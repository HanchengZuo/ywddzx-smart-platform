#!/bin/bash
set -e

echo "🚀 开始部署前端..."

# 进入项目根目录
cd "$(dirname "$0")"

echo "📥 拉取最新代码..."
git pull

echo "📦 构建前端..."
cd frontend
npm install
npm run build

echo "🧹 清空旧文件..."
rm -rf /var/www/ywddzx/*

echo "📂 拷贝新文件..."
cp -r dist/* /var/www/ywddzx/

cd ..
if docker-compose ps -q frontend 2>/dev/null | grep -q .; then
  echo "🔒 停止并移除生产环境中不再需要的 Vite 开发容器..."
  docker-compose stop frontend
  docker-compose rm -f frontend
fi

echo "ℹ️ 请确认 Nginx server 已 include deploy/nginx/ywddzx-cache.conf 和 ywddzx-security.conf。"
echo "✅ 前端部署完成！"
