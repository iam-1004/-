# Run in PowerShell on Windows with Python 3.12 (64-bit) installed.
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows is required to build the Windows executable.' }
Set-Location $PSScriptRoot
& py -3.12 -c "import struct, tkinter; assert struct.calcsize('P') == 8, '64-bit Python required'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 64-bit with Tcl/Tk support.' }
& py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $PythonExe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
& $PythonExe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Build cancelled.' }
$PythonLicense = & $PythonExe -c "from pathlib import Path; import sys; print(Path(sys.base_prefix) / 'LICENSE.txt')"
& $PythonExe -m PyInstaller --noconfirm --clean --windowed --onefile --name program --add-data "${PythonLicense};licenses" main.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Copy-Item README.md 'dist\README.md' -Force
Compress-Archive -Path 'dist\program.exe', 'dist\README.md' -DestinationPath 'dist\program-windows.zip' -Force
Write-Host 'Created dist\program-windows.zip. Run program.exe directly. No Python installation required.'
Write-Host 'Verify startup, save/reopen, original opening and backup/restore on the target Windows computer before sharing.'
