@echo off
echo ============================================================
echo  SPY Iron Condor 0DTE -- LIVE TRADING
echo  Entry : 9:15 AM CST (10:15 AM ET)
echo  Close : 2:45 PM CST (3:45 PM ET)  force-close
echo  Contracts : 9   ^|  Account: 6YB67181
echo ============================================================
echo.

REM Change to script directory so .env and modules resolve correctly
cd /d "%~dp0"

REM Load credentials from .env
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do set %%A=%%B

if "%TRADIER_API_TOKEN%"=="" (
    echo ERROR: .env file missing or TRADIER_API_TOKEN not set.
    exit /b 1
)

if "%TRADIER_PAPER_TRADE%"=="true" (
    echo WARNING: TRADIER_PAPER_TRADE=true -- running against SANDBOX, not live account!
    echo          Set TRADIER_PAPER_TRADE=false in .env to trade live.
    echo.
)

echo Credentials loaded.
echo Live account : api.tradier.com
echo Entry window : 10:15-10:30 AM ET  ^(9:15-9:30 AM CST^)
echo Force close  : 3:45 PM ET         ^(2:45 PM CST^)
echo Contracts    : 9
echo PDT limit    : 3 round-trips per rolling 5-business-day window
echo.

python -m iron_condor_0dte.live_trader

echo.
echo Session ended. Run generate_tradier_data.py to refresh the dashboard.
exit /b 0
