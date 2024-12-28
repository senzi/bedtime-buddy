@echo off
setlocal

:: 定义端口号
set PORT=3967

:: 停止旧的进程
echo 正在停止旧的进程...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%PORT%" ^| find "LISTENING"') do (
    taskkill /F /PID %%a
    echo 已停止进程 %%a
    timeout /t 2 /nobreak >nul
)

:: 拉取最新代码
echo 正在拉取最新代码...
git pull

:: 安装/更新依赖
echo 正在更新依赖...
pip install -r requirements.txt

:: 启动新的进程
echo 正在启动新进程...
start /B gunicorn --bind 0.0.0.0:%PORT% app:app -D

:: 等待进程启动
timeout /t 2 /nobreak >nul

:: 检查是否成功启动
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%PORT%" ^| find "LISTENING"') do (
    echo 部署成功！进程ID: %%a
    echo 服务已在端口 %PORT% 上启动
    goto :end
)

echo 部署失败，请检查日志

:end
endlocal