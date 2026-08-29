$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Copyied.lnk"
$appPath = Join-Path $projectDir "dist\Copyied.exe"
$launcherPath = Join-Path $projectDir "launch.vbs"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = if (Test-Path $appPath) { $appPath } else { "$env:WINDIR\System32\wscript.exe" }
$shortcut.Arguments = if (Test-Path $appPath) { "" } else { "`"$launcherPath`"" }
$shortcut.WorkingDirectory = $projectDir
$shortcut.WindowStyle = 1
$shortcut.Description = "Copyied clipboard history widget"
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
