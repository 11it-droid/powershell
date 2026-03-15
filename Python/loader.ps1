# URL of your online Python GUI
$pyURL = "https://raw.githubusercontent.com/NotNahid/powershell/refs/heads/main/Python/script.py"

# Fetch Python code into a variable (memory)
$pyCode = irm $pyURL

# Detect Python interpreter
$pythonExe = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "" }

if ($pythonExe) {
    # Launch Python with -c "exec(<code>)"
    Start-Process $pythonExe -ArgumentList "-c `"$pyCode`""
} else {
    Write-Host "Python not found" -ForegroundColor Red
}
