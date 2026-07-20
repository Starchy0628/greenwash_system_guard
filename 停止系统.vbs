' ============================================================
'  GreenwashGuard - 停止系统
'  双击此文件停止后台运行的服务
' ============================================================
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
pidFile = strDir & "\.server.pid"

If fso.FileExists(pidFile) Then
    Set f = fso.OpenTextFile(pidFile, 1)
    pid = f.ReadLine()
    f.Close
    
    On Error Resume Next
    WshShell.Run "taskkill /F /PID " & pid, 0, True
    If Err.Number = 0 Then
        MsgBox "系统已停止！", vbInformation, "GreenwashGuard"
    Else
        MsgBox "停止失败，请手动在任务管理器中结束python进程", vbExclamation, "提示"
    End If
    On Error GoTo 0
    
    fso.DeleteFile pidFile
Else
    ' 通过端口查找并终止
    WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %a", 0, True
    MsgBox "已尝试停止端口8000上的服务", vbInformation, "GreenwashGuard"
End If
