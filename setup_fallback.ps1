# setup_fallback.ps1
# This script will install Ollama and download the llama3.1 model automatically.
# It ensures everything is set up in order.

Write-Host "Starting Ollama Fallback Setup..." -ForegroundColor Cyan

# 1. Check if Ollama is already installed
$ollamaInstalled = $false
try {
    $ollamaVersion = ollama --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Ollama is already installed: $ollamaVersion" -ForegroundColor Green
        $ollamaInstalled = $true
    }
} catch {
    # Not installed
}

# 2. Download and Install Ollama if not present
if (-not $ollamaInstalled) {
    $installerPath = ".\OllamaSetup.exe"
    
    if (-not (Test-Path $installerPath)) {
        Write-Host "Downloading Ollama installer..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installerPath
    } else {
        Write-Host "Found pre-downloaded Ollama installer." -ForegroundColor Green
    }
    
    Write-Host "Installing Ollama silently... (This may require administrator privileges)" -ForegroundColor Yellow
    $process = Start-Process -FilePath $installerPath -ArgumentList "/SILENT" -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "Ollama installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Ollama installation may have failed or was cancelled. Exit Code: $($process.ExitCode)" -ForegroundColor Red
    }
    
    # Clean up installer
    Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue
    
    # Add Ollama to current session PATH so we can use it immediately
    $env:PATH += ";$env:LOCALAPPDATA\Programs\Ollama"
}

# 3. Pull the llama3.1 model
Write-Host "Pulling the llama3.1 model (8B parameters). This may take a few minutes depending on your internet connection..." -ForegroundColor Yellow
try {
    # Ensure Ollama server is running in the background if it was just installed
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5 # Give it a moment to start
    
    ollama pull llama3.1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Model llama3.1 successfully downloaded and ready for use!" -ForegroundColor Green
    } else {
        Write-Host "Failed to pull llama3.1. Please run 'ollama pull llama3.1' manually." -ForegroundColor Red
    }
} catch {
    Write-Host "Error pulling model: $_" -ForegroundColor Red
}

Write-Host "Setup Complete! Your SAHAKAR-SEVA project is now fully equipped with local AI fallback." -ForegroundColor Cyan
Write-Host "You can test it by running app.py without a GEMINI_API_KEY." -ForegroundColor Cyan
