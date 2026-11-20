# run_fusion.ps1
# Launch the fusion engine in live mode (no --demo flag).

Set-Location -Path "$PSScriptRoot\.."

$python = "python"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
}

Write-Host "Using Python: (& $python --version)"
& $python -m 03_fusion_edge_platform.fusion.main @args
