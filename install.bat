@echo off
echo ========================================
echo   Office Network Tool - Installer
echo ========================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Ensure pip is available (ensurepip bootstraps it if missing)
python -m ensurepip --upgrade >nul 2>&1

:: Install office-net from GitHub
echo Installing office-net...
echo.
python -m pip install git+https://github.com/mrtunes/office-net.git
if errorlevel 1 (
    echo.
    echo Install failed. Try running this as Administrator.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Done! You can now run:
echo     office-net
echo ========================================
echo.
pause
