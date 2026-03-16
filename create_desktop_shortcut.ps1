$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherPath = Join-Path $projectRoot "launch_app.bat"

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "launch_app.bat not found at $launcherPath"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutBase = -join @(
    [char]0x5B9E,
    [char]0x65F6,
    [char]0x7FFB,
    [char]0x8BD1,
    [char]0x4E00,
    [char]0x952E,
    [char]0x542F,
    [char]0x52A8
)
$shortcutPath = Join-Path $desktop ($shortcutBase + ".lnk")

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "One-click launcher for realtime translator desktop app"
$shortcut.Save()

Write-Output ('Shortcut created: {0}' -f $shortcutPath)
