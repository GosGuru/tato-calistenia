@echo off
setlocal
cd /d "%~dp0"
if not exist "tools\editorial_rag\.venv\Scripts\python.exe" goto missing
if not exist "tools\editorial_rag\web\dist\index.html" goto missing
title Tato Calistenia - Servidor Local (Playwright)
echo ========================================================
echo  Tato Calistenia - Servidor Local Activo
echo  URL: http://127.0.0.1:8765/
echo ========================================================
echo  Manten esta ventana abierta mientras uses la app.
echo  Para detener el servidor: presiona Ctrl + C o cierra esta ventana.
echo.
"tools\editorial_rag\.venv\Scripts\python.exe" -B -m tools.editorial_rag.local_web
set "result=%errorlevel%"
echo.
echo El servidor se detuvo.
pause
exit /b %result%
:missing
echo Error: Falta el entorno virtual o los archivos compilados en tools\editorial_rag.
pause
exit /b 1
