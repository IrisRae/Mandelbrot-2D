from pathlib import Path
import sys,hashlib,zipfile,json
sys.path.insert(0,r'C:\Users\Lenovo\AppData\Local\Temp\mandelbrot_docx_tools')
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root=Path(r'D:\OpenGL-Dev\MandelbulbStudio')
out=Path(r'C:\Users\Lenovo\Desktop\二维曼德博分形核心代码.docx')
if out.exists():
    out=out.with_stem(out.stem+'_20261009')
files={n:(root/n).read_text(encoding='utf-8-sig') for n in ['src/main.cpp','src/shaders/scene.frag','src/shaders/scene.vert']}
doc=Document()
sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(1.8);sec.bottom_margin=Cm(1.7)
sec.left_margin=Cm(1.7);sec.right_margin=Cm(1.7)
sec.header_distance=Cm(.8);sec.footer_distance=Cm(.8)
def font(style,name,size,east='微软雅黑'):
    style.font.name=name;style.font.size=Pt(size)
    style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),east)
font(doc.styles['Normal'],'Calibri',10)
doc.styles['Normal'].paragraph_format.space_after=Pt(6)
doc.styles['Normal'].paragraph_format.line_spacing=1.15
for n,size in [('Title',27),('Subtitle',12),('Heading 1',17),('Heading 2',12)]:
    font(doc.styles[n],'Calibri',size)
    doc.styles[n].font.color.rgb=RGBColor.from_string('153A59')
code=doc.styles.add_style('Source Code',WD_STYLE_TYPE.PARAGRAPH)
font(code,'Consolas',8,'等线')
code.paragraph_format.line_spacing=Pt(10)
code.paragraph_format.space_after=Pt(0)
code.paragraph_format.space_before=Pt(0)
code.paragraph_format.keep_together=True
code.paragraph_format.widow_control=False
code.paragraph_format.left_indent=Cm(.15)
shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F2F5F8')
code.element.get_or_add_pPr().append(shade)
meta=doc.styles.add_style('Source Location',WD_STYLE_TYPE.PARAGRAPH)
font(meta,'Calibri',8)
meta.font.color.rgb=RGBColor.from_string('586575')
meta.paragraph_format.keep_with_next=True
header=sec.header.paragraphs[0]
header.text='OPENGL  /  MANDELBROT 2D                                    核心代码参考'
font(header.style,'Calibri',8)
footer=sec.footer.paragraphs[0];footer.alignment=2
footer.add_run('第 ')
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
footer.add_run(' 页')
doc.core_properties.title='二维曼德博分形核心代码'
doc.core_properties.subject='D:\\OpenGL-Dev 当前二维 Mandelbrot 实现'
doc.core_properties.author='OpenGL-Dev'

blocks=[]
def block(name,text,start=1):
    text=text.rstrip('\n')
    count=len(text.splitlines())
    doc.add_paragraph(f'{name}  ·  原文件第 {start}—{start+count-1} 行',style='Source Location')
    lines=[]
    for line in text.split('\n'):
        doc.add_paragraph(line,style='Source Code')
        lines.append(line)
    blocks.append((name,start,lines))
    doc.add_paragraph('')
def extract(name,a,b):
    src=files[name];begin=src.index(a);end=src.index(b,begin)
    text=src[begin:end].rstrip('\n')
    block(name,text,src[:begin].count('\n')+1)
def section(title,description):
    doc.add_heading(title,level=1)
    doc.add_paragraph(description)
def table(headers,rows):
    t=doc.add_table(rows=1,cols=len(headers));t.style='Light Shading Accent 1'
    for c,v in zip(t.rows[0].cells,headers):c.text=v
    for row in rows:
        for c,v in zip(t.add_row().cells,row):c.text=str(v)

doc.add_paragraph('二维曼德博分形',style='Title')
doc.add_paragraph('核心代码与实现说明',style='Subtitle')
doc.add_paragraph('源码快照：2026 年 10 月 9 日\n工程：D:\\OpenGL-Dev\\MandelbulbStudio\n技术：C++17 / OpenGL 3.3 / GLSL 330')
doc.add_paragraph('本文直接摘录当前工程源码：片元与顶点着色器完整收录，C++ 部分按核心功能摘录。代码为可选择、可复制的文本；保留源码内容，长行在 Word 中自动折行。C++ 摘录需结合原工程的头文件、辅助函数及 GLFW/GLAD 依赖使用。')
preview=root/'previews/palette-1.png'
if preview.exists():
    doc.add_picture(str(preview),width=Cm(15.8))
    doc.add_paragraph('工程保存的实际渲染预览：经典蓝金配色。',style='Caption')
doc.add_heading('阅读顺序',level=2)
doc.add_paragraph('1. 数学原理与数据流\n2. 完整 GPU 着色器\n3. 二维视图与迭代预算\n4. 渲染资源与参数上传\n5. 原有按键和鼠标交互\n6. 精度选择与低负载渲染循环\n7. CPU 参考算法与内存边界')
doc.add_page_break()

section('1  数学原理与数据流','对复平面上每个采样点 c，从 z₀ = 0 开始计算 zₙ₊₁ = zₙ² + c。当前实现以 |z|² > 65536 为逃逸条件，使用平滑逃逸次数着色；迭代预算内未逃逸的点显示为黑色。有限迭代是对集合归属的近似，边界附近仍存在数值误差。')
doc.add_paragraph('像素坐标 → 按画面高度归一化 → 二维旋转 → 缩放并加上复平面中心 → Mandelbrot 迭代 → 平滑色带与辉光 → RGBA8 纹理 → 放大至窗口。')
table(['变量 / 参数','作用'],[
('centerX / centerY','复平面视图中心，CPU 使用 double'),
('scale','可见平面的半高；默认 1.3，越小放大越深'),
('angle','二维平面旋转角，单位为弧度'),
('uCenterHi / uCenterLo、uScale','将 CPU double 分拆为高、低 float 传入 GPU'),
('uPrecise','scale < 0.002 时选择原生 fp64 迭代'),
('uIterations / uSamples','有限迭代预算；节能/均衡 1 次采样，精细 4 次'),
('uClassify','验证模式输出黑白归属掩码，不执行最终配色输出')])

