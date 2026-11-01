#version 330 core
// particles: synthetic fixture (written for the tests) — one simulation step into two targets
layout(location = 0) out vec4 outPosition;
layout(location = 1) out vec4 outVelocity;
in vec2 vUv;

uniform sampler2D uPosition;
uniform sampler2D uVelocity;
uniform float uDt, uDrag;
uniform vec3 uGravity;

struct Particle {
  vec3 pos;
  vec3 vel;
  float age;
};

Particle readParticle(vec2 uv) {
  Particle p;
  vec4 a = texture(uPosition, uv);
  vec4 b = texture(uVelocity, uv);
  p.pos = a.xyz;
  p.age = a.w;
  p.vel = b.xyz;
  return p;
}

vec3 dragOf(vec3 v) { return -uDrag * v * length(v); }

Particle step(Particle p) {
  vec3 acc = uGravity + dragOf(p.vel);
  p.vel += acc * uDt;
  p.pos += p.vel * uDt;
  p.age += uDt;
  if (p.pos.y < 0.0) {
    p.pos.y = -p.pos.y;
    p.vel.y = -0.5 * p.vel.y;
  }
  return p;
}

void main() {
  Particle p = step(readParticle(vUv));
  outPosition = vec4(p.pos, p.age);
  outVelocity = vec4(p.vel, 1.0);
}
