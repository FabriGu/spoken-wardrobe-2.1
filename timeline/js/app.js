/**
 * Timeline Grid Installation - Main Application
 *
 * "Dream to Reality" - A museum installation visualizing
 * the evolution of computer vision through fashion.
 */

import config, { getConfigWithOverrides } from '../config.js';
import { CameraManager } from './CameraManager.js';
import { GridManager } from './GridManager.js';
import { Act1Runway } from './Act1Runway.js';
import { Era1Roberts } from './effects/Era1Roberts.js';

// Apply URL parameter overrides
const appConfig = getConfigWithOverrides(config);

/**
 * Main Application Controller
 */
class TimelineApp {
    constructor() {
        this.cameraManager = null;
        this.gridManager = null;
        this.act1Runway = null;

        // State
        this.currentAct = null; // 'dream', 'journey', 'reality'
        this.currentEra = 0;
        this.isRunning = false;

        // Timing
        this.journeyStartTime = null;
        this.lastEraTime = null;

        // AI Generation state
        this.generationState = {
            started: false,
            image2D: null,
            mesh3D: null
        };

        // Elements
        this.elements = {};

        console.log('[TimelineApp] Initializing with config:', appConfig);
    }

    /**
     * Initialize the application
     */
    async init() {
        this._cacheElements();
        this._showLoading(true);

        try {
            // Initialize camera
            this.cameraManager = new CameraManager({
                resolution: appConfig.cameraResolution,
                frameRate: 30
            });
            await this.cameraManager.initialize();

            // Initialize grid manager
            this.gridManager = new GridManager('era-grid', appConfig);

            // Setup callbacks
            this.gridManager.onCellCreated = (eraId, cellData) => {
                this._onCellCreated(eraId, cellData);
            };

            // Initialize Act 1 runway scene
            this.act1Runway = new Act1Runway('runway-canvas');
            await this.act1Runway.init(this.cameraManager.videoElement);

            // Setup FPS counter if enabled
            if (appConfig.showFps) {
                this._setupFPSCounter();
            }

            this._showLoading(false);

            // Start the experience
            this._startExperience();

        } catch (error) {
            console.error('[TimelineApp] Initialization failed:', error);
            this._showError(error.message);
        }
    }

    /**
     * Cache DOM elements
     */
    _cacheElements() {
        this.elements = {
            actDream: document.getElementById('act-dream'),
            actJourney: document.getElementById('act-journey'),
            actReality: document.getElementById('act-reality'),
            eraGrid: document.getElementById('era-grid'),
            eraLabel: document.getElementById('era-label'),
            loadingOverlay: document.getElementById('loading-overlay'),
            fpsCounter: document.getElementById('fps-counter')
        };
    }

    /**
     * Start the experience
     */
    _startExperience() {
        // Check if we should jump to a specific act
        if (appConfig.jumpToAct === 2) {
            this._startAct('journey');
        } else if (appConfig.jumpToAct === 3) {
            this._startAct('reality');
        } else {
            // Start with Act 1: The Dream
            this._startAct('dream');
        }
    }

    /**
     * Transition to an act
     */
    _startAct(act) {
        console.log(`[TimelineApp] Starting Act: ${act}`);

        // Hide all acts
        this.elements.actDream.classList.add('hidden');
        this.elements.actJourney.classList.add('hidden');
        this.elements.actReality.classList.add('hidden');

        this.currentAct = act;

        switch (act) {
            case 'dream':
                this.elements.actDream.classList.remove('hidden');
                this._runActDream();
                break;

            case 'journey':
                this.elements.actJourney.classList.remove('hidden');
                this._runActJourney();
                break;

            case 'reality':
                this.elements.actReality.classList.remove('hidden');
                this._runActReality();
                break;
        }
    }

    /**
     * Act 1: The Dream
     */
    _runActDream() {
        console.log('[TimelineApp] Act 1: Dream starting');

        // Start camera for silhouette
        this.cameraManager.start();

        // Start runway scene
        this.act1Runway.start();

        // Update UI elements
        const dreamUI = this.elements.actDream.querySelector('#dream-ui');
        if (dreamUI) {
            dreamUI.classList.add('active');
        }

        // After Act 1 duration (configurable), transition to Act 2
        // For now, use a fixed duration. In production, this would wait for speech capture.
        setTimeout(() => {
            this._endActDream();
        }, appConfig.act1Duration || 15000);
    }

    /**
     * End Act 1 and transition to Act 2
     */
    _endActDream() {
        console.log('[TimelineApp] Act 1: Dream ending');

        // Stop runway
        this.act1Runway.stop();

        // Stop camera (will restart for Act 2)
        this.cameraManager.stop();

        // Transition to journey
        this._startAct('journey');
    }

    /**
     * Act 2: The Journey (Grid Experience)
     */
    _runActJourney() {
        console.log('[TimelineApp] Act 2: Journey starting');

        this.isRunning = true;
        this.journeyStartTime = performance.now();
        this.lastEraTime = this.journeyStartTime;
        this.currentEra = 0;

        // Start camera capture
        this.cameraManager.start();

        // Show first era
        this._showNextEra();

        // Start the era progression loop
        this._journeyLoop();
    }