section('2  GPU 分形计算与着色','以下两个着色器均为完整原文件。主片元着色器包括心形区/二周期圆形区快速判断、普通与双精度迭代、五套配色、四点采样及色调映射。')
doc.add_heading('2.1  全屏三角形顶点着色器',level=2)
block('src/shaders/scene.vert',files['src/shaders/scene.vert'])
doc.add_heading('2.2  完整片元着色器',level=2)
block('src/shaders/scene.frag',files['src/shaders/scene.frag'])

section('3  二维视图与迭代预算','AppState 保存视图与操作状态。每放大约一倍，增加 40 次迭代，并按画质限制最大次数。左键平移会使用当前旋转角将屏幕位移转换到复平面；右键仅在二维平面内旋转。')
extract('src/main.cpp','constexpr double PI2','struct Renderer')

section('4  渲染资源与参数上传','Renderer 只维护一张 RGBA8 离屏纹理；内部尺寸改变时重新分配其存储，普通重绘复用原纹理。中心和缩放拆分为高、低 float，深度缩放时在着色器中重组为 double。析构函数释放 OpenGL 资源。')
extract('src/main.cpp','struct Renderer','struct Image')

section('5  原有按键和鼠标交互','以下原始回调保留配色、画质、辉光、自动旋转、帧率、复位和退出功能。滚轮与中键拖动调用同一缩放函数；普通按键仅接受首次按下，上下方向键支持长按重复。')
table(['输入','功能'],[('1—5 / C','选择 / 循环配色'),('Q / F','切换画质 / 30、60 FPS'),('G / ↑↓','辉光开关 / 强度'),('Space / R / Esc','自动旋转 / 重置 / 退出'),('左键 / 右键拖动','平移 / 平面旋转'),('滚轮 / 中键上下拖动','缩放')])
extract('src/main.cpp','static void keyCallback','static void title')

section('6  精度选择与低负载渲染循环','下列片段位于 runApplication 内部。创建上下文并加载 OpenGL 后查询 fp64 支持；不支持时将最小半高限制为 0.002。普通交互在静止或最小化时等待事件，失焦时停止自动旋转，GPU 计时使用异步查询。连续 12 次计时超过 28 ms 时降低一档画质。')
doc.add_heading('6.1  精度能力与初始状态',level=2)
extract('src/main.cpp','        supportsDouble=glfwExtensionSupported','        if(options.benchmark)')
doc.add_heading('6.2  事件回调与主循环',level=2)
src=files['src/main.cpp'];a=src.index('            glfwSetWindowUserPointer(w,&s);');b=src.index('            glDeleteQueries(1,&query);',a)+len('            glDeleteQueries(1,&query);')
block('src/main.cpp',src[a:b],src[:a].count('\n')+1)

section('7  CPU 参考算法与内存边界','CPU 双精度参考算法使用相同逃逸阈值与迭代上限，可独立对照 GPU 归属掩码。截图与验证才执行像素回读，普通交互不保留 CPU 整帧图像。')
doc.add_heading('7.1  CPU 归属参考',level=2)
extract('src/main.cpp','static bool cpuInside','static void verifyMask')
doc.add_heading('7.2  截图回读容量限制',level=2)
extract('src/main.cpp','static Image readFrame','static float brightness')
table(['画质','最长边','基础 / 最大迭代','采样'],[('节能','640 px','192 / 768','1'),('均衡','960 px','320 / 1152','1'),('精细','1440 px','512 / 1536','4')])
doc.add_paragraph('默认 1280×800 窗口在均衡画质下使用 960×600×4 字节纹理，约 2.20 MiB。单张纹理理论上限为 1440²×4 字节，约 7.91 MiB。截图 RGBA 缓冲上限为 3840×2160×4 字节，约 31.64 MiB。以上不包含程序、驱动和窗口交换缓冲占用。')
doc.add_heading('源码对照与运行',level=2)
doc.add_paragraph('Visual Studio 解决方案：\nD:\\OpenGL-Dev\\MandelbulbStudio\\build\\vs2026\\MandelbulbStudio.slnx\n选择 mandelbulb 启动项目，Release / x64，按 F5。\n命令行验证：build\\vs2026\\Release\\mandelbulb.exe --verify')
doc.add_paragraph('为兼容原工程，目录与可执行文件保留 Mandelbulb 命名；本文所列实际算法为二维 Mandelbrot。')
for name in files:
    sha=hashlib.sha256((root/name).read_bytes()).hexdigest()
    doc.add_paragraph(name+'\nSHA-256: '+sha,style='Source Location')
doc.save(out)

# Verify that every source line survived DOCX serialization exactly, in order.
loaded=Document(out)
actual=[p.text for p in loaded.paragraphs if p.style.name=='Source Code']
expected=[line for _,_,lines in blocks for line in lines]
assert actual==expected,'Source text changed during serialization'
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert 'word/document.xml' in z.namelist()
report={'path':str(out),'bytes':out.stat().st_size,'source_blocks':len(blocks),'source_lines':len(actual),'exact_source_roundtrip':True}
(Path(__file__).parent/'docx-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
