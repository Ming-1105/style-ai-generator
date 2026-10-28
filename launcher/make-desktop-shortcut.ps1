# Makes a "CopyCat" shortcut with an icon on your desktop. Run it once (double-click make-desktop-shortcut.bat).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')

$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\CopyCat.lnk")
$shortcut.TargetPath = "$here\start-copycat.bat"
$shortcut.WorkingDirectory = $here
$shortcut.IconLocation = "$here\copycat.ico"
$shortcut.WindowStyle = 7   # minimised, so only the browser shows
$shortcut.Description = "Start CopyCat and open it in the browser"
$shortcut.Save()

Write-Host "Done. A CopyCat shortcut is now on your desktop: $desktop\CopyCat.lnk"
