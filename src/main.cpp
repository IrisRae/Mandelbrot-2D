#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

#include <glad/gl.h>
#include <GLFW/glfw3.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <chrono>
#include <thread>

namespace fs = std::filesystem;

static fs::path executableDirectory(const char* argumentZero) {
#ifdef _WIN32
    (void)argumentZero;
    std::vector<wchar_t> buffer(32768);
    const DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (!length || length >= buffer.size()) throw std::runtime_error("Cannot locate executable directory.");
    return fs::path(std::wstring(buffer.data(), length)).parent_path();
#else
    return fs::absolute(fs::u8path(argumentZero)).parent_path();
#endif
}

struct Options {
    bool verify = false, help = false, benchmark = false;
    fs::path capture;
    int width = 1280, height = 800, palette = 0, quality = 1;
    double centerX = -0.6, centerY = 0.0, scale = 1.3;
    double yaw = 0.0, pitch = 0.0;
    float time = 0.0f, glow = 1.0f;
};

static Options parseOptions(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto value = [&]() -> std::string {
            if (++i >= argc) throw std::runtime_error("Missing value for " + arg);
            return argv[i];
        };
        auto number = [&]() {
            const std::string input = value();
            size_t count = 0;
            const double result = std::stod(input, &count);
            if (count != input.size() || !std::isfinite(result))
                throw std::runtime_error("Invalid number for " + arg);
            return result;
        };
        auto integer = [&]() {
            const double result = number();
            if (result < 0.0f || result > 8192.0f || result != std::floor(result))
                throw std::runtime_error("Invalid integer for " + arg);
            return static_cast<int>(result);
        };
        if (arg == "--verify") options.verify = true;
        else if (arg == "--benchmark") options.benchmark = true;
        else if (arg == "--help" || arg == "-h") options.help = true;
        else if (arg == "--capture") options.capture = fs::u8path(value());
        else if (arg == "--width") options.width = integer();
        else if (arg == "--height") options.height = integer();
        else if (arg == "--palette") options.palette = integer() - 1;
        else if (arg == "--quality") options.quality = integer();
        else if (arg == "--yaw") options.yaw = number();
        else if (arg == "--pitch") options.pitch = number();
        else if (arg == "--distance") options.scale = number() / 2.45;
        else if (arg == "--scale") options.scale = number();
        else if (arg == "--center-x") options.centerX = number();
        else if (arg == "--center-y") options.centerY = number();
        else if (arg == "--angle") options.yaw = number();
        else if (arg == "--time") options.time = static_cast<float>(number());
        else if (arg == "--glow") options.glow = static_cast<float>(number());
        else throw std::runtime_error("Unknown option: " + arg + " (use --help)");
    }
    if (options.width < 320 || options.height < 240)
        throw std::runtime_error("Minimum image size is 320 x 240.");
    if (options.palette < 0 || options.palette > 4)
        throw std::runtime_error("Palette must be 1 through 5.");
    if(options.width > 3840 || options.height > 2160) throw std::runtime_error("Maximum window/capture size: 3840x2160.");
    if(options.quality > 2) throw std::runtime_error("Quality must be 0, 1 or 2.");
    if(options.scale < 1e-7 || options.scale > 4.0 || std::abs(options.centerX)>4.0 || std::abs(options.centerY)>4.0)
        throw std::runtime_error("Plane out of range: scale 1e-7..4, center -4..4.");
    options.yaw=std::remainder(options.yaw,6.283185307179586);
    options.pitch=std::remainder(options.pitch,6.283185307179586);
    if (options.time < 0.0f || options.time > 86400.0f)
        throw std::runtime_error("Time must be between 0 and 86400 seconds.");
    if (options.glow < 0.0f || options.glow > 2.0f)
        throw std::runtime_error("Glow must be between 0 and 2.");
    if (int(options.verify)+int(options.benchmark)+int(!options.capture.empty())>1)
        throw std::runtime_error("Use --verify, --benchmark and --capture separately.");
    return options;
}

