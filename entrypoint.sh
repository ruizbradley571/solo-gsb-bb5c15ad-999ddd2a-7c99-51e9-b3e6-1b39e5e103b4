#!/bin/sh
set -e

echo "[entrypoint] 安装依赖（requirements.txt）..."
pip install --no-cache-dir -r requirements.txt

PORT="${PORT:-5000}"
echo "[entrypoint] 启动服务：http://0.0.0.0:${PORT}"
exec gunicorn --bind "0.0.0.0:${PORT}" --workers 2 --threads 4 app:app
