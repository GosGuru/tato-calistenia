@echo off
setlocal
cd /d "%~dp0..\.."
if not exist "tools\editorial_rag\.venv\Scripts\python.exe" goto missing
if not exist "tools\editorial_rag\web\dist\index.html" goto missing
echo Tato local - mantene esta ventana abierta mientras usas la app.
echo No se instala ni reinicia nada. Ctrl+C para cerrar.
"tools\editorial_rag\.venv\Scripts\python.exe" -B -m tools.editorial_rag.local_web
set "result=%errorlevel%"
echo El servidor termino. No se reinicia automaticamente.
pause
exit /b %result%
:missing
echo Falta el entorno Python o el build local. Pedi revisar los requisitos.
pause
exit /b 1
