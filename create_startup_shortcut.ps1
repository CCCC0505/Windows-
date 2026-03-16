param(
    [switch]$Disable
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherPath = Join-Path $projectRoot "launch_app.bat"
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "launch_app.bat not found at $launcherPath"
}

$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "Realtime Translator V1.lnk"

if ($Disable) {
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
        Write-Output ("Startup shortcut removed: {0}" -f $shortcutPath)
    }
    else {
        Write-Output ("Startup shortcut not found: {0}" -f $shortcutPath)
    }
    exit 0
}

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Auto-start launcher for realtime translator desktop app"
$shortcut.Save()

Write-Output ("Startup shortcut created: {0}" -f $shortcutPath)
