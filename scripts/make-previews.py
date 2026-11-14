"""Optional preview export; Python + Pillow. Not needed to build or run the app."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess
root=Path(__file__).resolve().parents[1]
exe=root/'build/vs2026/Release/mandelbulb.exe'
dest=root/'previews'
names=['glacier','jade','amber','amethyst','coral']
labels=['01  GLACIER','02  JADE','03  AMBER','04  AMETHYST','05  CORAL']
for i,name in enumerate(names,1):
    ppm=dest/(name+'.ppm')
    subprocess.run([str(exe),'--capture',str(ppm),'--quality','2','--palette',str(i)],check=True)
    with Image.open(ppm) as im: im.save(dest/(name+'.png'))
    ppm.unlink()
sheet=Image.new('RGB',(1600,860),'#0b111b')
d=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
d.text((35,22),'MANDELBULB  /  COLOR STUDIES',font=font,fill='#eef4fc')
d.text((35,60),'Power 8  |  OpenGL GPU ray marching  |  Five original palettes',font=small,fill='#95a9bf')
positions=[(15,105),(545,105),(1075,105),(280,478),(810,478)]
for name,label,(x,y) in zip(names,labels,positions):
    with Image.open(dest/(name+'.png')) as im:
        sheet.paste(im.resize((510,319),Image.Resampling.LANCZOS),(x,y))
    d.text((x+15,y+323),label,font=small,fill='#d3e3f3')
sheet.save(dest/'five-palettes.png')
print(dest/'five-palettes.png')
