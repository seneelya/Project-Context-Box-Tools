#version 330 core
// Synthetic fixture: conditional preprocessor branches that split C statements,
// so glsl-spec reports ERROR / MISSING nodes inside main (written for the tests).
out vec4 fragColor;
uniform float uMix;
uniform float uGain;

float layerWeight(int k) {
  return 1.0 / float(k + 1);
}

vec4 layerColor(int k, vec2 uv) {
  return vec4(uv, float(k) * 0.25, 1.0);
}

void main() {
  vec2 uv = gl_FragCoord.xy / 512.0;
  vec4 acc = vec4(0.0);
  for (int k = 0; k < 3; k++) {
    if (layerWeight(k) <= 0.0) continue;
    vec4 c;
#ifdef SPLIT_IF
    if (k == 0 && uMix > 0.5) {
      c = layerColor(k, uv * 2.0);
    } else
#endif
    {
      c = layerColor(k, uv);
    }
#ifdef SPLIT_OPEN
    if (uGain > 1.0) {
      c *= uGain;
#endif
    acc += c * layerWeight(k);
  }
#ifdef SPLIT_TAIL
  acc.rgb = vec3(1.0) - acc.rgb;
#endif
  fragColor = acc;
}
