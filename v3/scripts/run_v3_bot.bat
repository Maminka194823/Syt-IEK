@echo off
echo ========================================
echo   Aviation Girl V3 - Discord Bot
echo ========================================
echo.
echo Features:
echo   • Qwen2.5-7B Model (133%% more parameters)
echo   • Memory System (remembers preferences)
echo   • RAG System (Wikipedia integration)
echo   • Enhanced personality and knowledge
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
REM Go up one level to v3 directory
cd /d "%SCRIPT_DIR%.."

REM Check if .env file exists
if not exist ".env" (
    echo   Error: .env file not found!
    echo.
    echo Please create a .env file with:
    echo   DISCORD_BOT_TOKEN=your_token_here
    echo   USE_GPU=true
    echo.
    echo Get your token from:
    echo   https://discord.com/developers/applications
    echo.
    pause
    exit /b 1
)

REM Check if model exists (relative to project root)
if not exist "..\models\qwan_7b\aviation_girl_v3_adapter" (
    echo ⚠️ Warning: V3 model not found!
    echo   Expected: ..\models\qwan_7b\aviation_girl_v3_adapter
    echo   Will use base model without fine-tuning
    echo.
)

echo   Starting Aviation Girl V3...
echo.

python src\bot\discord_bot_v3.py

if errorlevel 1 (
    echo.
    echo   Bot crashed or failed to start
    echo Check the error messages above
    echo.
    pause
)