static std::string readText(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Cannot open shader: " + path.string());
    std::ostringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

static GLuint compileShader(GLenum type, const std::string& source) {
    const GLuint shader = glCreateShader(type);
    const char* text = source.c_str();
    glShaderSource(shader, 1, &text, nullptr);
    glCompileShader(shader);
    GLint ok = GL_FALSE;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[4096]{};
        glGetShaderInfoLog(shader, sizeof(log), nullptr, log);
        glDeleteShader(shader);
        throw std::runtime_error(std::string("Shader compilation failed: ") + log);
    }
    return shader;
}

constexpr double PI2 = 6.283185307179586;
constexpr double MIN_SCALE = 1e-7, MAX_SCALE = 4.0, DEFAULT_SCALE = 1.3;
static bool supportsDouble = false;
static double minimumScale = 0.002;
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
    s.scale=std::clamp(s.scale*std::exp(std::clamp(amount,-32.0,32.0)),minimumScale,MAX_SCALE);
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
struct Renderer {
    GLuint program=0,vao=0,fbo=0,texture=0,vertex=0,fragment=0;
    int rw=0,rh=0;
    GLint resolution=-1,centerHi=-1,centerLo=-1,scale=-1,angle=-1,iterations=-1;
    GLint glow=-1,palette=-1,samples=-1,precise=-1,classify=-1;
    void initialize(const fs::path& path) {
        vertex=compileShader(GL_VERTEX_SHADER,readText(path/"scene.vert"));
        fragment=compileShader(GL_FRAGMENT_SHADER,readText(path/"scene.frag"));
        program=glCreateProgram();
        glAttachShader(program,vertex); glAttachShader(program,fragment); glLinkProgram(program);
        GLint ok=0; glGetProgramiv(program,GL_LINK_STATUS,&ok);
        if(!ok) { char log[4096]{}; glGetProgramInfoLog(program,4096,nullptr,log); throw std::runtime_error(log); }
        auto uniform=[&](const char* name) {
            const GLint location=glGetUniformLocation(program,name);
            if(location<0) throw std::runtime_error(std::string("Missing shader uniform: ")+name);
            return location;
        };
        resolution=uniform("uResolution"); centerHi=uniform("uCenterHi"); centerLo=uniform("uCenterLo");
        scale=uniform("uScale"); angle=uniform("uAngle"); iterations=uniform("uIterations");
        glow=uniform("uGlow"); palette=uniform("uPalette"); samples=uniform("uSamples");
        precise=uniform("uPrecise"); classify=uniform("uClassify");
        glGenVertexArrays(1,&vao); glGenFramebuffers(1,&fbo); glGenTextures(1,&texture);
        glBindTexture(GL_TEXTURE_2D,texture);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
        glDisable(GL_DEPTH_TEST); glDisable(GL_BLEND); glDisable(GL_FRAMEBUFFER_SRGB); glDisable(GL_DITHER);
    }
    void draw(int w,int h,const AppState& s,bool mask=false) {
        if(w<=0 || h<=0) throw std::runtime_error("Empty render target.");
        const int caps[]={640,960,1440};
        double ratio=std::min(1.0,double(caps[s.quality])/std::max(w,h));
        int nw=std::max(1,int(w*ratio)),nh=std::max(1,int(h*ratio));
        glBindFramebuffer(GL_FRAMEBUFFER,fbo);
        if(nw!=rw || nh!=rh) {
            rw=nw;rh=nh;
            glBindTexture(GL_TEXTURE_2D,texture);
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,rw,rh,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
            glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
            if(glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE) throw std::runtime_error("Framebuffer allocation failed.");
        }
        glViewport(0,0,rw,rh); glUseProgram(program); glBindVertexArray(vao);
        glUniform2f(resolution,float(rw),float(rh));
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
        glDrawArrays(GL_TRIANGLES,0,3);
        glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo); glBindFramebuffer(GL_DRAW_FRAMEBUFFER,0);
        glBlitFramebuffer(0,0,rw,rh,0,0,w,h,GL_COLOR_BUFFER_BIT,GL_LINEAR);
        glBindFramebuffer(GL_FRAMEBUFFER,0);
    }
    ~Renderer() {
        if(texture) glDeleteTextures(1,&texture);
        if(fbo) glDeleteFramebuffers(1,&fbo);
        if(vao) glDeleteVertexArrays(1,&vao);
        if(program) glDeleteProgram(program);
        if(vertex) glDeleteShader(vertex);
        if(fragment) glDeleteShader(fragment);
    }
};
struct Image {
    int width = 0, height = 0;
    std::vector<unsigned char> rgba;

