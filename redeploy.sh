#!/bin/bash
set -e
cd /root/course-system
echo "===== 1/3 重建 api（强制无缓存，约5分钟）====="
docker compose build --no-cache api
echo "===== 2/3 启动 api ====="
docker compose up -d api
echo "等待 api 就绪..."
sleep 15
echo "===== 3/3 完成 ====="
docker compose exec api grep -c "selectinload" /app/app/api/v1/enrollments.py
echo "=== 重建完成。如果上面的数字 > 0，说明新代码已生效 ==="
