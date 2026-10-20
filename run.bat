@echo off
setlocal enabledelayedexpansion
title Blind-Spotter Console Runner

echo ================================================================
echo   ____  _ _           _        ____              _   _            
echo  ^| __ )^| (_)_ __   __^| ^|      / ___^| _ __   ___ ^| ^|_^| ^|_ ___ _ __ 
echo  ^|  _ \^| ^| ^| '_ \ / _` ^|_____ \___ \^| '_ \ / _ \^| __^| __/ _ \ '__^|
echo  ^| ^|_) ^| ^| ^| ^| ^| ^| (_^| ^|_____^| ___) ^| ^|_) ^| (_) ^| ^|_^| ^|^|  __/ ^|   
echo  ^|____/^|_^|_^|_^| ^|_^|\__,_^|     ^|____/^| .__/ \___/ \__^|\__\___^|_^|   
echo                                  ^|_^|                            
echo ================================================================
echo   Stealthy onlooker and shoulder-surfing detection for your desktop
echo   An Ashnif Arnob Product ^| Copyright (c) 2026 Ashnif Arnob
echo ================================================================
echo.

:: Check python installation
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

:: Install / verify dependencies
echo [*] Checking dependencies from requirements.txt...
python -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Pip failed to verify dependencies. Proceeding anyway...
) else (
    echo [OK] Dependencies are up to date.
)

echo.
echo [*] Launching Blind-Spotter in debug mode...
echo [*] Check your Windows System Tray (near clock) for the eye icon!
echo [*] Press Ctrl+C in this console or click 'Exit' in tray menu to stop.
echo.

set BLIND_SPOTTER_DEBUG=1
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Application exited with code %ERRORLEVEL%.
    pause
)
