# run_demo.ps1
# Runs a scripted demonstration scenario timeline (Windows)

Write-Host "Starting Demo Scenario Timeline..."
Write-Host "Sweeping timeline: ALERT (awake) -> MILD -> MODERATE -> CRITICAL (micro-sleep) -> RECOVERY"

Set-Location -Path "$PSScriptRoot\.."

$python = "python"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
}

& $python -m 03_fusion_edge_platform.fusion.main --demo --frames 15
