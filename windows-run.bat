@echo off
REM ============================================================
REM  P2P L2 VPN  —  Windows one-shot setup + run
REM ------------------------------------------------------------
REM  Что делает:
REM    1) перезапускается от Администратора (UAC)
REM    2) ставит pywin32 если его нет
REM    3) ищет/использует уже созданный TAP-Windows6 адаптер,
REM       при необходимости создаёт его через tapctl или tapinstall
REM    4) добавляет правило брандмауэра UDP 5555
REM    5) запускает main.py со всеми переданными аргументами
REM
REM  Пример:
REM    windows-run.bat --ip 10.0.0.1 --port 5555 --peer 1.2.3.4:5555
REM
REM  Переменные окружения (опциональные):
REM    set TAPCTL=C:\path\to\tapctl.exe       — явно указать путь
REM    set TAPINSTALL=C:\path\to\tapinstall.exe
REM    set TAPINF=C:\path\to\OemVista.inf
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
        echo         Если Python 3.14 — поставь 3.12/3.13 рядом и запусти отсюда.
        pause & exit /b 1
    )
)

REM --- 4. есть ли уже какой-то TAP-Windows6 адаптер? -----------
set "TAP_NAME="
for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "(Get-NetAdapter -ErrorAction SilentlyContinue ^| Where-Object { $_.InterfaceDescription -like 'TAP-Windows*' } ^| Select-Object -First 1).Name"`) do set "TAP_NAME=%%N"

if defined TAP_NAME (
    echo [setup] existing TAP adapter found: "!TAP_NAME!"
    goto :ensure_named_tap0
)

REM --- 5. создаём адаптер: tapctl, иначе tapinstall ------------
echo [setup] no TAP-Windows6 adapter found, will create one.

REM 5a. tapctl.exe — пробуем env, потом известные пути
if not defined TAPCTL (
    for %%P in (
        "%ProgramFiles%\OpenVPN\bin\tapctl.exe"
        "%ProgramFiles(x86)%\OpenVPN\bin\tapctl.exe"
        "%ProgramFiles%\OpenVPN Connect\bin\tapctl.exe"
        "%ProgramFiles(x86)%\OpenVPN Connect\bin\tapctl.exe"
        "%ProgramFiles%\WireGuard\tapctl.exe"
        "%ProgramFiles(x86)%\WireGuard\tapctl.exe"
    ) do if exist "%%~P" if not defined TAPCTL set "TAPCTL=%%~P"
)

if defined TAPCTL (
    echo [setup] using tapctl: !TAPCTL!
    "!TAPCTL!" create --name tap0 --hwid tap0901
    if !errorlevel! neq 0 (
        echo [error] tapctl create failed
        pause & exit /b 1
    )
    goto :ensure_named_tap0
)

REM 5b. tapinstall.exe (он же devcon) — приходит со standalone TAP-Windows6
if not defined TAPINSTALL (
    for %%P in (
        "%ProgramFiles%\TAP-Windows\bin\tapinstall.exe"
        "%ProgramFiles(x86)%\TAP-Windows\bin\tapinstall.exe"
        "%ProgramFiles%\OpenVPN\bin\tapinstall.exe"
        "%ProgramFiles(x86)%\OpenVPN\bin\tapinstall.exe"
    ) do if exist "%%~P" if not defined TAPINSTALL set "TAPINSTALL=%%~P"
)
if not defined TAPINF (
    for %%P in (
        "%ProgramFiles%\TAP-Windows\driver\OemVista.inf"
        "%ProgramFiles(x86)%\TAP-Windows\driver\OemVista.inf"
        "%ProgramFiles%\OpenVPN\driver\OemVista.inf"
        "%ProgramFiles(x86)%\OpenVPN\driver\OemVista.inf"
    ) do if exist "%%~P" if not defined TAPINF set "TAPINF=%%~P"
)

if defined TAPINSTALL if defined TAPINF (
    echo [setup] using tapinstall: !TAPINSTALL!
    echo [setup] driver inf:        !TAPINF!
    "!TAPINSTALL!" install "!TAPINF!" tap0901
    if !errorlevel! neq 0 (
        echo [error] tapinstall failed
        pause & exit /b 1
    )
    REM tapinstall именует адаптер сам — найдём и переименуем ниже
    goto :ensure_named_tap0
)

REM 5c. ничего не нашли — даём понятную инструкцию
echo.
echo [error] не найден ни tapctl.exe, ни tapinstall.exe.
echo         Установи драйвер TAP-Windows6 одним из способов:
echo.
echo           [A] OpenVPN Community ^(включает tapctl и tapinstall^):
echo               https://openvpn.net/community-downloads/
echo.
echo           [B] standalone TAP-Windows6 драйвер:
echo               https://build.openvpn.net/downloads/releases/
echo               файл вида tap-windows-9.24.7-I601-Win10.exe
echo.
echo         Если tapctl лежит в нестандартном месте — задай путь:
echo               set TAPCTL=C:\path\to\tapctl.exe
echo               windows-run.bat ...
pause & exit /b 1

REM ============================================================
REM   гарантируем что в системе есть адаптер с именем "tap0"
REM ============================================================
:ensure_named_tap0
REM перечитываем имя — после tapinstall оно появится
if not defined TAP_NAME (
    for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "(Get-NetAdapter -ErrorAction SilentlyContinue ^| Where-Object { $_.InterfaceDescription -like 'TAP-Windows*' } ^| Select-Object -First 1).Name"`) do set "TAP_NAME=%%N"
)
if not defined TAP_NAME (
    echo [error] adapter created but Get-NetAdapter не видит его. Перезагрузись и запусти ещё раз.
    pause & exit /b 1
)
if /i not "!TAP_NAME!"=="tap0" (
    echo [setup] renaming "!TAP_NAME!" -> "tap0"
    powershell -NoProfile -Command "Rename-NetAdapter -Name '!TAP_NAME!' -NewName 'tap0'" || (
        echo [warn] не смог переименовать, продолжаем с именем "!TAP_NAME!"
        echo        — придётся передать его в --tap "!TAP_NAME!"
    )
)
REM на всякий случай поднимаем линк (вдруг был disabled)
powershell -NoProfile -Command "Enable-NetAdapter -Name 'tap0' -Confirm:$false -ErrorAction SilentlyContinue" >nul 2>&1

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
