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

echo "✅ 前端部署完成！"
