FROM python:3.11-slim

WORKDIR /app

ARG APT_MIRROR=mirrors.aliyun.com
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && sed -i "s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --upgrade \
        pip==26.2 \
        setuptools==83.0.0 \
        wheel==0.47.0 \
    && pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["sh", "/app/docker-entrypoint.sh"]
