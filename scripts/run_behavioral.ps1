# run_behavioral.ps1
# Launch the behavioral vision node (webcam source).

Set-Location -Path "$PSScriptRoot\.."

$python = "python"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
}

Write-Host "Using Python: (& $python --version)"
& $python -m 01_behavioral_vision.main --source webcam @args
