import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import subprocess,time,json,os
from PIL import Image

root=Path(r'D:\OpenGL-Dev\MandelbulbStudio')
out=Path(__file__).parent/'previews'
out.mkdir(exist_ok=True)
exe=root/'build/vs2026/Release/mandelbulb.exe'
env={k.upper():v for k,v in os.environ.items()}
def run(args):
    r=subprocess.run([str(exe),*args],env=env,capture_output=True,text=True,check=True)
    print(r.stdout,flush=True)
    return r.stdout
report=run(['--benchmark'])
for i in range(1,6):
    ppm=out/f'palette-{i}.ppm'
    run(['--capture',str(ppm),'--palette',str(i),'--quality','2'])
    with Image.open(ppm) as im: im.save(ppm.with_suffix('.png'))
for args in [['--scale','0'],['--scale','nan'],['--width','8192'],['--quality','3'],['--center-x','5'],['--verify','--benchmark'],['--palette','0']]:
    r=subprocess.run([str(exe),*args],env=env,capture_output=True)
    assert r.returncode==1,args

# Exercise the actual Win32 -> GLFW event path in a hidden interactive window.
user=c.WinDLL('user32',use_last_error=True)
kernel=c.WinDLL('kernel32',use_last_error=True)
user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
user.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
user.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
user.ShowWindow.argtypes=[w.HWND,c.c_int]
user.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
class Memory(c.Structure):
    _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(n,c.c_size_t) for n in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage']]
kernel.K32GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(Memory),w.DWORD]
callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
user.EnumWindows.argtypes=[callback,w.LPARAM]
si=subprocess.STARTUPINFO()
si.dwFlags|=subprocess.STARTF_USESHOWWINDOW
si.wShowWindow=0
p=subprocess.Popen([str(exe)],env=env,startupinfo=si,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
hwnd=None
def scan(h,_):
    global hwnd
    pid=w.DWORD()
    user.GetWindowThreadProcessId(h,c.byref(pid))
    if pid.value==p.pid:
        buf=c.create_unicode_buffer(1024)
        user.GetWindowTextW(h,buf,len(buf))
        if buf.value.startswith('Mandelbrot 2D'): hwnd=h
    return True
cb=callback(scan)
def title():
    buf=c.create_unicode_buffer(1024)
    user.GetWindowTextW(hwnd,buf,len(buf))
    return buf.value
def key(vk):
    lp=1|(user.MapVirtualKeyW(vk,0)<<16)
    if vk in (37,38,39,40): lp|=1<<24
    user.PostMessageW(hwnd,0x100,vk,lp)
    user.PostMessageW(hwnd,0x101,vk,lp|(1<<30)|(1<<31))
def memory():
    m=Memory();m.cb=c.sizeof(m)
    assert kernel.K32GetProcessMemoryInfo(w.HANDLE(p._handle),c.byref(m),m.cb)
    return dict(private_mib=round(m.PrivateUsage/1048576,2),working_mib=round(m.WorkingSetSize/1048576,2))
try:
    for _ in range(100):
        user.EnumWindows(cb,0)
        if hwnd and 'Zoom' in title(): break
        time.sleep(.1)
    assert hwnd and 'Zoom' in title(),'Interactive window missing'
    user.ShowWindow(hwnd,0)
    checks=[]
    for vk,expected in [(ord('5'),'Ember'),(ord('C'),'Classic'),(ord('Q'),'Fine'),(ord('F'),'60fps'),(32,'Spin'),(32,'Still'),(ord('G'),'Glow 0'),(38,'Glow 1.1'),(ord('R'),'Balanced')]:
        key(vk);time.sleep(.15)
        t=title();assert expected in t,(expected,t)
        checks.append(expected)
    samples=[]
    # Repeat quality changes and several sizes, returning to the same size per batch.
    for batch in range(5):
        for i in range(24):
            key(ord('Q'));key(ord('1')+i%5)
            dims=[(640,480),(1280,800),(1600,1000)][i%3]
            user.SetWindowPos(hwnd,None,0,0,*dims,0x0002|0x0004|0x0010)
            time.sleep(.06)
        key(ord('R'));user.SetWindowPos(hwnd,None,0,0,1280,800,0x0002|0x0004|0x0010)
        time.sleep(.3)
        samples.append(memory())
    key(27)
    p.wait(timeout=5)
    assert p.returncode==0
    data={'win32_key_checks':checks,'memory_batches':samples,'resizes_and_quality_changes':120,'exit_code':p.returncode}
    print(json.dumps(data,indent=2),flush=True)
    (out/'runtime-check.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    (out/'benchmark.txt').write_text(report,encoding='utf-8')
finally:
    if p.poll() is None:
        if hwnd:user.PostMessageW(hwnd,0x10,0,0)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate()
