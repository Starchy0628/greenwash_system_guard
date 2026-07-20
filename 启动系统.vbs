' ============================================================
'  谛观 GreenwashGuard - 一键启动（静默模式，无黑框）
'  双击此文件即可自动启动系统并打开浏览器
' ============================================================
Option Explicit

Dim WshShell, fso, strDir, pythonCmd, launcherPath
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcherPath = strDir & "\launcher.py"

' 检查Python是否安装
On Error Resume Next
WshShell.Run "python --version", 0, True
If Err.Number <> 0 Then
    MsgBox "未检测到 Python！" & vbCrLf & vbCrLf & _
           "请先安装 Python 3.10 或更高版本。" & vbCrLf & vbCrLf & _
           "下载地址：https://www.python.org/downloads/" & vbCrLf & _
           "安装时请务必勾选：Add Python to PATH", vbCritical, "环境缺失"
    WScript.Quit 1
End If
On Error GoTo 0

' 使用pythonw.exe静默启动launcher（无控制台窗口）
Dim pythonw
pythonw = "pythonw"
On Error Resume Next
' 尝试找到pythonw的完整路径
Dim exec
Set exec = WshShell.Exec("python -c ""import sys; print(sys.executable.replace('python.exe','pythonw.exe'))""")
If Err.Number = 0 Then
    Dim output
    output = exec.StdOut.ReadAll()
    If Trim(output) <> "" Then
        pythonw = Trim(output)
    End If
End If
On Error GoTo 0

' 后台启动launcher.py
WshShell.Run """" & pythonw & """ """ & launcherPath & """", 0, False

' 启动后显示一个简短的提示
WScript.Sleep 2000
MsgBox "系统正在启动中..." & vbCrLf & vbCrLf & _
       "请稍候，浏览器将自动打开。" & vbCrLf & _
       "如果未自动打开，请手动访问：http://localhost:8000" & vbCrLf & vbCrLf & _
       "双击「停止系统.vbs」可停止服务。", vbInformation, "GreenwashGuard"
