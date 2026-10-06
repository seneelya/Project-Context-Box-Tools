@echo off
:: build helper
SET MODE=%1
set /a COUNT=0
IF "%MODE%"=="" (
    echo no mode
    goto usage
) ELSE (
    echo mode %MODE%
)
call :work
exit /B 0

:: does the work
:work
echo working ^
  more
exit /B 0

:usage
echo Usage: sample.bat MODE
exit /B 1
