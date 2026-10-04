import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js';
import { EmilyPresence } from './EmilyPresence.js';
import { Atmosphere } from './Atmosphere.js';

export class EmilyScene {
    constructor(container) {
        this.container = container;
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.container.appendChild(this.renderer.domElement);

        this.scene = new THREE.Scene();
        
        this.camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 100);
        this.camera.position.z = 10;
        
        // Objects
        this.atmosphere = new Atmosphere();
        this.scene.add(this.atmosphere.group);
        
        this.presence = new EmilyPresence();
        // Dynamic Lighting
        this.coreLight = new THREE.PointLight(0x14b8a6, 0.0, 20);
        this.coreLight.position.set(0, 0, 0);
        this.scene.add(this.coreLight);
        
        this.scene.add(this.presence.mesh);
        
        // Lighting
        const ambient = new THREE.AmbientLight(0xffffff, 0.2);
        this.scene.add(ambient);
        
        // Mouse tracking for subtle parallax
        this.mouseX = 0;
        this.mouseY = 0;
        this.targetCameraZ = 10;
        
        window.addEventListener('mousemove', (e) => {
            this.mouseX = (e.clientX / window.innerWidth) * 2 - 1;
            this.mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
        });

        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        this.clock = new THREE.Clock();
        this.animate = this.animate.bind(this);
        this.animate();
    }
    
    setSystemState(state) {
        this.presence.setState(state);
        
        // Dynamic Lighting Physics
        if(state === 'thinking') {
            this.targetCameraZ = 8.5;
            this.coreLight.color.setHex(0x8b5cf6);
            this.coreLight.intensity = 2.5;
        } else if (state === 'speaking') {
            this.targetCameraZ = 9.5;
            this.coreLight.color.setHex(0x10b981);
            this.coreLight.intensity = 3.0;
        } else {
            this.targetCameraZ = 10;
            this.coreLight.color.setHex(0x14b8a6);
            this.coreLight.intensity = 1.0;
        }
        
        // Cinematic push-in on thinking
        if(state === 'thinking') {
            this.targetCameraZ = 8.5;
        } else if (state === 'speaking') {
            this.targetCameraZ = 9.5;
        } else {
            this.targetCameraZ = 10;
        }
    }
    
    setAudioLevel(level) {
        this.presence.setAudioLevel(level);
    }
    
    
    triggerAwakening() {
        this.presence.uniforms.uIntensity.value = 0.0;
        this.presence.mesh.scale.set(0.1, 0.1, 0.1);
        this.presence.targetIntensity = 1.0;
        this.targetScale = 1.0;
        this.isAwakening = true;
    }
    
    animate() {
        requestAnimationFrame(this.animate);
        const delta = this.clock.getDelta();
        const time = this.clock.getElapsedTime();
        
        this.presence.update(time, delta);
        
        if (this.isAwakening) {
            const currentScale = this.presence.mesh.scale.x;
            const newScale = currentScale + (this.targetScale - currentScale) * delta * 0.5;
            this.presence.mesh.scale.set(newScale, newScale * 1.05, newScale);
            if (newScale > 0.99) this.isAwakening = false;
        }
        
        this.atmosphere.update(time, delta);
        
        // Subtle camera physics
        this.camera.position.x += (this.mouseX * 0.3 - this.camera.position.x) * 0.05;
        this.camera.position.y += (this.mouseY * 0.3 - this.camera.position.y) * 0.05;
        this.camera.position.z += (this.targetCameraZ - this.camera.position.z) * 0.02;
        this.camera.lookAt(0, 0, 0);
        
        this.renderer.render(this.scene, this.camera);
    }
}
