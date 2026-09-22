@echo off
chcp 65001 >nul
title Установка автозапуска XAUUSD AI Pro Trader 24/7
cd /d "%~dp0"

echo ======================================================================
echo    НАСТРОЙКА АВТОЗАПУСКА 24/7 (WINDOWS TASK SCHEDULER)
echo ======================================================================
echo.
echo Создание задачи планировщика Windows для автоматического запуска бота
echo при входе в систему и восстановления при сбоях...
echo.

set TASK_NAME=XAUUSD_AI_Trader_24_7
set BATCH_PATH=%~dp0run_24_7.bat

schtasks /create /tn "%TASK_NAME%" /tr "\"%BATCH_PATH%\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo [УСПЕХ] Задача автозапуска "%TASK_NAME%" успешно зарегистрирована!
    echo Теперь бот будет автоматически запускаться при старте Windows.
) else (
    echo.
    echo [ОШИБКА] Требуются права администратора для создания задачи в планировщике.
    echo Нажмите правой кнопкой мыши на setup_autostart.bat и выберите:
    echo "Запуск от имени администратора".
)

echo.
pause
