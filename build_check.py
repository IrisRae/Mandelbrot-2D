import os, subprocess
from pathlib import Path
root=Path(__file__).parent
env={}
for key,value in os.environ.items():
    env[key.upper()]=value
cmake=r'C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
def run(args):
    subprocess.run(args,cwd=root,env=env,check=True)
run([cmake,'--fresh','--preset','vs2026'])
for config in ['release','debug']:
    run([cmake,'--build','--preset',config,'--parallel','4'])
    run([str(root/'build/vs2026'/config.capitalize()/'mandelbulb.exe'),'--verify'])
