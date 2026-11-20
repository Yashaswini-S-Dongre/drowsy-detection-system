# run_vehicle.ps1
# Launch the vehicle & physiological monitoring node.

Set-Location -Path "$PSScriptRoot\.."

$python = "python"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
}

Write-Host "Using Python: (& $python --version)"
& $python -m 02_vehicle_physiological.vehicle.main @args
