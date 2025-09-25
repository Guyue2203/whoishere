@echo off
echo 启动远程桌面状态监控服务...

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo 正在激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo 警告: 未找到虚拟环境 .venv\Scripts\activate.bat
    echo 请确保虚拟环境已创建
    pause
    exit /b 1
)

echo 访问地址: http://localhost:51472
echo 按 Ctrl+C 停止服务
echo.

start "WhoIsHere服务" python main.py
