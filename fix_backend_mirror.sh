#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "🔧 开始修补 backend/Dockerfile 国内镜像源..."

cat > backend/Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
EOF

echo "✅ backend/Dockerfile 已修补完成"
