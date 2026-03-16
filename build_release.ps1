param(
    [switch]$SkipTests,
    [switch]$OneFile,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $projectRoot

try {
    $python = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw ".venv\Scripts\python.exe not found. Please create venv and install dependencies first."
    }

    if (-not (Test-Path -LiteralPath "config.toml") -and (Test-Path -LiteralPath "config.example.toml")) {
        Copy-Item -LiteralPath "config.example.toml" -Destination "config.toml" -Force
        Write-Output "[INFO] config.toml created from config.example.toml"
    }

    if (-not $SkipTests) {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest failed. Build aborted."
        }
    }

    if (-not $NoClean) {
        if (Test-Path -LiteralPath "build") {
            Remove-Item -LiteralPath "build" -Recurse -Force
        }
        if (Test-Path -LiteralPath "dist") {
            Remove-Item -LiteralPath "dist" -Recurse -Force
        }
    }

    $args = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--name", "RealtimeTranslatorV1",
        "--windowed"
    )

    if (-not $NoClean) {
        $args += "--clean"
    }
    if ($OneFile) {
        $args += "--onefile"
    }

    if (Test-Path -LiteralPath "config.example.toml") {
        $args += @("--add-data", "config.example.toml;.")
    }
    if (Test-Path -LiteralPath "README.md") {
        $args += @("--add-data", "README.md;.")
    }
    if (Test-Path -LiteralPath "models") {
        $args += @("--add-data", "models;models")
    }

    $entry = "app\main.py"
    if (-not (Test-Path -LiteralPath $entry)) {
        throw "Entry file not found: $entry"
    }
    $args += $entry

    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $bundle = if ($OneFile) {
        Join-Path $projectRoot "dist\RealtimeTranslatorV1.exe"
    }
    else {
        Join-Path $projectRoot "dist\RealtimeTranslatorV1"
    }
    if (-not (Test-Path -LiteralPath $bundle)) {
        throw "Build output not found: $bundle"
    }

    if (-not $OneFile) {
        $outConfig = Join-Path $bundle "config.toml"
        if (-not (Test-Path -LiteralPath $outConfig) -and (Test-Path -LiteralPath "config.example.toml")) {
            Copy-Item -LiteralPath "config.example.toml" -Destination $outConfig -Force
        }
    }

    Write-Output "[OK] Build completed: $bundle"
}
finally {
    Pop-Location
}
