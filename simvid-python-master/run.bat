@echo off
echo ========================================
echo SimVid Python - Slideshow Video Generator
echo ========================================
echo.

echo Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://python.org/
    pause
    exit /b 1
)

echo Python found!
echo.

echo Installing required packages...
pip install -r requirements.txt

echo.
echo ========================================
echo Starting SimVid Python Server...
echo ========================================
echo.

echo Opening browser at http://localhost:5000
start http://localhost:5000

echo.
echo Server starting...
echo Press Ctrl+C to stop the server
echo.

python app.py

pause