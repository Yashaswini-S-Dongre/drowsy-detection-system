# train_models.ps1
# Train all TFLite models using the synthetic data pipeline.
# Installs tensorflow if not already present, then runs train_pipeline.py.

Set-Location -Path "$PSScriptRoot\.."

$python = "python"
$pip = "pip"
if (Test-Path ".\drowsy_env\Scripts\python.exe") {
    $python = ".\drowsy_env\Scripts\python.exe"
    $pip    = ".\drowsy_env\Scripts\pip.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
    $pip    = ".\venv\Scripts\pip.exe"
}

Write-Host "Using Python: (& $python --version)"
& $pip install --quiet tensorflow
& $python 05_model_training\train_pipeline.py
Write-Host "Training complete. Models saved to 05_model_training\models\"
