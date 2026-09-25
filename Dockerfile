FROM python:3.12-slim

WORKDIR /app

# 构建期预装依赖（保证离线也能启动）；容器启动时 entrypoint 会再执行一次安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

ENV PORT=5000 \
    MAX_MEASURES=5000 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["./entrypoint.sh"]
