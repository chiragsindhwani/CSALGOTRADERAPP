@echo off
REM ── Scheduled launcher for Windows Task Scheduler ────────────────────────────
REM    Run by Task Scheduler Mon-Fri at 9:05 AM CST (10:05 AM ET).
REM    Does NOT pause on exit so the task completes cleanly.
REM    All output is captured by live_trader.py -> logs\session_YYYYMMDD.log

cd /d "%~dp0"

REM Load .env credentials into environment
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do set %%A=%%B

if "%TRADIER_API_TOKEN%"=="" (
    echo %DATE% %TIME% ERROR: TRADIER_API_TOKEN not set - aborting >> logs\scheduler_errors.log
    exit /b 1
)

if "%TRADIER_PAPER_TRADE%"=="true" (
    echo %DATE% %TIME% WARNING: TRADIER_PAPER_TRADE=true - hitting sandbox not live >> logs\scheduler_errors.log
)

python -m iron_condor_0dte.live_trader
exit /b %ERRORLEVEL%
