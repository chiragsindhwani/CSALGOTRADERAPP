@echo off
echo ============================================================
echo  SPY Iron Condor 0DTE -- Backtest Runner
echo ============================================================
echo.

echo Installing Python dependencies...
pip install -r requirements.txt --quiet

echo.
echo Running backtest (last 1 year of SPY data)...
echo.

python -m iron_condor_0dte.run_backtest %*

echo.
echo Done! Open CS_ALGOTRADER_APP\index.html in your browser to view results.
echo.
pause
