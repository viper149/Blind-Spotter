' ==============================================================================
' Blind-Spotter Silent Launcher
' Launches Blind-Spotter invisibly in the background with zero flashing console window.
' An Ashnif Arnob Product (c) 2026
' ==============================================================================

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get current script directory
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Set current directory
WshShell.CurrentDirectory = ScriptDir

' Command to execute via pythonw (windowless python)
' Check virtual environment pythonw first, else system pythonw
VenvPythonw = ScriptDir & "\.venv\Scripts\pythonw.exe"

If FSO.FileExists(VenvPythonw) Then
    PythonwCmd = """" & VenvPythonw & """ """ & ScriptDir & "\main.py"""
Else
    PythonwCmd = "pythonw """ & ScriptDir & "\main.py"""
End If

' Run with window style 0 (completely hidden), do not wait
WshShell.Run PythonwCmd, 0, False

Set WshShell = Nothing
Set FSO = Nothing
