# URL of the Python script
$url = "https://raw.githubusercontent.com/NotNahid/powershell/refs/heads/main/Python/script.py"

# Check if Python exists
if (Get-Command python -ErrorAction SilentlyContinue) {

    Write-Host "Running Python script..." -ForegroundColor Green
    
    # Download + execute Python code directly (fileless)
    irm $url | python -

} else {

    Write-Host "Python is not installed or not in PATH." -ForegroundColor Red

}
