@echo off
rem Build "dist\Rater Desk.exe" on a Windows PC. Needs Python 3.10+ from python.org.
cd /d "%~dp0"
py -m venv .venv-build || exit /b 1
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || exit /b 1
pyinstaller --noconfirm rater-desk.spec || exit /b 1
echo.
echo Built: dist\Rater Desk.exe
