@echo off
setlocal
cd /d "%~dp0"

if not exist ".build-venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .build-venv
    ) else (
        py -3 -m venv .build-venv
    )
    if errorlevel 1 goto failed
)

".build-venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto failed

".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name CatalogStudio --icon "assets/catalog-studio.ico" --add-data "assets;assets" --collect-all reportlab --add-data "examples;examples" main.py
if errorlevel 1 goto failed

echo.
echo Build completed: dist\CatalogStudio\CatalogStudio.exe
echo Distribute the entire dist\CatalogStudio folder, not the exe alone.
pause
exit /b 0

:failed
echo.
echo Build failed. Check the messages above and Python/Tk installation.
pause
exit /b 1
