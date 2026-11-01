#version 330 core
uniform float uTime;
const float alpha = 1.0, beta = 2.0;
struct Particle {
    vec3 position;
    float size;
};
layout(std140) uniform Camera {
    mat4 projection;
} camera;
#define SCALE 2.0
// Transform one sample.
float transform(float x) {
    x *= SCALE;
    return x;
}
