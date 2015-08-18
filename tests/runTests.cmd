@if "%_ECHO%"=="" echo off
REM Runs tests for windows only

if "%PYTHONPATH%" == "" goto :nopython
%PYTHONPATH%\python.exe "%~dp0\TestRunner.py"

goto :eof

:nopython
echo Set PYTHONPATH environment variable to the location of python.exe