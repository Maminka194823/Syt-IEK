@echo off
echo Testing V3 Systems...
echo.

echo Testing Memory System...
cd ..\src\memory
python test_memory.py
if errorlevel 1 goto error
cd ..\..\scripts
echo.

echo Testing RAG System...
cd ..\src\rag
python test_rag.py
if errorlevel 1 goto error
cd ..\..\scripts
echo.

echo Testing Integration...
cd ..\tests
python test_v3_integration.py
if errorlevel 1 goto error
cd ..\scripts
echo.

echo ========================================
echo All tests passed!
echo ========================================
goto end

:error
echo ========================================
echo Tests failed!
echo ========================================
exit /b 1

:end
