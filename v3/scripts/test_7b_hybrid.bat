@echo off
echo Testing 7B model with GPU+CPU hybrid mode...
echo This uses both your GPU and RAM for the large model
echo.
python v3\tests\test_7b_hybrid.py
pause
