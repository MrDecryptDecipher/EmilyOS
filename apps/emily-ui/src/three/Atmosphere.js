import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js';

function createLumenTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255, 255, 255, 0.9)');
    grad.addColorStop(0.25, 'rgba(56, 189, 248, 0.4)');
    grad.addColorStop(0.6, 'rgba(14, 165, 233, 0.1)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    const texture = new THREE.CanvasTexture(canvas);
    return texture;
}

function createVignetteTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(256, 256, 20, 256, 256, 256);
    grad.addColorStop(0, '#0c1427');
    grad.addColorStop(0.45, '#050914');
    grad.addColorStop(1, '#020409');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 512, 512);
    return new THREE.CanvasTexture(canvas);
}

export class Atmosphere {
    constructor() {
        this.group = new THREE.Group();
        
        // Luxury deep spatial vignette
        const geom = new THREE.PlaneGeometry(120, 120);
        const bgMat = new THREE.MeshBasicMaterial({
            map: createVignetteTexture(),
            depthWrite: false
        });
        const bg = new THREE.Mesh(geom, bgMat);
        bg.position.z = -18;
        this.group.add(bg);

        // Soft Bokeh Micro-Lumens
        const count = 220;
        const pGeom = new THREE.BufferGeometry();
        const positions = new Float32Array(count * 3);
        const speeds = new Float32Array(count);
        const phases = new Float32Array(count);
        
        for(let i = 0; i < count; i++) {
            positions[i*3] = (Math.random() - 0.5) * 36;
            positions[i*3+1] = (Math.random() - 0.5) * 26;
            positions[i*3+2] = (Math.random() - 0.5) * 16 - 3;
            speeds[i] = 0.08 + Math.random() * 0.18;
            phases[i] = Math.random() * Math.PI * 2;
        }
        
        pGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        pGeom.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 1));
        pGeom.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
        
        const pMat = new THREE.PointsMaterial({
            map: createLumenTexture(),
            size: 0.45,
            transparent: true,
            opacity: 0.4,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.particles = new THREE.Points(pGeom, pMat);
        this.group.add(this.particles);
    }
    
    update(time, delta) {
        const positions = this.particles.geometry.attributes.position.array;
        const speeds = this.particles.geometry.attributes.aSpeed.array;
        const phases = this.particles.geometry.attributes.aPhase.array;
        
        for(let i = 0; i < positions.length / 3; i++) {
            positions[i*3+1] += speeds[i] * delta;
            // Ethereal subtle orbital drift
            positions[i*3] += Math.sin(time * 0.4 + phases[i]) * delta * 0.12;
            
            if(positions[i*3+1] > 14) {
                positions[i*3+1] = -14;
                positions[i*3] = (Math.random() - 0.5) * 36;
            }
        }
        this.particles.geometry.attributes.position.needsUpdate = true;
    }
}
