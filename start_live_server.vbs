' start_live_server.vbs — mở BẢNG ĐIỀU KHIỂN The Cheopard Forex.
'
' HAI LỖI TỆP NÀY TỪNG GÂY RA — và cách chúng được vá
' ====================================================
' 1. "NHẤN VÀO MÀ KHÔNG THẤY GÌ": bản đầu trỏ vào `live_server.py` của hệ XAUUSD,
'    tệp đã bị xoá khi chuyển sang Forex. `pythonw.exe` khởi động, không tìm thấy
'    module, tắt ngay — và vì `pythonw` không có console nên không có gì hiện ra,
'    cũng không có thông báo lỗi nào. Nay VBS KIỂM TRA tệp trước khi chạy, còn
'    `live_server.py` bắt mọi lỗi khởi động và hiện thành hộp thoại.
'
' 2. "CHAY BAN CU": ban 14/08 giu khoa chong chay nhieu ban bang cach DUA CUA SO
'    CU LEN TRUOC roi tu thoat. Hau qua: sau moi lan sua code, nhan VBS chi
'    focus lai tien trinh cu dang chay ma cu. Nay `live_server.py` DUNG ban cu
'    roi nap ban moi (`--keep` giu hanh vi cu).
'
' 3. "NHAP NHAY MAY CHUC CUA SO DEN": buoc dung ban cu goi `tasklist` moi 0,3
'    giay, va `pythonw.exe` khong co console nen Windows cap cho moi lan mot
'    cua so moi. Nay moi lenh he thong chay voi CREATE_NO_WINDOW — xem
'    `live_server._run_hidden`.

Option Explicit

Dim WshShell, fso, currentDir, pywPath, pyPath, guiPath, args, i

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

pywPath = fso.BuildPath(currentDir, ".venv311\Scripts\pythonw.exe")
pyPath = fso.BuildPath(currentDir, ".venv311\Scripts\python.exe")
guiPath = fso.BuildPath(currentDir, "src\python\live_server.py")

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & WScript.Arguments(i)
Next

If Not fso.FileExists(pyPath) Then
    MsgBox "Khong tim thay moi truong Python 3.11 tai:" & vbCrLf & vbCrLf & _
           pyPath & vbCrLf & vbCrLf & _
           "Tao truoc bang:" & vbCrLf & _
           "    py -3.11 -m venv .venv311" & vbCrLf & _
           "    .venv311\Scripts\python.exe -m pip install -r requirements.txt", _
           vbCritical, "The Cheopard Forex"
    WScript.Quit 1
End If

If Not fso.FileExists(guiPath) Then
    MsgBox "Khong tim thay bang dieu khien tai:" & vbCrLf & vbCrLf & guiPath, _
           vbCritical, "The Cheopard Forex"
    WScript.Quit 1
End If

' pythonw.exe: chay GUI ma KHONG mo cua so console den kem theo.
' Tham so 1 = cua so binh thuong, de cua so customtkinter hien dung.
If fso.FileExists(pywPath) Then
    WshShell.Run Chr(34) & pywPath & Chr(34) & " -m src.python.live_server" & args, 1, False
Else
    WshShell.Run Chr(34) & pyPath & Chr(34) & " -m src.python.live_server" & args, 1, False
End If

Set WshShell = Nothing
Set fso = Nothing
