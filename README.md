# Mandelbrot 2D · 二维彩色曼德博分形

已将原三维 Mandelbulb 改为复平面上的 Mandelbrot 集：从 `z=0` 开始迭代 `z=z²+c`，外部按平滑逃逸次数着色，迭代预算内未逃逸的区域为黑色。五种配色，无透视、立体光照或三维网格。

为兼容已有 Visual Studio 解决方案与启动脚本，目录、项目及程序文件仍叫 `MandelbulbStudio` / `mandelbulb.exe`；窗口显示 `Mandelbrot 2D`。

## Visual Studio 打开与运行

双击 `open-visual-studio.cmd`，或者打开 `build/vs2026/MandelbulbStudio.slnx`。选择 `Release / x64`，启动项目 `mandelbulb`，按 **F5**；Debug / x64 也已验证。单独运行可双击 `run.cmd`。

修改源码或着色器后运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Configuration Release -Verify
```

所有构建依赖均在 `vendor`，无须联网。着色器构建时复制到可执行文件旁的 `shaders` 目录；分发时保留此目录。

## 原有操作

| 输入 | 二维版本行为 |
| --- | --- |
| 左键拖动 | 平移复平面，旋转后仍沿屏幕拖动方向移动 |
| 右键拖动 | 在二维平面内旋转 |
| 滚轮 / 中键上下拖动 | 缩放，以当前视图中心为基准 |
| `1`—`5` | 经典蓝金、冰川、翡翠、紫晶、余烬 |
| `C` | 循环五套配色 |
| `Q` | 均衡 → 精细 → 节能 |
| `G` | 开关辉光，保留设置的强度 |
| `↑` / `↓` | 辉光强度增减，范围 0—2 |
| `Space` | 开关平面自动旋转，默认关闭 |
| `F` | 切换 30 / 60 FPS 上限 |
| `R` | 重置中心、缩放、旋转、配色、画质、辉光和帧率 |
| `Esc` | 退出 |

## 内存与负载

| 画质 | 内部最长边上限 | 基础 / 最大迭代 | 每像素采样 |
| --- | --- | --- | --- |
| 节能 | 640 px | 192 / 768 | 1 |
| 均衡（默认） | 960 px | 320 / 1152 | 1 |
| 精细 | 1440 px | 512 / 1536 | 4 |

- 只使用一个 RGBA8 离屏纹理，尺寸改变时复用对象；无深度纹理、MSAA、图像历史缓存或分形网格。
- 默认 1280×800 窗口的均衡画质纹理为 960×600，约 **2.20 MiB**；所有画质的纹理理论上限 **7.91 MiB**。这些数字不含驱动、程序和窗口交换缓冲。
- 普通交互不回读图像、不分配整帧 CPU 像素缓冲。截图最大 3840×2160，RGBA 回读最多 **31.64 MiB**；验证仅保留一张基准和一张临时图。
- 静止时等待事件，最小化时停绘，失焦时停止自动旋转；默认最高 30 FPS。连续 12 次 GPU 采样超过 28 ms 自动降低画质，可按 Q 再切换。
- 缩放时增加迭代但始终有上限。深度缩放需要 `GL_ARB_gpu_shader_fp64`，使用原生双精度；支持时半高最小 `1e-7`（相对初始约 1300 万倍），不支持时限制为 `0.002`（650 倍）。中心范围为 ±4，半高最大 4。有限迭代不能保证边界附近每点的数学归属，也不提供无限精度缩放。

## 验证与截图

```powershell
.\build\vs2026\Release\mandelbulb.exe --verify
.\build\vs2026\Release\mandelbulb.exe --benchmark
.\build\vs2026\Release\mandelbulb.exe --capture preview.ppm --quality 2 --palette 1
.\build\vs2026\Release\mandelbulb.exe --capture detail.ppm --center-x -0.743643887037151 --center-y 0.13182590420533 --scale 0.001
```

`--verify` 检查真实 GPU 图像、独立 CPU 双精度归属参考、深度缩放、五套配色、重绘一致性、平移/旋转/缩放、辉光、所有原按键、竖屏/奇数尺寸和纹理上限。边界数值误差允许不超过 1% 抽样差异。

`--angle` 指定平面角度（弧度）；旧参数 `--yaw` / `--pitch` 均转为平面旋转角，`--distance` 转为半高 `distance/2.45`（结果须在半高范围内），`--time` 转为自动旋转经过的秒数。`--help` 显示全部参数。

`previews` 保存实际 GPU 渲染的 PNG、基准耗时及运行时内存检查。详细本机结果见 `verification.txt`。

## 文件与许可

`src/main.cpp` 负责交互、二维视图、资源限制和验证；`src/shaders/scene.frag` 负责 Mandelbrot 迭代与着色。GLFW 3.4、GLAD 的原许可证保留于 `vendor`。

本次修改前的未完成版本备份于上级 `backups/mandelbrot-partial-20261009`；之前的三维备份仍在 `backups/mandelbulb-3d-20261008-231013`。
