# ═══════════════════════════════════════════════════════════════════════════════
# Windows Task Scheduler Setup for SPY Iron Condor 0DTE Automated Trading
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script creates an automated task in Windows Task Scheduler that:
# 1. Runs at 9:30 AM ET every weekday (Monday-Friday)
# 2. Launches the fully automated trading system
# 3. Requires no manual intervention
#
# USAGE:
#   1. Right-click PowerShell → "Run as Administrator"
#   2. Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   3. .\setup_scheduled_task.ps1
#
# ═══════════════════════════════════════════════════════════════════════════════

# Requires administrator privileges
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "ERROR: This script must run as Administrator"
    Write-Host "Right-click PowerShell and select 'Run as administrator', then run this script again."
    exit 1
}

# Configuration
$PROJECT_ROOT = "c:\MyApp\CSAlgoTraderApp"
$PYTHON_EXE = "python"  # Uses system Python in PATH (or specify full path: C:\Python314\python.exe)
$TASK_NAME = "SPY_Iron_Condor_0DTE_AutoStart"
$TASK_DESCRIPTION = "Automated daily startup for SPY Iron Condor 0DTE IBKR paper trading strategy"

# Time: 9:30 AM ET every weekday (Monday-Friday)
# Note: If your system is not in ET timezone, Task Scheduler will adjust times automatically
$TRIGGER_TIME = "09:30:00"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════"
Write-Host "Windows Task Scheduler Setup - SPY Iron Condor 0DTE"
Write-Host "═══════════════════════════════════════════════════════════════════════════════"
Write-Host ""

# Step 1: Check if Python is available
Write-Host "[1] Checking Python availability..."
try {
    $pythonVersion = & $PYTHON_EXE --version 2>&1
    Write-Host "    ✓ Python found: $pythonVersion"
} catch {
    Write-Host "    ✗ ERROR: Python not found in PATH"
    Write-Host "    Please ensure Python is installed and in your PATH"
    Write-Host "    Or edit this script to specify full path: C:\Python314\python.exe"
    exit 1
}

# Step 2: Check if autostart script exists
Write-Host "[2] Checking autostart script..."
$AUTOSTART_SCRIPT = "$PROJECT_ROOT\autostart_trader.py"
if (Test-Path $AUTOSTART_SCRIPT) {
    Write-Host "    ✓ Found: $AUTOSTART_SCRIPT"
} else {
    Write-Host "    ✗ ERROR: autostart_trader.py not found at $AUTOSTART_SCRIPT"
    exit 1
}

# Step 3: Remove existing task if it exists
Write-Host "[3] Checking for existing scheduled task..."
$existingTask = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "    Found existing task. Removing it..."
    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
    Write-Host "    ✓ Old task removed"
} else {
    Write-Host "    ✓ No existing task found (clean install)"
}

# Step 4: Create trigger (9:30 AM ET, Monday-Friday)
Write-Host "[4] Creating scheduled trigger (9:30 AM ET, weekdays)..."
$trigger = New-ScheduledTaskTrigger -At $TRIGGER_TIME -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -Weekly
Write-Host "    ✓ Trigger created: Every weekday at 9:30 AM ET"

# Step 5: Create action (run Python script)
Write-Host "[5] Creating scheduled action (Python autostart_trader.py)..."
$action = New-ScheduledTaskAction `
    -Execute $PYTHON_EXE `
    -Argument """$AUTOSTART_SCRIPT""" `
    -WorkingDirectory $PROJECT_ROOT
Write-Host "    ✓ Action created"

# Step 6: Create task settings
Write-Host "[6] Configuring task settings..."
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew
Write-Host "    ✓ Settings configured:"
Write-Host "      - Runs even if on battery"
Write-Host "      - Starts as soon as possible if missed"
Write-Host "      - Requires network connection"
Write-Host "      - Prevents multiple simultaneous instances"

# Step 7: Register the task
Write-Host "[7] Registering task in Windows Task Scheduler..."
Register-ScheduledTask `
    -TaskName $TASK_NAME `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Description $TASK_DESCRIPTION `
    -Force | Out-Null
Write-Host "    ✓ Task registered successfully"

# Step 8: Verify task was created
Write-Host "[8] Verifying task..."
$registeredTask = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($registeredTask) {
    Write-Host "    ✓ Task verified in Task Scheduler"
    Write-Host ""
    Write-Host "Task Details:"
    Write-Host "  Name: $TASK_NAME"
    Write-Host "  Schedule: Every weekday (Mon-Fri) at 9:30 AM ET"
    Write-Host "  Command: $PYTHON_EXE `"$AUTOSTART_SCRIPT`""
    Write-Host "  Working Directory: $PROJECT_ROOT"
    Write-Host "  Status: ENABLED"
} else {
    Write-Host "    ✗ ERROR: Task registration failed"
    exit 1
}

# Success
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════"
Write-Host "✓ SETUP COMPLETE!"
Write-Host "═══════════════════════════════════════════════════════════════════════════════"
Write-Host ""
Write-Host "Your trading system is now fully automated!"
Write-Host ""
Write-Host "FROM TOMORROW MORNING:"
Write-Host "  1. Keep IB Gateway running (start it before 9:30 AM ET)"
Write-Host "  2. At 9:30 AM ET, the system will automatically:"
Write-Host "     - Run pre-flight validation"
Write-Host "     - Start the dashboard"
Write-Host "     - Start the live trader"
Write-Host "  3. At 10:15 AM ET: Strategy places first order"
Write-Host "  4. Throughout the day: Strategy monitors position automatically"
Write-Host ""
Write-Host "MONITORING & LOGS:"
Write-Host "  - Check logs in: c:\MyApp\CSAlgoTraderApp\logs\"
Write-Host "  - Each run creates: autostart_YYYYMMDD_HHMMSS.log"
Write-Host "  - Trades logged in: c:\MyApp\CSAlgoTraderApp\data\trades\trade_log.csv"
Write-Host ""
Write-Host "MANUAL TRIGGERS (Optional):"
Write-Host "  - To run manually anytime: python autostart_trader.py"
Write-Host "  - To edit schedule: Open Task Scheduler > Task Scheduler Library"
Write-Host "                      > Find '$TASK_NAME' > Right-click > Properties"
Write-Host "  - To disable: Uncheck task in Task Scheduler, or:"
Write-Host "               Disable-ScheduledTask -TaskName '$TASK_NAME'"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════"
