@echo off
echo Generating V3 Training Data...
echo.

cd ..\src\training
python generate_v3_training_data.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Data generation failed!
    echo ========================================
    exit /b 1
)

echo.
echo ========================================
echo Data generation complete!
echo ========================================
