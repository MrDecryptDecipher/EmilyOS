
// Manages Ambient UI visibility and depth styling
export class InteractionController {
    constructor() {
        this.idleTimer = null;
        this.isIdle = false;
        this.idleTimeout = 5000; // 5 seconds to ambient
        this.uiLayer = document.getElementById('ui-layer');
        
        this.resetIdle = this.resetIdle.bind(this);
        
        window.addEventListener('mousemove', this.resetIdle);
        window.addEventListener('keydown', this.resetIdle);
        window.addEventListener('click', this.resetIdle);
        
        this.resetIdle();
    }
    
    resetIdle() {
        if(this.isIdle) {
            this.isIdle = false;
            this.uiLayer.classList.remove('ui-ambient');
        }
        clearTimeout(this.idleTimer);
        this.idleTimer = setTimeout(() => {
            // Subtle ambient state without hiding interactive controls
            const state = window.currentEmilyState || 'listening';
            if (state !== 'thinking' && state !== 'speaking') {
                this.isIdle = true;
            }
        }, this.idleTimeout);
    }
}
