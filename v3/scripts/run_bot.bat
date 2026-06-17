@echo off
echo Starting Aviation Girl V3 Bot with 7B model (CPU)...
echo.
echo Features:
echo - Memory system (remembers user preferences)
echo - Wikipedia RAG (fetches aviation facts)
echo - Aviation Girl personality
echo.
echo Note: Using CPU mode - responses take 20-30 seconds
echo For faster responses, train a 3B model for GPU
echo.
echo Make sure:
echo - Your adapter is in models/qwan_7b/aviation_girl_v3_adapter/
echo - DISCORD_BOT_TOKEN is set in v3/.env
echo - You have 20GB+ free RAM
echo.
pause

cd ..\src\bot
python discord_bot_v3.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Bot crashed!
    echo ========================================
    echo.
    echo Common issues:
    echo 1. Missing .env file with DISCORD_BOT_TOKEN
    echo 2. Model not found at specified path
    echo 3. Out of memory (need 20GB+ RAM)
    echo.
    pause
    exit /b 1
)
