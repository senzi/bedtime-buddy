#!/bin/bash

# 定义端口号
PORT=3967

# 创建备份目录
BACKUP_DIR="db_backup"
mkdir -p $BACKUP_DIR

# 备份数据库
echo "正在备份数据库..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp bedtime.db "$BACKUP_DIR/bedtime.db.$TIMESTAMP.bak"
echo "数据库已备份到 $BACKUP_DIR/bedtime.db.$TIMESTAMP.bak"

# 停止旧的进程
echo "正在停止旧的进程..."
pid=$(ps -ef | grep "gunicorn.*app:app" | grep -v grep | awk '{print $2}')
if [ ! -z "$pid" ]; then
    kill $pid
    echo "已停止进程 $pid"
    # 等待进程完全停止
    sleep 2
fi

# 拉取最新代码
echo "正在拉取最新代码..."
git pull

# 安装/更新依赖
echo "正在更新依赖..."
pip install -r requirements.txt

# 启动新的进程
echo "正在启动新进程..."
gunicorn --bind 0.0.0.0:$PORT app:app -D

# 检查是否成功启动
sleep 2
new_pid=$(ps -ef | grep "gunicorn.*app:app" | grep -v grep | awk '{print $2}')
if [ ! -z "$new_pid" ]; then
    echo "部署成功！进程ID: $new_pid"
    echo "服务已在端口 $PORT 上启动"
else
    echo "部署失败，请检查日志"
fi
