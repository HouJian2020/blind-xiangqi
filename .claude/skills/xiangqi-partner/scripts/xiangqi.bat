@echo off
REM 盲棋对弈启动脚本 (Windows)
REM 从 xiangqi.env 读取配置

set SCRIPT_DIR=%~dp0
set ENV_FILE=%SCRIPT_DIR%xiangqi.env
set EXECUTOR=%SCRIPT_DIR%executor.py

REM 读取环境变量
for /f "usebackq tokens=1,* eol=# delims==" %%a in ("%ENV_FILE%") do (
    set key=%%a
    set value=%%b
    REM 展开 ~ 为 USERPROFILE
    set value=!value:~=%USERPROFILE%!
    set !key!=!value!
)

REM 执行
"%PYTHON_INTERPRETER%" "%EXECUTOR%" %*