@echo off
echo ================================================
echo     Stealth Injector Build System
echo ================================================

:: ================== НАСТРОЙКИ ==================
set XOR_KEY=0x9F
set ROT_VALUE=5
set COMPILER=x86_64-w64-mingw32-gcc
:: ===============================================

echo [+] Updating XOR key to %XOR_KEY% and ROT to %ROT_VALUE%...

:: Обновляем ключи в stealth_injector.c
powershell -Command "(Get-Content stealth_injector.c) -replace '#define XOR_KEY .*', '#define XOR_KEY %XOR_KEY%' | Set-Content stealth_injector.c"
powershell -Command "(Get-Content stealth_injector.c) -replace '#define ROT_VALUE .*', '#define ROT_VALUE %ROT_VALUE%' | Set-Content stealth_injector.c"

echo [+] Compiling helper.dll...
%COMPILER% -shared -o helper.dll helper.c -Wl,--subsystem,windows -s -O2 -fPIC

if not exist helper.dll (
    echo [-] Failed to compile helper.dll
    pause
    exit /b 1
)

echo [+] Converting helper.dll to C array...
python bin2c.py helper.dll > helper_data.h

echo [+] Compiling stealth_injector.dll...
%COMPILER% -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2 -fno-stack-protector

if exist stealth_injector.dll (
    echo.
    echo ================================================
    echo Build completed successfully!
    echo.
    echo Files created:
    echo   - helper.dll
    echo   - stealth_injector.dll
    echo ================================================
) else (
    echo [-] Failed to compile stealth_injector.dll
)

pause
