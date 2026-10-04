import { EmilyScene } from './three/EmilyScene.js';
import { InteractionController } from './ui/InteractionController.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize 3D Space
    window.emilyScene = new EmilyScene(document.getElementById('three-container'));
    
    // 2. Initialize UI Interaction (Ambient mode)
    window.interactionController = new InteractionController();
    
    // Cinematic & Awakening Sequence
    const uiLayer = document.getElementById('ui-layer');
    const cinematic = document.getElementById('intro-cinematic');
    
    if (uiLayer) {
        uiLayer.style.opacity = '0';
        uiLayer.style.pointerEvents = 'none';
        uiLayer.style.transition = 'opacity 2s ease-in';
    }
    
    // Expand cinematic text slowly
    setTimeout(() => {
        if (cinematic) cinematic.classList.add('expand');
    }, 100);
    
    // Fade out cinematic overlay
    setTimeout(() => {
        if (cinematic) cinematic.classList.add('fade-out');
    }, 800);
    
    // Trigger Core Awakening
    setTimeout(() => {
        if (window.emilyScene) window.emilyScene.triggerAwakening();
        
        // UI layer fades in after core forms
        setTimeout(() => {
            if (uiLayer) {
                uiLayer.style.opacity = '1';
                uiLayer.style.pointerEvents = 'all';
            }
        }, 800); 
    }, 1000);
    
    // Provide a global bridge so index.html's scripts can update the scene
    window.updateEmilyVisualState = (state) => {
        window.currentEmilyState = state;
        if(window.emilyScene) window.emilyScene.setSystemState(state);
        if(window.interactionController) window.interactionController.resetIdle();
    };
    
    window.updateEmilyAudioLevel = (level) => {
        if(window.emilyScene) window.emilyScene.setAudioLevel(level);
    };
});
