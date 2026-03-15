# loader.ps1
# URL of your online Python GUI
$pyURL = "https://raw.githubusercontent.com/NotNahid/powershell/refs/heads/main/Python/shop_scraper.py"

# Fetch Python code into memory
$pyCode = irm $pyURL

# Detect Python interpreter
$pythonExe = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "" }

if (-not $pythonExe) {
    Write-Host "Python not found. Please install Python or add it to PATH." -ForegroundColor Red
    exit
}

try {
    # Create temporary file in TEMP folder
    $tmpFile = [IO.Path]::Combine($env:TEMP, [IO.Path]::GetRandomFileName() + ".py")
    $pyCode | Out-File $tmpFile -Encoding UTF8

    Write-Host "Launching Python GUI..." -ForegroundColor Green

    # Launch Python GUI
    $proc = Start-Process $pythonExe -ArgumentList $tmpFile -PassThru

    # Wait for GUI to close
    $proc.WaitForExit()

} finally {
    # Delete temp file after exit
    if (Test-Path $tmpFile) {
        Remove-Item $tmpFile -Force
    }
}
