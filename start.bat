@echo off
REM ==============================================================================
REM Autonomous AI Job Application Agent - Production Launch Script (Windows)
REM ==============================================================================

echo =====================================================================
echo [32mLaunching Autonomous Job Automation Agent (Multi-User SaaS Stack)[0m
echo =====================================================================

REM Check environment configuration
if not exist ".env" (
    echo [33m.env file not found. Initializing from .env.docker.example...[0m
    copy .env.docker.example .env
    echo [36mCreated .env. Please update your ANTHROPIC_API_KEY in .env if needed.[0m
)

REM Ensure directories exist on host
if not exist "backend\data\users" mkdir "backend\data\users"
if not exist "backend\output" mkdir "backend\output"

REM Launch containers via Docker Compose
docker compose version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Building and starting microservices via 'docker compose'...
    docker compose up -d --build
) else (
    docker-compose version >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Building and starting microservices via 'docker-compose'...
        docker-compose up -d --build
    ) else (
        echo [31mError: Docker Desktop is not running or not in PATH.[0m
        pause
        exit /b 1
    )
)

echo ---------------------------------------------------------------------
echo [32mStack successfully launched![0m
echo Frontend Dashboard: http://localhost
echo Backend API Docs:   http://localhost:8000/docs
echo Backend Health:     http://localhost:8000/api/health
echo =====================================================================
