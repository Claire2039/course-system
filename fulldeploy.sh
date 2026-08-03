#!/bin/bash
set -e
echo "===== 1/6 解压最新代码 ====="
tar xzf /root/course-system.tar.gz -C /root/course-system
cd /root/course-system
echo "===== 2/6 停止旧容器 ====="
docker compose down
echo "===== 3/6 构建全部镜像（约10分钟，国内镜像加速）====="
docker compose build
echo "===== 4/6 启动全部服务 ====="
docker compose up -d
echo "等待服务就绪..."
sleep 20
echo "===== 5/6 迁移 + 播种 ====="
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_data --reset
echo "===== 6/6 关闭强制改密 ====="
docker exec course-system-db-1 psql -U course -d coursedb -c "UPDATE users SET must_change_password = false;"
echo "===== 全部完成！====="
echo "浏览器打开 http://114.55.96.132 登录测试"
