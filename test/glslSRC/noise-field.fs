#version 330 core
// noise-field: synthetic fixture (written for the tests) — value noise on a sphere
out vec4 fragColor;
in vec2 vUv;

#define TAU 6.2831853
vec3 hash3(vec3 p) {
  p = fract(p * vec3(0.1031, 0.1030, 0.0973));
  p += dot(p, p.yxz + 33.33);
  return fract((p.xxy + p.yxx) * p.zyx);
}
float valueNoise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash3(i).x, b = hash3(i + vec3(1, 0, 0)).x;
  float c = hash3(i + vec3(0, 1, 0)).x, d = hash3(i + vec3(1, 1, 0)).x;
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float octaves(vec3 p, int count) {
  float sum = 0.0, amp = 0.5;
  for (int i = 0; i < 8; i++) {
    if (i >= count) break;
    sum += amp * valueNoise(p);
    p = p * 2.0 + 7.3;
    amp *= 0.5;
  }
  return sum;
}

const float SPIN = 1.0;
vec3 dirOfAngles(float a, float b) { return vec3(cos(b) * cos(a), sin(b), SPIN * cos(b) * sin(a)); }
vec2 anglesOfDir(vec3 d) { return vec2(atan(SPIN * d.z, d.x), atan(d.y, length(d.xz))); }   // atan pair
vec3 eastOf(vec3 d) { return normalize(SPIN * vec3(-d.z, 0.0, d.x) + vec3(1e-7, 0.0, 0.0)); }
vec3 northOf(vec3 d) { return SPIN * cross(eastOf(d), d); }

vec3 dirOfUv(vec2 uv) { return dirOfAngles(uv.x * TAU, (uv.y - 0.5) * 3.14159265); }

uniform float uScale, uShift;
uniform vec3 uTint;
// cube-face direction of uv on face f (+X -X +Y -Y +Z -Z)
vec3 cubeDir(float f, vec2 uv) {
  vec2 q = uv * 2.0 - 1.0;
  if (f < 0.5) return normalize(vec3(1.0, -q.y, -q.x));
  if (f < 1.5) return normalize(vec3(-1.0, -q.y, q.x));
  return normalize(vec3(q.x, 1.0, q.y));
}

#ifdef DEBUG_VIEW
uniform float uDebugMix;
float debugStripes(vec2 uv) { return step(0.5, fract(uv.x * 16.0)); }
#endif

uniform float uFace;
uniform int uOctaves;
uniform float uThreshold, uSoftness;
float coverOf(float n, float t) {
  return smoothstep(t - uSoftness, t + uSoftness, n);
}

void main() {
  vec3 d = cubeDir(uFace, vUv);
  float n = octaves(d * uScale + uShift, uOctaves);
  vec3 col = uTint;
#ifdef DEBUG_VIEW
  if (uDebugMix > 0.5) {
    col = vec3(debugStripes(vUv));
  } else
#endif
  float cover = coverOf(n, uThreshold);
  fragColor = vec4(col * cover, cover);
}
