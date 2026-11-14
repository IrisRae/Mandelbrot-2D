"""Windows message-loop smoke test. Launches only its own application window."""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w
import subprocess,time
root=Path(__file__).resolve().parents[1]
u=c.WinDLL('user32',use_last_error=True)
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.IsWindowVisible.argtypes=[w.HWND]
callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
proc=subprocess.Popen([str(root/'build/vs2026/Release/mandelbulb.exe')],creationflags=subprocess.CREATE_NO_WINDOW)
hwnd=None
try:
    for _ in range(100):
        windows=[]
        @callback
        def enum(handle,_):
            pid=w.DWORD();u.GetWindowThreadProcessId(handle,c.byref(pid))
            if pid.value==proc.pid and u.IsWindowVisible(handle): windows.append(handle)
            return True
        u.EnumWindows(enum,0)
        if windows: hwnd=windows[0];break
        time.sleep(.1)
    assert hwnd,'No application window'
    def title():
        text=c.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,text,1024);return text.value
    def key(vk,scan):
        u.PostMessageW(hwnd,0x100,vk,1|(scan<<16))
        u.PostMessageW(hwnd,0x101,vk,1|(scan<<16)|(3<<30))
    def expect(part):
        for _ in range(50):
            if part in title():return
            time.sleep(.1)
        raise AssertionError((part,title()))
    expect('Glacier')
    for vk,scan,label in [(0x32,3,'Jade'),(0x33,4,'Amber'),(0x34,5,'Amethyst'),(0x35,6,'Coral'),(0x43,46,'Glacier'),(0x51,16,'Fine'),(0x51,16,'Eco'),(0x52,19,'Balanced')]:
        key(vk,scan);expect(label)
    print('PASS: actual GLFW window, numeric/letter palette switching, quality cycling, reset.')
    print('Window:',title())
finally:
    if hwnd: u.PostMessageW(hwnd,0x10,0,0)
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired: proc.terminate();proc.wait()
