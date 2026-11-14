from pathlib import Path

root = Path(__file__).parent
p = root / 'src/main.cpp'
s = p.read_text(encoding='utf-8-sig')
s = s.replace('float yaw = 0.55f, pitch = 0.24f, distance = 3.7f;', 'double centerX = -0.6, centerY = 0.0, scale = 1.3;\n    double yaw = 0.0, pitch = 0.0;')
s = s.replace('const float result = std::stof(input, &count);', 'const double result = std::stod(input, &count);')
s = s.replace('const float result = number();', 'const double result = number();')
s = s.replace('options.distance = number();', 'options.scale = number() / 2.45;\n        else if (arg == "--scale") options.scale = number();\n        else if (arg == "--center-x") options.centerX = number();\n        else if (arg == "--center-y") options.centerY = number();\n        else if (arg == "--angle") options.yaw = number();')
s = s.replace('options.time = number();', 'options.time = static_cast<float>(number());').replace('options.glow = number();', 'options.glow = static_cast<float>(number());')
s = s.replace('if(options.distance < 1.8f || options.distance > 12.0f || std::abs(options.pitch)>1.45f) throw std::runtime_error("Camera out of range.");', '''if(options.scale < 1e-7 || options.scale > 4.0 || std::abs(options.centerX)>4.0 || std::abs(options.centerY)>4.0)
        throw std::runtime_error("Plane out of range: scale 1e-7..4, center -4..4.");
    options.yaw=std::remainder(options.yaw,6.283185307179586);
    options.pitch=std::remainder(options.pitch,6.283185307179586);''')
s = s.replace('if (options.verify && !options.capture.empty())\n        throw std::runtime_error("Use --verify and --capture separately.");', 'if (int(options.verify)+int(options.benchmark)+int(!options.capture.empty())>1)\n        throw std::runtime_error("Use --verify, --benchmark and --capture separately.");')
a=s.index('struct Vec3'); b=s.index('struct Renderer',a)
s=s[:a]+'''constexpr double PI2 = 6.283185307179586;
constexpr double MIN_SCALE = 1e-7, MAX_SCALE = 4.0, DEFAULT_SCALE = 1.3;
struct AppState {
    int palette=0,quality=1,fpsCap=30;
    double centerX=-0.6,centerY=0.0,scale=DEFAULT_SCALE,angle=0.0;
    float glow=1.0f;
    bool glowEnabled=true,dirty=true,autoRotate=false,drag=false;
    int button=-1;
    double lastX=0,lastY=0;
};
static int iterationLimit(const AppState& s) {
    const int base[]={192,320,512};
    const int caps[]={768,1152,1536};
    return std::min(caps[s.quality],base[s.quality]+int(std::max(0.0,std::log2(DEFAULT_SCALE/s.scale)))*40);
}
static void zoom(AppState& s,double amount) {
    s.scale=std::clamp(s.scale*std::exp(std::clamp(amount,-32.0,32.0)),MIN_SCALE,MAX_SCALE);
    s.dirty=true;
}
static void moveCamera(AppState& s,double dx,double dy,int height) {
    if(s.button==GLFW_MOUSE_BUTTON_RIGHT) {
        s.angle=std::remainder(s.angle+(dx+dy)*.006,PI2);
    } else if(s.button==GLFW_MOUSE_BUTTON_MIDDLE) zoom(s,dy*.009);
    else {
        const double k=2.0*s.scale/std::max(height,1);
        const double ca=std::cos(s.angle),sa=std::sin(s.angle);
        s.centerX=std::clamp(s.centerX+(-dx*ca-dy*sa)*k,-4.0,4.0);
        s.centerY=std::clamp(s.centerY+(-dx*sa+dy*ca)*k,-4.0,4.0);
    }
    s.dirty=true;
}
''' + s[b:]
s=s.replace('int rw=0,rh=0;', '''int rw=0,rh=0;
    GLint resolution=-1,centerHi=-1,centerLo=-1,scale=-1,angle=-1,iterations=-1;
    GLint glow=-1,palette=-1,samples=-1,precise=-1,classify=-1;''')
