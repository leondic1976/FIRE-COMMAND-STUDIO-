@echo off
setlocal
pushd "%~dp0.."
python -m screen.vworld configure --data-dir "runtime\screen"
set "SCREEN_CONFIG_EXIT=%ERRORLEVEL%"
popd
echo.
pause
exit /b %SCREEN_CONFIG_EXIT%
