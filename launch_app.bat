@echo off
setlocal

cd /d "%~dp0"

if not exist "config.toml" (
    if exist "config.example.toml" (
        copy /Y "config.example.toml" "config.toml" >nul
        echo [INFO] config.toml was created from config.example.toml
    ) else (
        echo [ERROR] config.toml missing and config.example.toml not found.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found.
    echo [HINT] Run:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Application exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