needle='        glGenVertexArrays(1,&vao);'
idx=s.index(needle)
s=s[:idx]+'''        auto uniform=[&](const char* name) {
            const GLint location=glGetUniformLocation(program,name);
            if(location<0) throw std::runtime_error(std::string("Missing shader uniform: ")+name);
            return location;
        };
        resolution=uniform("uResolution"); centerHi=uniform("uCenterHi"); centerLo=uniform("uCenterLo");
        scale=uniform("uScale"); angle=uniform("uAngle"); iterations=uniform("uIterations");
        glow=uniform("uGlow"); palette=uniform("uPalette"); samples=uniform("uSamples");
        precise=uniform("uPrecise"); classify=uniform("uClassify");
''' + s[idx:]
s=s.replace('void draw(int w,int h,const AppState& s) {','void draw(int w,int h,const AppState& s,bool mask=false) {\n        if(w<=0 || h<=0) throw std::runtime_error("Empty render target.");')
s=s.replace('double scale=std::min(1.0,double(caps[s.quality])/std::max(w,h));\n        int nw=std::max(1,int(w*scale)),nh=std::max(1,int(h*scale));', 'double ratio=std::min(1.0,double(caps[s.quality])/std::max(w,h));\n        int nw=std::max(1,int(w*ratio)),nh=std::max(1,int(h*ratio));')
a=s.index('        glUniform2f(glGetUniformLocation(program,"uResolution")');b=s.index('        glDrawArrays',a)
s=s[:a]+'''        glUniform2f(resolution,float(rw),float(rh));
        const float hx=float(s.centerX),hy=float(s.centerY),hs=float(s.scale);
        glUniform2f(centerHi,hx,hy);
        glUniform2f(centerLo,float(s.centerX-double(hx)),float(s.centerY-double(hy)));
        glUniform2f(scale,hs,float(s.scale-double(hs)));
        glUniform1f(angle,float(s.angle));
        glUniform1f(iterations,float(iterationLimit(s)));
        glUniform1f(glow,s.glowEnabled?s.glow:0.0f);
        glUniform1i(palette,s.palette);
        glUniform1i(samples,!mask && s.quality==2?4:1);
        glUniform1i(precise,s.scale<.002?1:0);
        glUniform1i(classify,mask?1:0);
''' + s[b:]
s=s.replace('static Image readFrame(int width, int height) {\n', '''static Image readFrame(int width, int height) {
    if(width<=0 || height<=0 || size_t(width)*size_t(height)>size_t(3840)*2160)
        throw std::runtime_error("Readback exceeds the 31.64 MiB buffer limit.");
''')
s=s.replace('    if(action!=GLFW_PRESS) return;', '''    if(action!=GLFW_PRESS && action!=GLFW_REPEAT) return;
    if(action==GLFW_REPEAT && key!=GLFW_KEY_UP && key!=GLFW_KEY_DOWN) return;''')
s=s.replace('else if(key==GLFW_KEY_G) s.glow=s.glow>0 ? 0.0f : 1.0f;', '''else if(key==GLFW_KEY_G) s.glowEnabled=!s.glowEnabled;
    else if(key==GLFW_KEY_UP || key==GLFW_KEY_DOWN) {
        s.glow=std::clamp(s.glow+(key==GLFW_KEY_UP?.1f:-.1f),0.0f,2.0f);s.glowEnabled=true;
    }''')
