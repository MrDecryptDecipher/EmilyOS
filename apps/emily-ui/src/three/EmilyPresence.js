import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js';

// Advanced 3D Simplex Noise Shader with Analytic Derivation
const vertexShader = `
// Simplex 3D noise
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}

float snoise(vec3 v){
  const vec2  C = vec2(1.0/6.0, 1.0/3.0);
  const vec4  D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + 1.0 * C.xxx;
  vec3 x2 = x0 - i2 + 2.0 * C.xxx;
  vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;
  i = mod(i, 289.0);
  vec4 p = permute(permute(permute(
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 1.0/7.0;
  vec3  ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// Multi-octave organic turbulence
float fbm(vec3 p) {
    float v = 0.0;
    v += snoise(p) * 0.5;
    v += snoise(p * 2.02) * 0.25;
    v += snoise(p * 4.05) * 0.125;
    return v;
}

uniform float uTime;
uniform float uAudioReact;
uniform float uStateDeform;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPosition;
varying float vDisplacement;

void main() {
    float t = uTime * (0.12 + uStateDeform * 0.25);
    
    // Smooth domain warping
    vec3 p = position * 0.8;
    vec3 q = p + vec3(t * 0.4, t * 0.3, t * 0.2);
    float noiseVal = fbm(q);
    
    // Audio harmonic pulse (silky, non-jagged)
    float audioPulse = sin(length(position) * 3.0 - t * 4.0) * uAudioReact * 0.18;
    float statePulse = fbm(p * 1.5 - vec3(t * 0.6)) * uStateDeform * 0.25;
    
    float totalDisplacement = (noiseVal * 0.22 + audioPulse + statePulse);
    vDisplacement = totalDisplacement;
    
    vec3 newPos = position + normal * totalDisplacement;
    
    // Recompute smooth visual normal
    vNormal = normalize(normalMatrix * (normal + vec3(noiseVal * 0.2)));
    vPosition = (modelViewMatrix * vec4(newPos, 1.0)).xyz;
    vWorldPosition = (modelMatrix * vec4(newPos, 1.0)).xyz;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPos, 1.0);
}
`;

// Ethereal Prismatic Glass & Chromatic Dispersion Fragment Shader
const fragmentShader = `
uniform vec3 uColorBase;
uniform vec3 uColorGlow;
uniform vec3 uColorAccent;
uniform float uIntensity;
uniform float uTime;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPosition;
varying float vDisplacement;

void main() {
    vec3 viewDir = normalize(-vPosition);
    vec3 normal = normalize(vNormal);
    
    // Chromatic Fresnel Dispersion (RGB separation)
    float dotNV = max(dot(normal, viewDir), 0.0);
    float fresnelR = pow(1.0 - dotNV, 2.6);
    float fresnelG = pow(1.0 - clamp(dot(normalize(normal + vec3(0.015, 0.0, 0.0)), viewDir), 0.0, 1.0), 3.0);
    float fresnelB = pow(1.0 - clamp(dot(normalize(normal + vec3(0.035, 0.02, 0.0)), viewDir), 0.0, 1.0), 3.4);
    
    vec3 chromatic = vec3(fresnelR, fresnelG, fresnelB);
    
    // Subsurface scattering & core luminescence
    float coreLuminance = smoothstep(-0.2, 0.35, vDisplacement);
    vec3 innerCore = mix(uColorBase * 0.6, uColorGlow, coreLuminance);
    
    // Prismatic iridescent rim
    vec3 rimColor = mix(uColorGlow, uColorAccent, chromatic.b);
    
    // Specular highlight from imaginary key light
    vec3 lightDir = normalize(vec3(0.7, 0.9, 1.2));
    vec3 halfVec = normalize(lightDir + viewDir);
    float spec = pow(max(dot(normal, halfVec), 0.0), 32.0) * 0.8;
    
    // Final composite
    vec3 finalColor = innerCore + rimColor * (chromatic.r * 0.5 + chromatic.g * 0.3 + chromatic.b * 0.6) + vec3(spec);
    finalColor *= uIntensity;
    
    // Luxurious translucent alpha with soft falloff
    float alpha = clamp(0.75 + fresnelB * 0.25, 0.0, 1.0);
    
    gl_FragColor = vec4(finalColor, alpha);
}
`;

export class EmilyPresence {
    constructor() {
        // High tessellation icosahedron for fluid organic curvature
        this.geometry = new THREE.IcosahedronGeometry(2.35, 80);
        
        this.uniforms = {
            uTime: { value: 0.0 },
            uAudioReact: { value: 0.0 },
            uStateDeform: { value: 0.0 },
            uColorBase: { value: new THREE.Color('#032822') }, 
            uColorGlow: { value: new THREE.Color('#06b6d4') },
            uColorAccent: { value: new THREE.Color('#38bdf8') },
            uIntensity: { value: 1.0 }
        };

        this.material = new THREE.ShaderMaterial({
            vertexShader,
            fragmentShader,
            uniforms: this.uniforms,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        this.mesh = new THREE.Mesh(this.geometry, this.material);
        this.mesh.scale.set(1.0, 1.05, 1.0);
        
        this.targetAudioReact = 0.0;
        this.targetStateDeform = 0.0;
        this.targetIntensity = 1.0;
        this.currentState = 'IDLE';
    }

    update(time, delta) {
        this.uniforms.uTime.value = time;
        this.uniforms.uAudioReact.value += (this.targetAudioReact - this.uniforms.uAudioReact.value) * delta * 6.0;
        this.uniforms.uStateDeform.value += (this.targetStateDeform - this.uniforms.uStateDeform.value) * delta * 2.5;
        this.uniforms.uIntensity.value += (this.targetIntensity - this.uniforms.uIntensity.value) * delta * 3.0;
        
        // Gentle organic precession
        this.mesh.rotation.y = time * 0.04;
        this.mesh.rotation.x = Math.sin(time * 0.08) * 0.04;
    }
    
    setState(state) {
        this.currentState = state;
        switch(state.toLowerCase()) {
            case 'idle':
            case 'listening':
            case 'waiting':
                this.targetStateDeform = 0.0;
                this.targetIntensity = 1.0;
                this.uniforms.uColorBase.value.set('#042823'); 
                this.uniforms.uColorGlow.value.set('#0ea5e9');
                this.uniforms.uColorAccent.value.set('#38bdf8');
                break;
            case 'speaking':
                this.targetStateDeform = 0.22;
                this.targetIntensity = 1.35;
                this.uniforms.uColorBase.value.set('#064e3b');
                this.uniforms.uColorGlow.value.set('#10b981'); 
                this.uniforms.uColorAccent.value.set('#34d399');
                break;
            case 'thinking':
                this.targetStateDeform = 0.65;
                this.targetIntensity = 1.45;
                this.uniforms.uColorBase.value.set('#2e1065'); 
                this.uniforms.uColorGlow.value.set('#8b5cf6');
                this.uniforms.uColorAccent.value.set('#c084fc');
                break;
            case 'error':
                this.targetStateDeform = 0.1;
                this.targetIntensity = 1.1;
                this.uniforms.uColorBase.value.set('#450a0a');
                this.uniforms.uColorGlow.value.set('#ef4444');
                this.uniforms.uColorAccent.value.set('#f87171');
                break;
        }
    }
    
    setAudioLevel(level) {
        this.targetAudioReact = Math.min(Math.max(level, 0.0), 1.0);
    }
}
