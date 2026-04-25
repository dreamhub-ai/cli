# Dreamhub CLI installer for Windows
# Usage: irm https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.ps1 | iex
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Repo = "https://github.com/dreamhub-ai/cli.git"
$MinPython = [version]"3.11"

function Write-Info  { param($Msg) Write-Host "==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param($Msg) Write-Host "==> $Msg" -ForegroundColor Green }
function Write-Warn  { param($Msg) Write-Host "==> $Msg" -ForegroundColor Yellow }
function Write-Fail  { param($Msg) Write-Host "Error: $Msg" -ForegroundColor Red; exit 1 }

function Find-Python {
    foreach ($candidate in @("python3", "python", "py")) {
        $bin = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($bin) {
            try {
                $ver = & $bin.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -and [version]$ver -ge $MinPython) {
                    return $bin.Source
                }
            } catch {
                Write-Verbose "Python probe failed for ${candidate}: $_"
            }
        }
    }
    # py -3 explicitly requests Python 3, whereas bare py may default to Python 2
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -and [version]$ver -ge $MinPython) {
                return "py -3"
            }
        } catch {
            Write-Verbose "py -3 probe failed: $_"
        }
    }
    return $null
}

Write-Host ""
Write-Host "  Dreamhub CLI Installer"
Write-Host "  ----------------------"
Write-Host ""

# Step 1: Ensure Python 3.11+
$pythonBin = Find-Python
if ($pythonBin) {
    if ($pythonBin -eq "py -3") {
        $pyVer = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    } else {
        $pyVer = & $pythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    }
    Write-Ok "Found Python $pyVer ($pythonBin)"
} else {
    Write-Info "Python $MinPython+ not found. Installing..."

    $winget = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Info "Installing Python via winget..."
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Fail "winget not available. Please install Python $MinPython+ from https://www.python.org/downloads/ and re-run."
    }

    $pythonBin = Find-Python
    if (-not $pythonBin) {
        Write-Warn "Python was installed but is not on PATH yet."
        Write-Host ""
        Write-Host "  Close and reopen this terminal, then re-run this installer."
        Write-Host ""
        exit 1
    }
    if ($pythonBin -eq "py -3") {
        $pyVer = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    } else {
        $pyVer = & $pythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    }
    Write-Ok "Installed Python $pyVer"
}

# Helper to invoke python consistently
function Invoke-Python {
    param([string[]]$PythonArgs)
    if ($pythonBin -eq "py -3") {
        & py -3 @PythonArgs
    } else {
        & $pythonBin @PythonArgs
    }
}

# Step 2: Ensure pipx
$pipx = Get-Command "pipx" -ErrorAction SilentlyContinue
if ($pipx) {
    Write-Ok "Found pipx"
} else {
    Write-Info "Installing pipx..."
    Invoke-Python @("-m", "pip", "install", "--user", "pipx")
    Invoke-Python @("-m", "pipx", "ensurepath")

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    $pipx = Get-Command "pipx" -ErrorAction SilentlyContinue
    if (-not $pipx) {
        # Try via python -m pipx as fallback
        Write-Warn "pipx not on PATH yet, using python -m pipx"
    } else {
        Write-Ok "Installed pipx"
    }
}

# Step 3: Install Dreamhub CLI
Write-Info "Installing Dreamhub CLI..."
$pipxAvailable = Get-Command "pipx" -ErrorAction SilentlyContinue
if ($pipxAvailable) {
    if ($pythonBin -eq "py -3") {
        # Find the actual python3 path for --python flag
        $actualPython = & py -3 -c "import sys; print(sys.executable)"
        pipx install "git+$Repo" --force --python $actualPython
    } else {
        pipx install "git+$Repo" --force --python $pythonBin
    }
} else {
    if ($pythonBin -eq "py -3") {
        $actualPython = & py -3 -c "import sys; print(sys.executable)"
        Invoke-Python @("-m", "pipx", "install", "git+$Repo", "--force", "--python", $actualPython)
    } else {
        Invoke-Python @("-m", "pipx", "install", "git+$Repo", "--force", "--python", $pythonBin)
    }
}

# Step 4: Refresh PATH and verify
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$dh = Get-Command "dh" -ErrorAction SilentlyContinue
if ($dh) {
    Write-Host ""
    Write-Ok "Dreamhub CLI installed successfully!"
    Write-Host ""
    Write-Host "  Get started:"
    Write-Host "    dh auth login       Log in to your account"
    Write-Host "    dh mcp install      Set up Claude Desktop integration"
    Write-Host "    dh --help           See all commands"
    Write-Host ""
} else {
    Write-Host ""
    Write-Warn "Installation completed but 'dh' is not on your PATH yet."
    Write-Host ""
    Write-Host "  Close and reopen this terminal, then run: dh --help"
    Write-Host ""
}
