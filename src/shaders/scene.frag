#version 330 core
#extension GL_ARB_gpu_shader_fp64 : enable

// Colourful plane Mandelbrot set.
//
//   z <- z^2 + c, starting from z = 0, escaping once |z|^2 passes 65536.
//   Points not escaping within the finite iteration budget stay black;
//   this approximates membership in the set; the exterior is painted by the smooth (normalised) escape count.
//   Nothing is stored per frame beyond the one RGBA8 target the caller binds.
//
// Deep zoom uses native fp64 when supported. The host limits zoom otherwise.

out vec4 fragColor;

uniform vec2  uResolution;   // internal render size, pixels
uniform vec2  uCenterHi;     // plane centre (re, im), high part
uniform vec2  uCenterLo;     //                    low part
uniform vec2  uScale;        // half of the visible height: (high, low)
uniform float uAngle;        // plane rotation, radians
uniform float uIterations;   // iteration cap
uniform float uGlow;         // 0..2 boundary glow
uniform int   uPalette;      // 0..4
uniform int   uSamples;      // 1 or 4 samples per pixel
uniform int   uPrecise;      // 1 => native double arithmetic
uniform int   uClassify;     // 1 => output interior mask (verification)

const float BAILOUT2    = 65536.0;
const float LOG_BAILOUT = 5.5451774444795623;   // ln 256

// ------------------------------------------------------------------ colour
vec3 srgbToLinear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec3 linearToSrgb(vec3 c) {
    c = max(c, vec3(0.0));
    return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}

// Five stops read dark -> mid -> bright -> mid -> dark so the cycle wraps
// without a seam. Stops are given in sRGB and converted once below.
vec3 rampCycle(vec3 s0, vec3 s1, vec3 s2, vec3 s3, vec3 s4, float t) {
    float u = fract(t) * 5.0;
    if (u < 1.0) return mix(s0, s1, smoothstep(0.0, 1.0, u));
    if (u < 2.0) return mix(s1, s2, smoothstep(0.0, 1.0, u - 1.0));
    if (u < 3.0) return mix(s2, s3, smoothstep(0.0, 1.0, u - 2.0));
    if (u < 4.0) return mix(s3, s4, smoothstep(0.0, 1.0, u - 3.0));
    return mix(s4, s0, smoothstep(0.0, 1.0, u - 4.0));
}

void theme(int p, out vec3 s0, out vec3 s1, out vec3 s2, out vec3 s3, out vec3 s4,
           out vec3 accent) {
    if (p == 0) {                       // 1  Classic
        s0 = vec3(  0.0,   7.0, 100.0) / 255.0;
        s1 = vec3( 32.0, 107.0, 203.0) / 255.0;
        s2 = vec3(237.0, 255.0, 255.0) / 255.0;
        s3 = vec3(255.0, 170.0,   0.0) / 255.0;
        s4 = vec3(  0.0,   2.0,   0.0) / 255.0;
        accent = vec3(255.0, 217.0, 160.0) / 255.0;
    } else if (p == 1) {                // 2  Glacier
        s0 = vec3( 11.0,  27.0,  46.0) / 255.0;
        s1 = vec3( 27.0, 127.0, 168.0) / 255.0;
        s2 = vec3(127.0, 227.0, 218.0) / 255.0;
        s3 = vec3( 47.0, 111.0, 168.0) / 255.0;
        s4 = vec3( 12.0,  33.0,  54.0) / 255.0;
        accent = vec3(203.0, 247.0, 242.0) / 255.0;
    } else if (p == 2) {                // 3  Jade
        s0 = vec3( 10.0,  26.0,  17.0) / 255.0;
        s1 = vec3( 20.0, 113.0,  63.0) / 255.0;
        s2 = vec3(140.0, 232.0, 120.0) / 255.0;
        s3 = vec3( 43.0, 140.0,  99.0) / 255.0;
        s4 = vec3( 14.0,  36.0,  24.0) / 255.0;
        accent = vec3(214.0, 247.0, 174.0) / 255.0;
    } else if (p == 3) {                // 4  Amethyst
        s0 = vec3( 20.0,  11.0,  38.0) / 255.0;
        s1 = vec3( 85.0,  38.0, 155.0) / 255.0;
        s2 = vec3(199.0, 155.0, 255.0) / 255.0;
        s3 = vec3(110.0,  63.0, 184.0) / 255.0;
        s4 = vec3( 27.0,  16.0,  48.0) / 255.0;
        accent = vec3(232.0, 210.0, 255.0) / 255.0;
    } else {                            // 5  Ember
        s0 = vec3( 27.0,  11.0,  12.0) / 255.0;
        s1 = vec3(166.0,  35.0,  20.0) / 255.0;
        s2 = vec3(255.0, 143.0,  94.0) / 255.0;
        s3 = vec3(198.0,  61.0,  36.0) / 255.0;
        s4 = vec3( 40.0,  10.0,  12.0) / 255.0;
        accent = vec3(255.0, 203.0, 169.0) / 255.0;
    }
}