    const unsigned char* pixel(int x, int y) const {
        x = std::clamp(x, 0, width - 1);
        y = std::clamp(y, 0, height - 1);
        return &rgba[(static_cast<size_t>(y) * width + x) * 4];
    }
    const unsigned char* designPixel(float x, float y) const {
        const float scale = std::min(width / 1280.0f, height / 800.0f);
        return pixel(static_cast<int>(width * 0.5f + x * scale),
                     static_cast<int>(height * 0.5f + y * scale));
    }
    void save(const fs::path& path) const {
        std::ofstream file(path, std::ios::binary);
        if (!file) throw std::runtime_error("Cannot write capture: " + path.string());
        file << "P6\n" << width << ' ' << height << "\n255\n";
        for (int y = height - 1; y >= 0; --y)
            for (int x = 0; x < width; ++x)
                file.write(reinterpret_cast<const char*>(pixel(x, y)), 3);
        file.flush();
        if (!file) throw std::runtime_error("Capture write failed.");
    }
};

static Image readFrame(int width, int height) {
    if(width<=0 || height<=0 || size_t(width)*size_t(height)>size_t(3840)*2160)
        throw std::runtime_error("Readback exceeds the 31.64 MiB buffer limit.");
    Image frame{width, height, std::vector<unsigned char>(static_cast<size_t>(width) * height * 4)};
    glReadBuffer(GL_BACK);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, frame.rgba.data());
    if (glGetError() != GL_NO_ERROR) throw std::runtime_error("OpenGL draw/readback error.");
    return frame;
}

static float brightness(const unsigned char* c) {
    return 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2];
}
static int colorDifference(const unsigned char* a, const unsigned char* b) {
    return std::abs(int(a[0]) - b[0]) + std::abs(int(a[1]) - b[1]) + std::abs(int(a[2]) - b[2]);
}
static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(std::string("Verification failed: ") + message);
}


