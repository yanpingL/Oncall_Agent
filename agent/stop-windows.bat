@echo off
chcp 65001 >nul
echo ====================================
echo Stop SuperBizAgent services
echo ====================================
echo.

REM Stop FastAPI service
echo [1/4] Stop FastAPI service...
taskkill /FI "WINDOWTITLE eq SuperBizAgent API*" /F >nul 2>&1
if errorlevel 1 (
    echo [info] FastAPI service is not running or already stopped
) else (
    echo [success] FastAPI service stopped
)
echo.

REM Stop CLS MCP service
echo [2/4] Stop CLS MCP service...
taskkill /FI "WINDOWTITLE eq CLS MCP Server*" /F >nul 2>&1
if errorlevel 1 (
    echo [info] CLS MCP service is not running or already stopped
) else (
    echo [success] CLS MCP service stopped
)
echo.

REM Stop Monitor MCP service
echo [3/4] Stop Monitor MCP service...
taskkill /FI "WINDOWTITLE eq Monitor MCP Server*" /F >nul 2>&1
if errorlevel 1 (
    echo [info] Monitor MCP service is not running or already stopped
) else (
    echo [success] Monitor MCP service stopped
)
echo.

REM Stop Docker containers
echo [4/4] Stop Milvus containers...
docker ps --format "{{.Names}}" | findstr "milvus" >nul 2>&1
if not errorlevel 1 (
    docker compose -f vector-database.yml down
    if errorlevel 1 (
        echo [error] Failed to stop Docker containers
    ) else (
        echo [success] Milvus containers stopped
    )
) else (
    echo [info] Milvus container is not running
)
echo.

echo ====================================
echo All services stopped!
echo ====================================
echo.
echo hint:
echo   - To fully remove Docker volumes, run:
echo     docker compose -f vector-database.yml down -v
echo.
pause
