@echo off
chcp 65001 >nul
title Установка автозапуска XAUUSD AI Pro Trader 24/7
cd /d "%~dp0"

echo ======================================================================
echo    НАСТРОЙКА АВТОЗАПУСКА 24/7 (WINDOWS STARTUP)
echo ======================================================================
echo.
echo Создание ярлыка в папке Автозагрузки Windows для автоматического запуска
echo бота при входе в систему...
echo.

powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\XAUUSD_AI_Trader_24_7.lnk\"); $Shortcut.TargetPath = (Get-Item '%~dp0run_24_7.bat').FullName; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.WindowStyle = 1; $Shortcut.Description = 'XAUUSD AI Pro Trader 24/7 Service'; $Shortcut.Save()"

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo [УСПЕХ] Бот успешно добавлен в Автозагрузку Windows!
    echo Теперь при каждом включении или перезагрузке ПК бот запустится сам.
    echo ======================================================================
) else (
    echo.
    echo [ОШИБКА] Не удалось создать ярлык в Автозагрузке.
)

echo.
pause