s=s.replace('"Glacier","Jade","Amber","Amethyst","Coral"','"Classic","Glacier","Jade","Amethyst","Ember"')
s=s.replace('out<<"Mandelbulb | "','out<<"Mandelbrot 2D | "')
s=s.replace('<<" | GPU "', '<<" | Zoom "<<std::setprecision(3)<<DEFAULT_SCALE/s.scale<<"x | "<<iterationLimit(s)<<" iter | "<<(s.autoRotate?"Spin":"Still")<<" | Glow "<<(s.glowEnabled?s.glow:0.0f)\n       <<" | GPU "')
s=s.replace('L:pan R:orbit M:zoom | 1-5/C color Q quality Space spin','L:pan R:rotate M:zoom | 1-5/C Q G Space F R Esc')
a=s.index('static void verifyScene('); b=s.index('static int runApplication',a)
s=s[:a]+'''// Independent CPU double-precision oracle for the GPU membership mask.
static bool cpuInside(double cr,double ci,int limit) {
    double zr=0,zi=0;
    for(int i=0;i<limit;++i) {
        const double next=zr*zr-zi*zi+cr;
        zi=2*zr*zi+ci;zr=next;
        if(zr*zr+zi*zi>65536.0) return false;
    }
    return true;
}
static void verifyMask(Renderer& renderer,const AppState& s,int w,int h) {
    renderer.draw(w,h,s,true);
    const auto f=readFrame(w,h);
    int mismatch=0,count=0,inside=0;
    for(int y=3;y<h;y+=7) for(int x=3;x<w;x+=7) {
        double px=(x+.5-w*.5)*2.0/h*s.scale,py=(y+.5-h*.5)*2.0/h*s.scale;
        double cr=s.centerX+px*std::cos(s.angle)-py*std::sin(s.angle);
        double ci=s.centerY+px*std::sin(s.angle)+py*std::cos(s.angle);
        bool expected=cpuInside(cr,ci,iterationLimit(s));
        bool actual=f.pixel(x,y)[0]>127;
        mismatch+=expected!=actual;inside+=expected;++count;
    }
    std::cout<<"Mask scale "<<s.scale<<": "<<mismatch<<"/"<<count<<" mismatches, "<<inside<<" interior samples.\\n";
    require(mismatch<=std::max(2,count/100),"GPU differs from CPU Mandelbrot oracle");
}
static void verifyScene(GLFWwindow* w,Renderer& renderer) {
    AppState s;
    renderer.draw(640,480,s);
    const Image baseline=readFrame(640,480);
    require(brightness(baseline.pixel(320,240))<2,"Mandelbrot interior must be black");
    require(brightness(baseline.pixel(0,0))>8,"coloured exterior missing");
    // Retain only the baseline and one transient readback, never five full frames.
    for(int i=1;i<5;++i) {
        s.palette=i;renderer.draw(640,480,s);
        require(imageDifference(baseline,readFrame(640,480))>8,"palettes indistinguishable");
    }
    s=AppState{};renderer.draw(640,480,s);
    require(readFrame(640,480).rgba==baseline.rgba,"frame not deterministic");
    verifyMask(renderer,s,640,480);
    s.button=GLFW_MOUSE_BUTTON_RIGHT;moveCamera(s,110,25,480);renderer.draw(640,480,s);
    require(imageDifference(baseline,readFrame(640,480))>5,"plane rotation has no effect");
    verifyMask(renderer,s,640,480);
    s=AppState{};s.button=GLFW_MOUSE_BUTTON_LEFT;moveCamera(s,80,30,480);renderer.draw(640,480,s);
    require(imageDifference(baseline,readFrame(640,480))>5,"pan has no effect");
    s=AppState{};zoom(s,-.35);renderer.draw(640,480,s);
    require(imageDifference(baseline,readFrame(640,480))>5,"zoom has no effect");
    zoom(s,-100);require(s.scale==MIN_SCALE,"near clamp failed");zoom(s,100);require(s.scale==MAX_SCALE,"far clamp failed");
    s=AppState{};s.glowEnabled=false;renderer.draw(640,480,s);
    require(imageDifference(baseline,readFrame(640,480))>.01,"glow has no effect");
    s=AppState{};s.centerX=-.743643887037151;s.centerY=.13182590420533;s.scale=1e-7;
    verifyMask(renderer,s,320,240);
    s.scale=.001;verifyMask(renderer,s,320,240);
    s=AppState{};
    for(auto size:std::array<std::array<int,2>,3>{{{480,640},{777,511},{1600,1000}}}) {
        glfwSetWindowSize(w,size[0],size[1]);glfwPollEvents();
        int width,height;glfwGetFramebufferSize(w,&width,&height);
        for(int q=0;q<3;++q) {
            s.quality=q;renderer.draw(width,height,s);const auto f=readFrame(width,height);
            const int caps[]={640,960,1440};
            require(std::max(renderer.rw,renderer.rh)<=caps[q],"render size cap exceeded");
            require(size_t(renderer.rw)*renderer.rh*4<=size_t(1440)*1440*4,"texture memory cap exceeded");
            require(brightness(f.pixel(width/2,height/2))<2,"resized interior missing");
            require(brightness(f.pixel(0,0))>8,"resized exterior missing");
        }
    }
    glfwSetWindowUserPointer(w,&s);
    for(int i=0;i<5;++i) {keyCallback(w,GLFW_KEY_1+i,0,GLFW_PRESS,0);require(s.palette==i,"numeric palette failed");}
    keyCallback(w,GLFW_KEY_C,0,GLFW_PRESS,0);require(s.palette==0,"palette cycle failed");
    for(int i=0;i<3;++i) {int old=s.quality;keyCallback(w,GLFW_KEY_Q,0,GLFW_PRESS,0);require(s.quality==(old+1)%3,"quality cycle failed");}
    keyCallback(w,GLFW_KEY_G,0,GLFW_PRESS,0);require(!s.glowEnabled,"glow key failed");
    keyCallback(w,GLFW_KEY_UP,0,GLFW_PRESS,0);require(s.glowEnabled && s.glow>1,"glow intensity failed");
    for(int i=0;i<40;++i)keyCallback(w,GLFW_KEY_DOWN,0,GLFW_REPEAT,0);
    require(s.glow==0,"glow lower bound failed");
    keyCallback(w,GLFW_KEY_SPACE,0,GLFW_PRESS,0);require(s.autoRotate,"auto rotation key failed");
    keyCallback(w,GLFW_KEY_SPACE,0,GLFW_REPEAT,0);require(s.autoRotate,"repeat toggled rotation");
    keyCallback(w,GLFW_KEY_SPACE,0,GLFW_PRESS,0);require(!s.autoRotate,"pause key failed");
    keyCallback(w,GLFW_KEY_F,0,GLFW_PRESS,0);require(s.fpsCap==60,"FPS key failed");
    keyCallback(w,GLFW_KEY_F,0,GLFW_PRESS,0);require(s.fpsCap==30,"FPS restore failed");
    scrollCallback(w,0,2);require(s.scale<DEFAULT_SCALE,"wheel zoom failed");
    mouseCallback(w,GLFW_MOUSE_BUTTON_MIDDLE,GLFW_PRESS,0);double old=s.scale;
    cursorCallback(w,s.lastX,s.lastY+20);require(s.scale>old,"middle drag failed");
    mouseCallback(w,GLFW_MOUSE_BUTTON_MIDDLE,GLFW_RELEASE,0);require(!s.drag,"drag release failed");
    keyCallback(w,GLFW_KEY_R,0,GLFW_PRESS,0);
    require(s.quality==1 && s.scale==DEFAULT_SCALE && s.centerX==-.6 && s.centerY==0 && s.angle==0 && s.palette==0 && s.glow==1 && s.glowEnabled && !s.autoRotate && !s.drag && s.fpsCap==30,"reset failed");
    keyCallback(w,GLFW_KEY_ESCAPE,0,GLFW_PRESS,0);require(glfwWindowShouldClose(w),"exit key failed");
    glfwSetWindowShouldClose(w,0);glfwSetWindowUserPointer(w,nullptr);
    std::cout<<"PASS: CPU/GPU Mandelbrot membership, deep zoom, five palettes, deterministic frame, 2D rotation/pan/zoom, bounds, glow, three qualities, resize, texture budget, all original keys.\\n";
}
''' + s[b:]
a=s.index('        std::cout<<"Mandelbulb Studio /');b=s.index(';return 0;',a)
s=s[:a]+'''        std::cout<<"Mandelbrot 2D / OpenGL 3.3\\n--verify | --benchmark | --capture file.ppm\\n--palette 1..5 --quality 0..2 --width 320..3840 --height 240..2160\\n--center-x -4..4 --center-y -4..4 --scale 1e-7..4 --angle radians --glow 0..2\\nLegacy: --yaw/--pitch add plane rotation, --distance = scale*2.45, --time = rotation seconds\\nLeft drag: pan; right drag: rotate plane; wheel/middle drag: zoom\\n1..5/C palette; Q quality; G glow; Up/Down intensity; Space auto rotation; F 30/60 fps; R reset; Esc exit\\n"''' + s[b:]
s=s.replace('"Mandelbulb Studio",nullptr,nullptr','"Mandelbrot 2D",nullptr,nullptr')
s=s.replace('s.yaw=options.yaw;s.pitch=options.pitch;s.distance=options.distance;', 's.centerX=options.centerX;s.centerY=options.centerY;s.scale=options.scale;\n        s.angle=std::remainder(options.yaw+options.pitch+options.time*.18,PI2);')
s=s.replace('s.yaw=.55f+float(i)*.025f;', 's.angle=double(i)*.025;')
s=s.replace('s.yaw=std::remainder(s.yaw+float(dt)*.18f,6.2831853f);','s.angle=std::remainder(s.angle+dt*.18,PI2);')
p.write_text(s,encoding='utf-8')

p=root/'src/shaders/scene.frag'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('Points that never escape stay black, so the solid interior is exactly the\n//   set;', 'Points not escaping within the finite iteration budget stay black;\n//   this approximates membership in the set;')
s=s.replace('vec2 offset = vec2(0.0);', 'vec2 offset = uSamples == 4 ? vec2(-0.25, -0.25) : vec2(0.0);')
s=s.replace('vec2(r.x * step, 0.0)', 'dsMul(ds(r.x), uScale)').replace('vec2(r.y * step, 0.0)', 'dsMul(ds(r.y), uScale)')
# Glow is visible without requiring near-cap iterations, and remains a local effect.
s=s.replace('pow(level, 4.0) * 1.50 + near * 0.06', 'pow(level, 4.0) * 1.50 + (1.0 - exp(-mu * 0.035)) * 0.08')
p.write_text(s,encoding='utf-8')
print('Completed 2D host, shader integration and verification.')
