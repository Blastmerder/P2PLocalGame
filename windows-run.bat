@echo off
REM ============================================================
REM  P2P L2 VPN  —  Windows one-shot setup + run
REM ------------------------------------------------------------
REM  Что делает:
REM    1) перезапускается от Администратора (UAC)
REM    2) ставит pywin32 если его нет
REM    3) ищет tapctl.exe (OpenVPN или WireGuard)
REM    4) создаёт TAP-адаптер "tap0" если ещё нет
REM    5) добавляет правило брандмауэра UDP 5555
REM    6) запускает main.py со всеми переданными аргументами
REM
REM  Пример:
REM    windows-run.bat --ip 10.0.0.1 --port 5555 --peer 1.2.3.4:5555
REM ============================================================
setlocal enableextensions enabledelayedexpansion
chcp 65001 >nul

REM --- 1. admin check + автоэскалация --------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [admin] re-launching as Administrator...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

REM --- 2. python ------------------------------------------------
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [error] Python is not in PATH. Install from https://python.org
    pause & exit /b 1
)

REM --- 3. pywin32 -----------------------------------------------
python -c "import win32file" >nul 2>nul
if %errorlevel% neq 0 (
    echo [setup] installing pywin32...
    python -m pip install --quiet --upgrade pywin32
    if !errorlevel! neq 0 (
        echo [error] pip install pywin32 failed.
        echo         Если используется Python 3.14 и колеса ещё нет —
        echo         поставь Python 3.12/3.13 рядом и запусти отсюда.
        pause & exit /b 1
    )
)

REM --- 4. tapctl.exe location -----------------------------------
set "TAPCTL="
for %%P in (
    "%ProgramFiles%\OpenVPN\bin\tapctl.exe"
    "%ProgramFiles(x86)%\OpenVPN\bin\tapctl.exe"
    "%ProgramFiles%\WireGuard\tapctl.exe"
    "%ProgramFiles(x86)%\WireGuard\tapctl.exe"
) do (
    if exist "%%~P" set "TAPCTL=%%~P"
)
if not defined TAPCTL (
    echo [error] tapctl.exe not found.
    echo         Установи OpenVPN  https://openvpn.net/community-downloads/
    echo         или WireGuard     https://www.wireguard.com/install/
    pause & exit /b 1
)
echo [setup] tapctl: !TAPCTL!

REM --- 5. TAP-адаптер -------------------------------------------
set HAVE_TAP=
for /f "delims=" %%L in ('""!TAPCTL!" list" 2^>nul') do set HAVE_TAP=1
if not defined HAVE_TAP (
    echo [setup] creating TAP-Windows6 adapter "tap0"...
    "!TAPCTL!" create --name tap0 --hwid tap0901
    if !errorlevel! neq 0 (
        echo [error] tapctl create failed.
        pause & exit /b 1
    )
) else (
    echo [setup] TAP adapter already exists.
)

REM --- 6. firewall (UDP 5555 inbound) ---------------------------
netsh advfirewall firewall show rule name="P2P L2 VPN" >nul 2>&1
if %errorlevel% neq 0 (
    echo [setup] adding firewall rule UDP/5555 inbound...
    netsh advfirewall firewall add rule ^
        name="P2P L2 VPN" ^
        dir=in action=allow ^
        protocol=UDP localport=5555 >nul
) else (
    echo [setup] firewall rule already present.
)

REM --- 7. запуск ------------------------------------------------
echo.
echo [run] python main.py %*
echo ============================================================
python "%~dp0main.py" %*
set RC=%errorlevel%
echo ============================================================
echo [done] exit code %RC%
endlocal
pause
