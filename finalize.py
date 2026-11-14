from pathlib import Path
import shutil,json

stage=Path(__file__).parent
project=Path(r'D:\OpenGL-Dev')
studio=project/'MandelbulbStudio'
backup=project/'backups/mandelbrot-partial-20261009'
for name in ['README.md','run-demo.cmd']:
    shutil.copy2(project/name,backup/('root-'+name))
shutil.copy2(project/'README.md',project/'README-gradient.md')
shutil.copy2(project/'run-demo.cmd',project/'run-gradient.cmd')
(project/'run-demo.cmd').write_text('@echo off\ncall "%~dp0MandelbulbStudio\\run.cmd"\n',encoding='ascii')
(project/'open-visual-studio.cmd').write_text('@echo off\ncall "%~dp0MandelbulbStudio\\open-visual-studio.cmd"\n',encoding='ascii')
(project/'README.md').write_text('''# OpenGL · 二维彩色曼德博分形

当前演示位于 `MandelbulbStudio`，已经从三维分形改为二维复平面的彩色 Mandelbrot 集。

- 双击 `open-visual-studio.cmd` 用 Visual Studio 2026 打开分形工程，选择 `Release / x64`，按 F5。
- 双击 `run-demo.cmd` 直接运行二维分形。
- 完整操作、内存限制和构建命令见 [二维分形说明](MandelbulbStudio/README.md)。
- 左键平移、右键平面旋转、中键/滚轮缩放；1—5/C 配色、Q 画质、G 辉光、↑↓ 强度、Space 自动旋转、F 帧率、R 重置、Esc 退出。

保留原渐变矩形源码和根目录 CMake 工程，可通过 `run-gradient.cmd` 运行；原根目录 VS Code 调试配置仍用于渐变矩形。旧说明见 `README-gradient.md`。

本次修改前的文件保存在 `backups/mandelbrot-partial-20261009`，历史三维备份也保留于 `backups`。
''',encoding='utf-8')
runtime=json.loads((stage/'previews/runtime-check.json').read_text())
report='''Mandelbrot 2D verification — 2026-10-09
Target: D:\\OpenGL-Dev\\MandelbulbStudio
Visual Studio 2026 / MSVC 19.51.36260.0 / x64 / C++17
NVIDIA RTX 5060 Laptop GPU / OpenGL 3.3.0 NVIDIA 592.01

Debug and Release: built successfully without reported compiler warnings.
Both --verify runs PASS with the final shader.
CPU double oracle vs GPU membership samples:
  scale 1.3: 7/6279 differences; rotated: 1/6279.
  scale 1e-7 with native fp64: 1/1564; scale .001: 0/1564.
Finite iteration budget and chaotic boundary arithmetic explain limited differences;
this is a sampled numerical validation, not proof of exact set membership.
GPU tests: 5 palettes, black interior/coloured exterior, repeatability,
plane rotation, pan, zoom and clamps, glow, all 3 quality settings,
portrait/odd/1600x1000 resizing, texture size budget, original key callbacks.
Actual Win32 -> GLFW input tests: 5, C, Q, F, Space on/off, G, Up, R, Esc PASS.
Invalid CLI inputs: zero/NaN scale, excessive width, invalid quality/center/palette,
and conflicting operation modes rejected with exit code 1.
Five 1280x800 PNG captures saved in previews; default visually inspected.

Memory: one reused RGBA8 texture; default 960x600 = 2.20 MiB,
maximum theoretical texture 1440x1440 = 7.91 MiB.
120 window-size/quality changes, five process-memory samples:
'''
report+=json.dumps(runtime['memory_batches'],indent=2)+'\n'
report+='''No sustained growth observed in this short run; driver allocations are included
in process private memory and are separate from the small render texture budget.
This is not a long-duration leak certification or a total VRAM measurement.

Benchmark (default 1280x800 view; short samples, not worst-case deep zoom):
'''+(stage/'previews/benchmark.txt').read_text()
(studio/'verification.txt').write_text(report,encoding='utf-8')
print('Updated documentation, launchers, previews and verification report.')
