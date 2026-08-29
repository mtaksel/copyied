Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
launcher = scriptDir & "\launch.pyw"

shell.CurrentDirectory = scriptDir

If fso.FileExists(pythonw) Then
    command = """" & pythonw & """ """ & launcher & """"
Else
    command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & scriptDir & "\run.ps1"""
End If

shell.Run command, 0, False
