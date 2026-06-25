Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ws.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)

Dim pw
pw = ""

Dim paths
paths = Array( _
    ws.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Miniconda3\pythonw.exe", _
    ws.ExpandEnvironmentStrings("%USERPROFILE%") & "\miniconda3\pythonw.exe", _
    ws.ExpandEnvironmentStrings("%USERPROFILE%") & "\anaconda3\pythonw.exe", _
    "pythonw" _
)

Dim i
For i = 0 To UBound(paths)
    If fso.FileExists(paths(i)) Then
        pw = paths(i)
        Exit For
    End If
Next

ws.Run """" & pw & """ app.py", 0, False
