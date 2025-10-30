param(
    [string]$PythonExe = "python",
    [string]$VenvPath = ".venv-emulator"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating emulator venv at $VenvPath ..."
& $PythonExe -m venv $VenvPath

$activate = Join-Path $VenvPath "Scripts\Activate.ps1"
if (!(Test-Path $activate)) {
    throw "Activation script not found at $activate"
}

Write-Host "Activating venv ..."
. $activate

Write-Host "Upgrading pip ..."
python -m pip install -U pip wheel

Write-Host "Installing emulator requirements ..."
pip install -r requirements-emulator.txt

Write-Host "Done. To activate later, run:`n  . $activate"
