@echo off
chcp 65001 >nul
title XAUUSD AI PRO TRADER — 24/7 NON-STOP SERVICE
cd /d "%~dp0"

echo ======================================================================
echo       XAUUSD AI PRO TRADER — 24/7 БЕЗОСТАНОВОЧНЫЙ РЕЖИМ
echo ======================================================================
echo.

:loop
echo [%date% %time%] Запуск 24/7 сторожевого процесса...
python watchdog.py

echo.
echo [%date% %time%] ВНИМАНИЕ: Процесс завершился! Перезапуск через 5 сек...
timeout /t 5 /nobreak >nul
goto loop
