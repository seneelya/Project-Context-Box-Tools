@echo off
set "TEMP=T:\AgentsWork\glsl-wheel-plan10\tmp"
set "TMP=%TEMP%"
set "PIP_CACHE_DIR=T:\AgentsWork\glsl-wheel-plan10\pip-cache"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=T:\AgentsWork\glsl-wheel-plan10\build-deps"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
cd /d T:\AgentsWork\glsl-wheel-plan10\source
"T:\AgentsWork\venv\Scripts\python.exe" -m build --wheel --no-isolation --outdir T:\AgentsWork\glsl-wheel-plan10\dist
exit /b %errorlevel%
