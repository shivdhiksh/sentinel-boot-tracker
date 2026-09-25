' ==============================================================================
' Silent Runner Wrapper for TUF Power Monitor
' Executes the target Python script with zero console window pop-ups.
' ==============================================================================
Dim objShell, objFSO, strScriptDir, strPythonScript, strAction, strPythonExe, strCmd

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the absolute directory where this VBS script resides
strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strPythonScript = """" & strScriptDir & "\power_monitor.py"""

' Read command-line argument (startup or shutdown)
strAction = "startup"
If WScript.Arguments.Count > 0 Then
    strAction = WScript.Arguments(0)
End If

' Priority: Exact Python 3.13 user installation -> Fallback: System PATH
strPythonExe = "C:\Users\koppu\AppData\Local\Programs\Python\Python313\pythonw.exe"
If Not objFSO.FileExists(strPythonExe) Then
    strPythonExe = "pythonw.exe"
End If

' Window style 0 = Hidden window, False = Do not block caller execution
strCmd = """" & strPythonExe & """ " & strPythonScript & " " & strAction

Sub LogMessage(msg)
    On Error Resume Next
    Dim strLogFile, objLogFile, dNow, strFormattedDate, strFormattedTime
    strLogFile = strScriptDir & "\error.log"
    dNow = Now
    strFormattedDate = Year(dNow) & "-" & Right("0" & Month(dNow), 2) & "-" & Right("0" & Day(dNow), 2)
    strFormattedTime = FormatDateTime(dNow, 3)
    Set objLogFile = objFSO.OpenTextFile(strLogFile, 8, True)
    If Err.Number = 0 Then
        objLogFile.WriteLine strFormattedDate & " " & strFormattedTime & " [INFO] " & msg
        objLogFile.Close
    End If
    On Error GoTo 0
End Sub

LogMessage "silent_runner.vbs launched (Action: " & strAction & ", Python: " & strPythonExe & ")"
objShell.Run strCmd, 0, False