    /**
     * Journey loop - manages era progression timing
     */
    _journeyLoop() {
        if (!this.isRunning || this.currentAct !== 'journey') return;

        const now = performance.now();
        const elapsed = now - this.lastEraTime;

        // Check if it's time for the next era
        if (elapsed >= appConfig.eraDisplayDuration) {
            if (!this.gridManager.isComplete()) {
                this._showNextEra();
                this.lastEraTime = now;
            } else {
                // All eras shown, wait a bit then move to Act 3
                console.log('[TimelineApp] Journey complete');
                setTimeout(() => {
                    this._startAct('reality');
                }, appConfig.eraDisplayDuration);
                return;
            }
        }

        // Continue loop
        requestAnimationFrame(() => this._journeyLoop());
    }

    /**
     * Show the next era in sequence
     */
    _showNextEra() {
        this.currentEra++;

        // Skip if in skip list
        while (appConfig.skipEras.includes(this.currentEra) && this.currentEra <= appConfig.totalEras) {
            this.currentEra++;
        }

        if (this.currentEra > appConfig.totalEras) return;

        // Add era to grid
        const cellData = this.gridManager.showEra(this.currentEra);

        if (cellData) {
            // Get effect for this era
            const effect = this._getEffectForEra(this.currentEra);

            // Register canvas with camera manager (with effect if available)
            this.cameraManager.addDestination(
                `era-${this.currentEra}`,
                cellData.canvas,
                effect
            );

            if (effect) {
                console.log(`[TimelineApp] Attached ${effect.name} to era ${this.currentEra}`);
            }
        }

        console.log(`[TimelineApp] Showing era ${this.currentEra}/${appConfig.totalEras}`);
    }

    /**
     * Get the effect processor for a specific era
     */
    _getEffectForEra(eraId) {
        switch (eraId) {
            case 1:
                return new Era1Roberts();
            // Eras 2-9: Add effects as they're implemented
            case 10:
            case 11:
                // AI generation eras - show generating state
                this.gridManager.setGenerating(eraId, true);
                return null;
            default:
                return null;
        }
    }

    /**
     * Called when a new cell is created
     */
    _onCellCreated(eraId, cellData) {
        console.log(`[TimelineApp] Cell created for era ${eraId}`);
        // Effects are now attached in _showNextEra() after destination is registered
    }

    /**
     * Act 3: The Reality
     */
    _runActReality() {
        console.log('[TimelineApp] Act 3: Reality');

        // TODO: Implement final runway with 3D mesh
        // For now, just show completion message

        // After finale duration, reset
        setTimeout(() => {
            this._resetExperience();
        }, appConfig.act3Duration);
    }

    /**
     * Reset and start over
     */
    _resetExperience() {
        console.log('[TimelineApp] Resetting experience');

        this.isRunning = false;
        this.currentEra = 0;
        this.cameraManager.stop();

        // Clear all camera destinations
        for (let i = 1; i <= appConfig.totalEras; i++) {
            this.cameraManager.removeDestination(`era-${i}`);
        }

        // Reset grid
        this.gridManager.reset();

        // Reset generation state
        this.generationState = {
            started: false,
            image2D: null,
            mesh3D: null
        };

        // Start again
        setTimeout(() => {
            this._startExperience();
        }, 2000);
    }

    /**
     * Setup FPS counter
     */
    _setupFPSCounter() {
        this.elements.fpsCounter.classList.remove('hidden');
        const fpsSpan = this.elements.fpsCounter.querySelector('span');

        setInterval(() => {
            fpsSpan.textContent = this.cameraManager.getFPS();
        }, 500);
    }

    /**
     * Show/hide loading overlay
     */
    _showLoading(show) {
        if (show) {
            this.elements.loadingOverlay.classList.remove('hidden');
        } else {
            this.elements.loadingOverlay.classList.add('hidden');
        }
    }

    /**
     * Show error message
     */
    _showError(message) {
        const overlay = this.elements.loadingOverlay;
        overlay.innerHTML = `
            <div style="color: #ff6b6b; font-size: 1.5rem;">Error</div>
            <div style="margin-top: 1rem;">${message}</div>
            <div style="margin-top: 2rem; font-size: 0.875rem; color: rgba(255,255,255,0.5);">
                Please ensure camera permissions are granted and refresh the page.
            </div>
        `;
        overlay.classList.remove('hidden');
    }

    /**
     * Cleanup
     */
    dispose() {
        this.isRunning = false;
        if (this.act1Runway) {
            this.act1Runway.dispose();
        }
        if (this.cameraManager) {
            this.cameraManager.dispose();
        }
        if (this.gridManager) {
            this.gridManager.reset();
        }
    }
}

// === Application Entry Point ===
let app = null;

async function main() {
    console.log('[Timeline] Dream to Reality - Starting...');

    app = new TimelineApp();
    await app.init();

    // Handle cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (app) app.dispose();
    });
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
} else {
    main();
}

// Export for debugging
window.timelineApp = app;
