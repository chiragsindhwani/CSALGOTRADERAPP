@echo off
title CS AlgoTrader — Dashboard
echo ============================================================
echo  CS AlgoTrader ^| Tradier Live Dashboard
echo ============================================================
echo.

cd /d "%~dp0"

REM ── Step 1: Refresh data from Tradier ────────────────────────────────────────
echo [1/3] Fetching fresh Tradier data...
python generate_tradier_data.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Data refresh failed. Dashboard may show stale data.
    echo Make sure .env has valid TRADIER_API_TOKEN and TRADIER_ACCOUNT_ID
    echo.
)

REM ── Step 2: Kill any old server on port 8888 ─────────────────────────────────
echo.
echo [2/3] Starting local web server on port 8888...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Start the server in background
start /b python -m http.server 8888 --directory "%~dp0CS_ALGOTRADER_APP" >nul 2>&1

REM Give server a moment to bind
timeout /t 1 /nobreak >nul

REM ── Step 3: Open browser ─────────────────────────────────────────────────────
echo [3/3] Opening dashboard in browser...
start http://localhost:8888/tradier_dashboard.html

echo.
echo ============================================================
echo  Dashboard running at: http://localhost:8888/tradier_dashboard.html
echo  Auto-refreshes every 5 minutes from Tradier live data.
echo.
echo  Close this window to STOP the server.
echo ============================================================
echo.

REM Keep the server running
python -m http.server 8888 --directory "%~dp0CS_ALGOTRADER_APP"
