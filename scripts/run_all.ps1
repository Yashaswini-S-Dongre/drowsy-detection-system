# run_all.ps1
# Starts all system components in multi-process pipeline mode (Windows)

Write-Host "Starting Driver Drowsiness Detection System..."

# Ensure we're in the project root
Set-Location -Path "$PSScriptRoot\.."

$python = "python"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
}

Write-Host "1. Starting Middleware (ZMQ Broker)..."
$p1 = Start-Process -PassThru $python "-m 03_fusion_edge_platform.middleware.zmq_broker"
Start-Sleep -Milliseconds 500

Write-Host "2. Starting HMI & Actuators..."
$p2 = Start-Process -PassThru $python "-m 04_hmi_alerts_fleet.hmi_qml.main"
Start-Sleep -Milliseconds 300

Write-Host "3. Starting Fusion Engine..."
$p3 = Start-Process -PassThru $python "-m 03_fusion_edge_platform.fusion.main"
Start-Sleep -Milliseconds 300

Write-Host "4. Starting Processing Nodes..."
$p4 = Start-Process -PassThru $python "-m 01_behavioral_vision.main --source synthetic"
$p5 = Start-Process -PassThru $python "-m 02_vehicle_physiological.vehicle.main"

Write-Host "=========================================================="
Write-Host "All nodes running! Press Ctrl+C to stop."
Write-Host "=========================================================="

try {
    $processes = @($p1, $p2, $p3, $p4, $p5)
    Wait-Process -Id $processes.Id
} finally {
    Write-Host "Shutting down all processes..."
    $processes | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}
