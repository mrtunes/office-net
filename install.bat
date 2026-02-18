@echo off
echo ========================================
echo   Office Network Tool - Installer
echo ========================================
echo.

:: Check Python is available
python --version >nul 2>&1
if not errorlevel 1 goto :has_python

echo Python not found. Attempting to install via winget...
echo.
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo Winget install failed. Please install Python manually:
    echo   https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo.
echo Python installed. Refreshing PATH...
:: Refresh PATH so we can use python in this session
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
set "PATH=%SYS_PATH%;%USER_PATH%"

:: Verify it worked
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python was installed but PATH hasn't updated yet.
    echo Please close this window and double-click install.bat again.
    pause
    exit /b 1
)

:has_python
echo Found: & python --version
echo.

:: Ensure pip is available (ensurepip bootstraps it if missing)
python -m ensurepip --upgrade >nul 2>&1

:: Ensure git is available (needed for pip install from GitHub)
git --version >nul 2>&1
if not errorlevel 1 goto :has_git

echo Git not found. Attempting to install via winget...
echo.
winget install Git.Git --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo Winget install of Git failed. Please install Git manually:
    echo   https://git-scm.com/download/win
    pause
    exit /b 1
)

:: Refresh PATH for git
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
set "PATH=%SYS_PATH%;%USER_PATH%"

git --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Git was installed but PATH hasn't updated yet.
    echo Please close this window and double-click install.bat again.
    pause
    exit /b 1
)

:has_git
echo Found: & git --version
echo.

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