// The main cardioid and the period-2 bulb are exactly interior. Testing them
// analytically keeps the solid middle from burning the whole iteration budget.
bool triviallyInside(float cr, float ci) {
    float px = cr - 0.25, py = ci;
    float q  = px * px + py * py;
    bool cardioid = (q * (q + px) <= 0.25 * py * py);
    float bx = cr + 1.0;
    bool bulb = (bx * bx + ci * ci <= 0.0625);
    return cardioid || bulb;
}

void main() {
    vec3 s0, s1, s2, s3, s4, accent;
    theme(uPalette, s0, s1, s2, s3, s4, accent);
    s0 = srgbToLinear(s0); s1 = srgbToLinear(s1); s2 = srgbToLinear(s2);
    s3 = srgbToLinear(s3); s4 = srgbToLinear(s4); accent = srgbToLinear(accent);

    vec2  halfRes = 0.5 * uResolution;
    float pixels  = 2.0 / uResolution.y;
    float ca = cos(uAngle), sa = sin(uAngle);
    float step = uScale.x;

    vec3  accum   = vec3(0.0);
    float insides = 0.0;

    for (int s = 0; s < 4; ++s) {
        if (s >= uSamples) break;
        vec2 offset = uSamples == 4 ? vec2(-0.25, -0.25) : vec2(0.0);
        if (s == 1)      offset = vec2( 0.25, -0.25);
        else if (s == 2) offset = vec2(-0.25,  0.25);
        else if (s == 3) offset = vec2( 0.25,  0.25);

        vec2 q = (gl_FragCoord.xy + offset - halfRes) * pixels;
        vec2 r = vec2(q.x * ca - q.y * sa, q.x * sa + q.y * ca);

        float crf = uCenterHi.x + (uCenterLo.x + r.x * (step + uScale.y));
        float cif = uCenterHi.y + (uCenterLo.y + r.y * (step + uScale.y));

        // The analytic test is only exact enough while plain floats still
        // resolve one pixel; at depth a misjudged edge would smear whole bands.
        bool inside = (uPrecise == 0) && triviallyInside(crf, cif);
        float mu = 0.0;

        if (!inside) {
            inside = true;
#ifdef GL_ARB_gpu_shader_fp64
            if (uPrecise == 1) {
                double pixelScale = double(uScale.x) + double(uScale.y);
                // Form the pixel grid in double precision as well as the orbit.
                dvec2 dq = (dvec2(gl_FragCoord.xy) + dvec2(offset) - dvec2(halfRes)) * (2.0 / double(uResolution.y));
                dvec2 dr = dvec2(dq.x * double(ca) - dq.y * double(sa), dq.x * double(sa) + dq.y * double(ca));
                double cr = double(uCenterHi.x) + double(uCenterLo.x) + dr.x * pixelScale;
                double ci = double(uCenterHi.y) + double(uCenterLo.y) + dr.y * pixelScale;
                double zr = 0.0, zi = 0.0;
                for (int i = 0; i < 4096; ++i) {
                    if (float(i) >= uIterations) break;
                    double nzr = zr * zr - zi * zi + cr;
                    double nzi = 2.0 * zr * zi + ci;
                    zr = nzr; zi = nzi;
                    float m2 = float(zr * zr + zi * zi);
                    if (m2 > BAILOUT2) {
                        inside = false;
                        mu = float(i) + 1.0 - log2(log(sqrt(m2)) / LOG_BAILOUT);
                        break;
                    }
                }
            } else
#endif
            {
                float zr = 0.0, zi = 0.0;
                for (int i = 0; i < 4096; ++i) {
                    if (float(i) >= uIterations) break;
                    float nzr = zr * zr - zi * zi + crf;
                    float nzi = 2.0 * zr * zi + cif;
                    zr = nzr; zi = nzi;
                    float m2 = zr * zr + zi * zi;
                    if (m2 > BAILOUT2) {
                        inside = false;
                        mu = float(i) + 1.0 - log2(log(sqrt(m2)) / LOG_BAILOUT);
                        break;
                    }
                }
            }
        }

        if (inside) insides += 1.0;

        vec3 colour = vec3(0.0);
        if (!inside) {
            float level = clamp(mu / uIterations, 0.0, 1.0);
            float near  = pow(level, 1.6);
            vec3  band  = rampCycle(s0, s1, s2, s3, s4, mu * 0.045 + 0.86);
            colour  = band * (0.70 + 0.30 * near);
            colour += accent * (pow(level, 4.0) * 1.50 + (1.0 - exp(-mu * 0.035)) * 0.08) * uGlow;
        }
        accum += colour;
    }
    accum /= float(uSamples);

    if (uClassify == 1) {
        fragColor = vec4(vec3(insides * 2.0 > float(uSamples) ? 1.0 : 0.0), 1.0);
        return;
    }

    accum = accum / (1.0 + accum);            // keep the rim from clipping
    accum = linearToSrgb(accum);
    float noise = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
    fragColor = vec4(clamp(accum + (noise - 0.5) / 255.0, 0.0, 1.0), 1.0);
}