static void keyCallback(GLFWwindow* w,int key,int,int action,int) {
    if(action!=GLFW_PRESS && action!=GLFW_REPEAT) return;
    if(action==GLFW_REPEAT && key!=GLFW_KEY_UP && key!=GLFW_KEY_DOWN) return;
    auto& s=*static_cast<AppState*>(glfwGetWindowUserPointer(w));
    if(key>=GLFW_KEY_1 && key<=GLFW_KEY_5) s.palette=key-GLFW_KEY_1;
    else if(key==GLFW_KEY_C) s.palette=(s.palette+1)%5;
    else if(key==GLFW_KEY_Q) s.quality=(s.quality+1)%3;
    else if(key==GLFW_KEY_G) s.glowEnabled=!s.glowEnabled;
    else if(key==GLFW_KEY_UP || key==GLFW_KEY_DOWN) {
        s.glow=std::clamp(s.glow+(key==GLFW_KEY_UP?.1f:-.1f),0.0f,2.0f);s.glowEnabled=true;
    }
    else if(key==GLFW_KEY_SPACE) s.autoRotate=!s.autoRotate;
    else if(key==GLFW_KEY_F) s.fpsCap=s.fpsCap==30 ? 60 : 30;
    else if(key==GLFW_KEY_R) s=AppState{};
    else if(key==GLFW_KEY_ESCAPE) glfwSetWindowShouldClose(w,1);
    s.dirty=true;
}
static void mouseCallback(GLFWwindow* w,int button,int action,int) {
    auto& s=*static_cast<AppState*>(glfwGetWindowUserPointer(w));
    if(button!=GLFW_MOUSE_BUTTON_LEFT && button!=GLFW_MOUSE_BUTTON_RIGHT && button!=GLFW_MOUSE_BUTTON_MIDDLE) return;
    if(action==GLFW_PRESS) { s.drag=true;s.button=button;glfwGetCursorPos(w,&s.lastX,&s.lastY); }
    else if(button==s.button) { s.drag=false;s.button=-1; }
}
static void cursorCallback(GLFWwindow* w,double x,double y) {
    auto& s=*static_cast<AppState*>(glfwGetWindowUserPointer(w));
    if(s.drag) { int width,height;glfwGetWindowSize(w,&width,&height);moveCamera(s,x-s.lastX,y-s.lastY,height); }
    s.lastX=x;s.lastY=y;
}
static void scrollCallback(GLFWwindow* w,double,double y) { zoom(*static_cast<AppState*>(glfwGetWindowUserPointer(w)),-y*.10); }
static void title(GLFWwindow* w,const AppState& s,const Renderer& r,double ms) {
    const char* palettes[]={"Classic","Glacier","Jade","Amethyst","Ember"};
    const char* qualities[]={"Eco","Balanced","Fine"};
    std::ostringstream out;
    out<<"Mandelbrot 2D | "<<s.palette+1<<" "<<palettes[s.palette]<<" | "<<qualities[s.quality]<<" "<<r.rw<<"x"<<r.rh
       <<" | Zoom "<<std::setprecision(3)<<DEFAULT_SCALE/s.scale<<"x | "<<iterationLimit(s)<<" iter | "<<(s.autoRotate?"Spin":"Still")<<" | Glow "<<(s.glowEnabled?s.glow:0.0f)
       <<" | GPU "<<std::fixed<<std::setprecision(1)<<ms<<"ms | "<<s.fpsCap<<"fps cap | L:pan R:rotate M:zoom | 1-5/C Q G Space F R Esc";
    glfwSetWindowTitle(w,out.str().c_str());
}
static double imageDifference(const Image& a,const Image& b) {
    double d=0;
    for(size_t i=0;i<a.rgba.size();i+=4) d+=colorDifference(&a.rgba[i],&b.rgba[i]);
    return d/double(a.width*a.height);
}
// Independent CPU double-precision oracle for the GPU membership mask.
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
    std::cout<<"Mask scale "<<s.scale<<": "<<mismatch<<"/"<<count<<" mismatches, "<<inside<<" interior samples.\n";
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
    zoom(s,-100);require(s.scale==minimumScale,"near clamp failed");zoom(s,100);require(s.scale==MAX_SCALE,"far clamp failed");
    s=AppState{};s.glowEnabled=false;renderer.draw(640,480,s);
    require(imageDifference(baseline,readFrame(640,480))>.01,"glow has no effect");
    if(supportsDouble) {
        s=AppState{};s.centerX=-.743643887037151;s.centerY=.13182590420533;s.scale=1e-7;
        verifyMask(renderer,s,320,240);
        s.scale=.001;verifyMask(renderer,s,320,240);
    } else std::cout<<"SKIP deep zoom: fp64 unavailable, limited to 650x.\n";
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
    std::cout<<"PASS: CPU/GPU Mandelbrot membership, deep zoom, five palettes, deterministic frame, 2D rotation/pan/zoom, bounds, glow, three qualities, resize, texture budget, all original keys.\n";
}
static int runApplication(int argc,char** argv) {
    Options options;
    try { options=parseOptions(argc,argv); } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
    if(options.help) {
        std::cout<<"Mandelbrot 2D / OpenGL 3.3\n--verify | --benchmark | --capture file.ppm\n--palette 1..5 --quality 0..2 --width 320..3840 --height 240..2160\n--center-x -4..4 --center-y -4..4 --scale 1e-7..4 --angle radians --glow 0..2\nLegacy: --yaw/--pitch add plane rotation, --distance = scale*2.45, --time = rotation seconds\nLeft drag: pan; right drag: rotate plane; wheel/middle drag: zoom\n1..5/C palette; Q quality; G glow; Up/Down intensity; Space auto rotation; F 30/60 fps; R reset; Esc exit\n";return 0;
    }
    glfwSetErrorCallback([](int code,const char* msg){std::cerr<<code<<": "<<msg<<'\n';});
    if(!glfwInit()) return 1;
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);
    glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_DEPTH_BITS,0);glfwWindowHint(GLFW_STENCIL_BITS,0);glfwWindowHint(GLFW_SAMPLES,0);
    bool hidden=options.verify || options.benchmark || !options.capture.empty();
    if(hidden) glfwWindowHint(GLFW_VISIBLE,GLFW_FALSE);
    GLFWwindow* w=glfwCreateWindow(options.verify?640:options.width,options.verify?480:options.height,"Mandelbrot 2D",nullptr,nullptr);
    if(!w) {glfwTerminate();return 1;}
    glfwMakeContextCurrent(w);
    if(!gladLoadGL(glfwGetProcAddress) || !GLAD_GL_VERSION_3_3) {glfwDestroyWindow(w);glfwTerminate();return 1;}
    glfwSwapInterval(hidden?0:1);
    glfwSetWindowSizeLimits(w,320,240,3840,2160);
    std::cout<<"GPU: "<<glGetString(GL_RENDERER)<<"\nOpenGL: "<<glGetString(GL_VERSION)<<'\n';
    int result=0;
    try {
        supportsDouble=glfwExtensionSupported("GL_ARB_gpu_shader_fp64")==GLFW_TRUE;
        minimumScale=supportsDouble?MIN_SCALE:0.002;
        if(options.scale<minimumScale) throw std::runtime_error("This GPU supports scale >= 0.002; deeper zoom needs GL_ARB_gpu_shader_fp64.");
        std::cout<<"Deep zoom fp64: "<<(supportsDouble?"yes":"no")<<'\n';
        Renderer renderer;renderer.initialize(executableDirectory(argv[0])/"shaders");
        AppState s;s.palette=options.palette;s.quality=options.quality;s.glow=options.glow;
        s.centerX=options.centerX;s.centerY=options.centerY;s.scale=options.scale;
        s.angle=std::remainder(options.yaw+options.pitch+options.time*.18,PI2);
        if(options.benchmark) {
            int width,height;glfwGetFramebufferSize(w,&width,&height);
            GLuint query;glGenQueries(1,&query);
            for(int q=0;q<3;q++) {
                s.quality=q;double sum=0,peak=0;
                for(int i=0;i<16;i++) {
                    s.angle=double(i)*.025;
                    glBeginQuery(GL_TIME_ELAPSED,query);renderer.draw(width,height,s);glEndQuery(GL_TIME_ELAPSED);
                    GLuint64 ns=0;glGetQueryObjectui64v(query,GL_QUERY_RESULT,&ns);
                    double ms=double(ns)*1e-6;
                    if(i>=4){sum+=ms;peak=std::max(peak,ms);}
                }
                std::cout<<"Quality "<<q<<" internal "<<renderer.rw<<'x'<<renderer.rh<<" GPU mean "<<sum/12.0<<"ms peak "<<peak<<"ms; RGBA8 "<<double(renderer.rw*renderer.rh*4)/1048576.0<<" MiB\n";
            }
            glDeleteQueries(1,&query);
            require(glGetError()==GL_NO_ERROR,"benchmark OpenGL error");
        }
        else if(options.verify) verifyScene(w,renderer);
        else if(!options.capture.empty()) {
            int width,height;glfwGetFramebufferSize(w,&width,&height);
            renderer.draw(width,height,s);readFrame(width,height).save(options.capture);
            std::cout<<"Saved "<<options.capture.string()<<" (internal "<<renderer.rw<<'x'<<renderer.rh<<")\n";
        } else {
            glfwSetWindowUserPointer(w,&s);glfwSetKeyCallback(w,keyCallback);glfwSetMouseButtonCallback(w,mouseCallback);
            glfwSetCursorPosCallback(w,cursorCallback);glfwSetScrollCallback(w,scrollCallback);
            glfwSetWindowRefreshCallback(w,[](GLFWwindow* win){static_cast<AppState*>(glfwGetWindowUserPointer(win))->dirty=true;});
            glfwSetFramebufferSizeCallback(w,[](GLFWwindow* win,int,int){static_cast<AppState*>(glfwGetWindowUserPointer(win))->dirty=true;});
            glfwSetWindowFocusCallback(w,[](GLFWwindow* win,int focused){auto& a=*static_cast<AppState*>(glfwGetWindowUserPointer(win));if(!focused){a.drag=false;a.button=-1;}a.dirty=true;});
            GLuint query=0;glGenQueries(1,&query);bool pending=false;
            double gpuMs=0,lastFrame=glfwGetTime();int slowFrames=0;
            while(!glfwWindowShouldClose(w)) {
                glfwPollEvents();int width,height;glfwGetFramebufferSize(w,&width,&height);
                if(width<=0 || height<=0 || glfwGetWindowAttrib(w,GLFW_ICONIFIED)) {glfwWaitEventsTimeout(.2);lastFrame=glfwGetTime();continue;}
                if(!s.dirty && (!s.autoRotate || !glfwGetWindowAttrib(w,GLFW_FOCUSED))) {glfwWaitEventsTimeout(.1);lastFrame=glfwGetTime();continue;}
                double now=glfwGetTime(),remaining=1.0/s.fpsCap-(now-lastFrame);
                if(remaining>0) {glfwWaitEventsTimeout(remaining);continue;}
                double dt=std::min(now-lastFrame,.1);lastFrame=now;
                if(s.autoRotate && glfwGetWindowAttrib(w,GLFW_FOCUSED) && !s.drag) s.angle=std::remainder(s.angle+dt*.18,PI2);
                if(pending) {
                    GLint available=0;glGetQueryObjectiv(query,GL_QUERY_RESULT_AVAILABLE,&available);
                    if(available) {
                        GLuint64 ns=0;glGetQueryObjectui64v(query,GL_QUERY_RESULT,&ns);gpuMs=double(ns)*1e-6;pending=false;
                        slowFrames=gpuMs>28.0 ? slowFrames+1 : 0;
                        if(slowFrames>=12 && s.quality>0) {--s.quality;slowFrames=0;std::cout<<"GPU budget: quality reduced.\n";}
                    }
                }
                bool timed=!pending;
                if(timed) glBeginQuery(GL_TIME_ELAPSED,query);
                renderer.draw(width,height,s);
                if(timed) {glEndQuery(GL_TIME_ELAPSED);pending=true;}
                glfwSwapBuffers(w);s.dirty=false;
                title(w,s,renderer,gpuMs);
            }
            glDeleteQueries(1,&query);
        }
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';result=1;}
    glfwDestroyWindow(w);glfwTerminate();return result;
}

#ifdef _WIN32
int wmain(int argc, wchar_t** argv) {
    try {
        std::vector<std::string> arguments;
        arguments.reserve(argc);
        for (int i = 0; i < argc; ++i) {
            const int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, argv[i], -1,
                                                   nullptr, 0, nullptr, nullptr);
            if (length <= 0) throw std::runtime_error("Invalid Unicode argument.");
            std::string text(static_cast<size_t>(length), '\0');
            if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, argv[i], -1,
                                     text.data(), length, nullptr, nullptr))
                throw std::runtime_error("Cannot decode Unicode argument.");
            text.pop_back();
            arguments.push_back(std::move(text));
        }
        std::vector<char*> pointers;
        pointers.reserve(argc);
        for (auto& text : arguments) pointers.push_back(text.data());
        return runApplication(argc, pointers.data());
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
#else
int main(int argc, char** argv) { return runApplication(argc, argv); }
#endif
