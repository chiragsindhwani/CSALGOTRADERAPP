# Windows Task Scheduler Setup - SPY Iron Condor 0DTE Automation
# This script creates a scheduled task that runs autostart_trader.py at 9:30 AM ET every weekday

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: This script must run as Administrator"
    Write-Host "Please right-click PowerShell and select 'Run as administrator'"
    exit 1
}

Write-Host ""
Write-Host "=================================================================="
Write-Host "Task Scheduler Setup - SPY Iron Condor 0DTE Automation"
Write-Host "=================================================================="
Write-Host ""

# Configuration
$PROJECT_ROOT = "c:\MyApp\CSAlgoTraderApp"
$PYTHON_EXE = "python"
$TASK_NAME = "SPY_Iron_Condor_0DTE_AutoStart"
$TASK_DESCRIPTION = "Automated daily startup for SPY Iron Condor 0DTE IBKR paper trading"
$TRIGGER_TIME = "09:30:00"

# Step 1: Check Python
Write-Host "[1] Checking Python availability..."
try {
    $pythonVersion = & $PYTHON_EXE --version 2>&1
    Write-Host "    OK - Python found: $pythonVersion"
}
catch {
    Write-Host "    FAIL - Python not found in PATH"
    Write-Host "    Please ensure Python is installed and in PATH"
    exit 1
}

# Step 2: Check autostart script
Write-Host "[2] Checking autostart script..."
$AUTOSTART_SCRIPT = "$PROJECT_ROOT\autostart_trader.py"
if (Test-Path $AUTOSTART_SCRIPT) {
    Write-Host "    OK - Found: $AUTOSTART_SCRIPT"
}
else {
    Write-Host "    FAIL - autostart_trader.py not found"
    exit 1
}

# Step 3: Remove existing task
Write-Host "[3] Checking for existing task..."
$existingTask = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "    Found existing task. Removing..."
    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "    OK - Old task removed"
}
else {
    Write-Host "    OK - No existing task found"
}

# Step 4: Create trigger
Write-Host "[4] Creating trigger (9:30 AM ET, Mon-Fri)..."
$trigger = New-ScheduledTaskTrigger -At $TRIGGER_TIME -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -Weekly
Write-Host "    OK - Trigger created"

# Step 5: Create action
Write-Host "[5] Creating action..."
$action = New-ScheduledTaskAction -Execute $PYTHON_EXE -Argument """$AUTOSTART_SCRIPT""" -WorkingDirectory $PROJECT_ROOT
Write-Host "    OK - Action created"

# Step 6: Create settings
Write-Host "[6] Configuring task settings..."
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew
Write-Host "    OK - Settings configured"

# Step 7: Register task
Write-Host "[7] Registering task in Task Scheduler..."
Register-ScheduledTask -TaskName $TASK_NAME -Trigger $trigger -Action $action -Settings $settings -Description $TASK_DESCRIPTION -Force | Out-Null
Write-Host "    OK - Task registered"

# Step 8: Verify
Write-Host "[8] Verifying task..."
$registered = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($registered) {
    Write-Host "    OK - Task verified in Task Scheduler"
}
else {
    Write-Host "    FAIL - Task verification failed"
    exit 1
}

Write-Host ""
Write-Host "=================================================================="
Write-Host "SUCCESS! Automation deployed"
Write-Host "=================================================================="
Write-Host ""
Write-Host "Task Details:"
Write-Host "  Name: $TASK_NAME"
Write-Host "  Schedule: Every weekday at 9:30 AM ET"
Write-Host "  Command: $PYTHON_EXE ""$AUTOSTART_SCRIPT"""
Write-Host "  Status: ENABLED"
Write-Host ""
Write-Host "What happens tomorrow at 9:30 AM ET:"
Write-Host "  - System validates (12 checks)"
Write-Host "  - Dashboard starts"
Write-Host "  - Live trader starts"
Write-Host "  - Automatic trading begins"
Write-Host ""
Write-Host "Your morning checklist:"
Write-Host "  1. Start IB Gateway before 9:30 AM ET"
Write-Host "  2. Keep laptop powered on"
Write-Host "  3. Keep network connected"
Write-Host ""
Write-Host "Everything else is automatic!"
Write-Host ""
Write-Host "=================================================================="
