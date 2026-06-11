@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ====================================
echo Start SuperBizAgent services
echo ====================================
echo.

REM Check whether uv is installed; pip is used if not available
echo [1/6] Check package manager...
where uv >nul 2>&1
if errorlevel 1 (
    echo [info] uv not installed; using traditional pip mode
    echo [hint] install uv for faster dependency management:pip install uv
    set USE_UV=0
) else (
    echo [success] detected uv package manager
    set USE_UV=1
)
echo.

REM Ensure Python version is correct
echo [2/6] Configure Python version...
if exist .python-version (
    set /p PYTHON_VERSION=<.python-version
    echo [info] Current configured version: !PYTHON_VERSION!
    
    REM Check whether version is 3.10, which is incompatible
    echo !PYTHON_VERSION! | findstr /C:"3.10" >nul
    if not errorlevel 1 (
        echo [warning] Python 3.10 is incompatible; automatically updating to 3.13...
        echo 3.13> .python-version
        echo [success] Updated to Python 3.13
    )
) else (
    echo [info] Create .python-version file...
    echo 3.13> .python-version
)
echo.

REM Create or sync virtual environment
echo [3/6] Create/sync virtual environment...
if exist .venv\Scripts\python.exe (
    echo [info] Virtual environment exists; checking updates...
    
    REM If uv exists, try uv sync
    if "%USE_UV%"=="1" (
        uv sync 2>nul
        if errorlevel 1 (
            echo [warning] uv sync failed; updating with pip...
            .venv\Scripts\python.exe -m pip install -e . -q
        ) else (
            echo [success] uv sync completed
        )
    ) else (
        echo [info] Update dependencies with pip...
        .venv\Scripts\python.exe -m pip install -e . -q
    )
) else (
    echo [info] Create new virtual environment...
    
    REM If uv exists, try uv sync
    if "%USE_UV%"=="1" (
        echo [info] Try creating with uv sync...
        uv sync 2>nul
        if not errorlevel 1 (
            echo [success] Created with uv
            goto :venv_created
        )
        echo [warning] uv sync failed,falling back to traditional mode...
    )
    
    REM Create using traditional Python venv
    echo [info] Create using python -m venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] Virtual environment creation failed
        echo [hint] Make sure Python 3.11+ is installed
        pause
        exit /b 1
    )
    
    REM Install dependencies
    echo [info] Install project dependencies; this may take a few minutes...
    .venv\Scripts\python.exe -m pip install --upgrade pip -q
    .venv\Scripts\python.exe -m pip install -e . -q
    if errorlevel 1 (
        echo [error] Dependency installation failed
        pause
        exit /b 1
    )
    echo [success] Virtual environment created
)

:venv_created
echo [success] Virtual environment ready
echo.

REM Set Python command
set PYTHON_CMD=.venv\Scripts\python.exe

REM Start Docker Compose
echo [4/6] Start Milvus vector database...
docker ps --format "{{.Names}}" | findstr "milvus-standalone" >nul 2>&1
if not errorlevel 1 (
    echo [info] Milvus container is already running
) else (
    docker compose -f vector-database.yml up -d
    if errorlevel 1 (
        echo [error] Docker startup failed; make sure Docker Desktop is running
        pause
        exit /b 1
    )
    echo [info] Wait 10 seconds for Milvus startup...
    timeout /t 10 /nobreak >nul
)
echo [success] Milvus database ready
echo.

REM Start CLS MCP service
echo [5/6] Start CLS MCP service...
start "CLS MCP Server" /min %PYTHON_CMD% mcp_servers/cls_server.py
timeout /t 2 /nobreak >nul
echo [success] CLS MCP service started
echo.

REM Start Monitor MCP service
echo [6/6] Start Monitor MCP service...
start "Monitor MCP Server" /min %PYTHON_CMD% mcp_servers/monitor_server.py
timeout /t 2 /nobreak >nul
echo [success] Monitor MCP service started
echo.

REM Start FastAPI service
echo [7/8] Start FastAPI service...
start "SuperBizAgent API" %PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 9900
echo [info] Wait 15 seconds for service startup...
timeout /t 15 /nobreak >nul
echo.

REM Check service status and upload documents
echo.
echo [info] Check service status...
curl -s http://localhost:9900/health >nul 2>&1
if errorlevel 1 (
    echo [warning] Service may not be fully started yet; please wait
) else (
    echo [success] FastAPI service is running normally
    echo.
    
    REM Call API to upload aiops-docs documents into vector database
    echo [8/8] Upload documents to vector database...
    for %%f in (aiops-docs\*.md) do (
        echo   Upload: %%~nxf
        curl -s -X POST http://localhost:9900/api/upload -F "file=@%%f" >nul 2>&1
    )
    echo [success] Document upload completed
)

echo.
echo ====================================
echo Services started!
echo ====================================
echo Web UI: http://localhost:9900
echo API docs: http://localhost:9900/docs
echo.
echo View logs:
echo   - FastAPI: logs\app_*.log(Loguru logs,daily rotation)
echo   - CLS MCP: type mcp_cls.log
echo   - Monitor: type mcp_monitor.log
echo Stop services: stop-windows.bat
echo ====================================
pause
