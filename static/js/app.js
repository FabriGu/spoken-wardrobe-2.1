/**
 * Spoken Wardrobe - Main Application
 *
 * Entry point for the Three.js frontend. Initializes WebSocket connection,
 * state manager, and Three.js scene for 3D mesh overlay.
 */

import { WebSocketClient } from './websocket.js';
import { UIStateManager } from './state_manager.js';
import { MeshLoadingAnimation } from './mesh_loading_animation.js';
import { KeypointRenderer } from './keypoint_renderer.js';

/**
 * Audio Analyzer for real-time waveform visualization.
 * Uses Web Audio API to capture microphone audio and analyze frequencies.
 */
class AudioAnalyzer {
    constructor() {
        this.audioContext = null;
        this.analyser = null;
        this.source = null;
        this.stream = null;
        this.dataArray = null;
        this.isRunning = false;
        this.animationId = null;
        this.onDataCallback = null;
    }

    /**
     * Start capturing and analyzing audio from microphone.
     * @param {function} onData - Callback called with frequency data array (0-255 values)
     */
    async start(onData) {
        if (this.isRunning) return;

        this.onDataCallback = onData;

        try {
            // Get microphone access
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Create audio context and analyser
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 64; // 32 frequency bins
            this.analyser.smoothingTimeConstant = 0.8;

            // Connect microphone to analyser
            this.source = this.audioContext.createMediaStreamSource(this.stream);
            this.source.connect(this.analyser);

            // Create data array for frequency data
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);

            this.isRunning = true;
            this._animate();

            console.log('[AudioAnalyzer] Started');
        } catch (error) {
            console.warn('[AudioAnalyzer] Could not access microphone:', error.message);
            // Fallback to simulated waveform if microphone access denied
        }
    }

    /**
     * Stop audio capture.
     */
    stop() {
        this.isRunning = false;

        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        if (this.source) {
            this.source.disconnect();
            this.source = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }

        console.log('[AudioAnalyzer] Stopped');
    }

    /**
     * Animation loop to continuously read frequency data.
     * @private
     */
    _animate() {
        if (!this.isRunning) return;

        this.analyser.getByteFrequencyData(this.dataArray);

        if (this.onDataCallback) {
            this.onDataCallback(this.dataArray);
        }

        this.animationId = requestAnimationFrame(() => this._animate());
    }
}

class SpokenWardrobeApp {
    constructor() {
        this.wsClient = null;
        this.stateManager = null;
        this.threeScene = null;
        this.meshData = null;
        this.audioAnalyzer = null;
        this.meshLoadingAnimation = null;
        this.keypointRenderer = null;
        this.lastLandmarks = null;  // Track last known landmarks for A-pose positioning
        this.lastFrameAspect = null;

        // Initialize on DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    /**
     * Initialize the application.
     */
    init() {
        console.log('[App] Initializing Spoken Wardrobe UI...');

        // Initialize audio analyzer for real waveform
        this.audioAnalyzer = new AudioAnalyzer();

        // Initialize keypoint renderer for BlazePose visualization
        const keypointCanvas = document.getElementById('keypoint-overlay');
        if (keypointCanvas) {
            this.keypointRenderer = new KeypointRenderer(keypointCanvas);
            console.log('[App] Keypoint renderer initialized');
        }

        // Initialize state manager
        this.stateManager = new UIStateManager();
        this.stateManager.onUserAction = (action) => this.handleUserAction(action);
        this.stateManager.onStateChange = (newState, oldState) => this._handleStateChange(newState, oldState);

        // Initialize WebSocket client
        this.wsClient = new WebSocketClient('ws://localhost:8765');
        this._setupWebSocketHandlers();
        this.wsClient.connect();
        this.wsClient.startHeartbeat();

        // Initialize Three.js scene (lazy load when needed)
        this._initThreeScene();

        console.log('[App] Initialization complete');
    }

    /**
     * Handle state transitions for audio analyzer and mesh loading animation.
     * @private
     */
    _handleStateChange(newState, oldState) {
        const audioStates = ['LISTENING', 'RECORDING'];

        // Start audio analyzer when entering listening/recording state
        if (audioStates.includes(newState) && !audioStates.includes(oldState)) {
            this.audioAnalyzer.start((frequencyData) => {
                this.stateManager.updateWaveformFromFrequencyData(frequencyData);
            });
        }

        // Stop audio analyzer when leaving listening/recording state
        if (audioStates.includes(oldState) && !audioStates.includes(newState)) {
            this.audioAnalyzer.stop();
        }

        // Handle 3D mesh loading animation
        if (newState === 'GENERATING_3D') {
            this._startMeshLoadingAnimation();
        } else if (oldState === 'GENERATING_3D') {
            this._stopMeshLoadingAnimation();
        }
    }

    /**
     * Start the 3D mesh loading animation.
     * @private
     */
    async _startMeshLoadingAnimation() {
        const container = document.getElementById('mesh-animation-container');
        if (!container) return;

        // Create and initialize if not exists
        if (!this.meshLoadingAnimation) {
            this.meshLoadingAnimation = new MeshLoadingAnimation(container);
            try {
                await this.meshLoadingAnimation.init();
            } catch (error) {
                console.warn('[App] Could not initialize mesh loading animation:', error);
                return;
            }
        }

        this.meshLoadingAnimation.start();
    }

    /**
     * Stop the 3D mesh loading animation.
     * @private
     */
    _stopMeshLoadingAnimation() {
        if (this.meshLoadingAnimation) {
            this.meshLoadingAnimation.stop();
        }
    }

    /**
     * Set up WebSocket event handlers.
     * @private
     */
    _setupWebSocketHandlers() {
        this.wsClient.onConnect = () => {
            console.log('[App] Connected to pipeline');
        };

        this.wsClient.onDisconnect = () => {
            console.log('[App] Disconnected from pipeline');
        };

        this.wsClient.onStateChange = (state, data) => {
            console.log(`[App] State change: ${state}`, data);
            this.stateManager.transition(state, data);

            // Reset mesh to center during CALIBRATING (before body tracking starts)
            if (state === 'CALIBRATING' && this.threeScene) {
                this.threeScene.resetToCenter();
            }

            // Position A-pose SVG based on user's keypoints when entering A_POSE state
            if (state === 'A_POSE' && this.lastLandmarks && this.keypointRenderer) {
                const topKeypoint = this.keypointRenderer.getTopKeypoint(this.lastLandmarks);
                if (topKeypoint) {
                    this._positionAposeSvg(topKeypoint, this.lastFrameAspect);
                }
            }
        };

        this.wsClient.onFrame = (imageBase64, landmarks, calibration, boneRotations, landmarks2d, frameAspect) => {
            this.stateManager.updateCameraFeed(imageBase64);

            // Store landmarks for A-pose positioning
            if (landmarks2d) {
                this.lastLandmarks = landmarks2d;
                this.lastFrameAspect = frameAspect;
            }

            // Render keypoints on overlay canvas (always visible)
            if (this.keypointRenderer && landmarks2d) {
                this.keypointRenderer.render(landmarks2d, frameAspect);
            } else if (this.keypointRenderer) {
                // Clear keypoints if no body detected
                this.keypointRenderer.clear();
            }

            // Update mesh if we have a mesh loaded
            if (this.threeScene && this.meshData) {
                // Update bone rotations for skeletal animation (if available)
                if (boneRotations) {
                    this.threeScene.updateBonesFromFrame(boneRotations);
                }

                // Update rigid transform as fallback (if skeletal animation disabled)
                if (calibration) {
                    this.threeScene.updateMeshTransform(calibration);
                }
            }
        };

        this.wsClient.onAudioLevel = (level, threshold) => {
            this.stateManager.updateWaveform(level);
        };

        this.wsClient.onTranscription = (text, isFinal) => {
            this.stateManager.updateTranscription(text, isFinal);
        };

        this.wsClient.onGenerationProgress = (stage, percent, message) => {
            this.stateManager.updateProgress(stage, percent, message);
        };

        this.wsClient.onMeshReady = async (glbBase64, sizeKb, textureBase64) => {
            console.log(`[App] Mesh received (${sizeKb.toFixed(1)} KB)`);
            this.meshData = glbBase64;

            // Ensure Three.js scene is initialized before loading mesh
            if (!this.threeScene) {
                console.warn('[App] ThreeScene not yet initialized, initializing now...');
                await this._initThreeScene();
            }

            if (this.threeScene) {
                await this.threeScene.loadMeshFromBase64(glbBase64);

                // Apply texture if provided and mesh doesn't have one
                if (textureBase64 && !this.threeScene.hasTexture) {
                    console.log('[App] Applying fallback texture to mesh');
                    // Check if method exists (defensive - in case of module loading issues)
                    if (typeof this.threeScene.applyTextureFromBase64 === 'function') {
                        this.threeScene.applyTextureFromBase64(textureBase64);
                    } else {
                        console.warn('[App] applyTextureFromBase64 method not available - browser may have cached old version. Try hard refresh (Cmd+Shift+R)');
                    }
                }
            } else {
                console.error('[App] Failed to initialize ThreeScene for mesh loading');
            }
        };

        this.wsClient.onPreviewImage = (imageBase64) => {
            this.stateManager.updatePreviewImage(imageBase64);
        };

        this.wsClient.onPreviewImageCropped = (imageBase64) => {
            this.stateManager.updatePreviewImageCropped(imageBase64);
        };

        this.wsClient.onPreviewMask = (maskBase64) => {
            this.stateManager.updatePreviewMask(maskBase64);
        };
    }

    /**
     * Initialize the Three.js scene for 3D mesh overlay.
     * @private
     */
    async _initThreeScene() {
        // Lazy load Three.js scene module for 3D mesh overlay
        try {
            const { ThreeScene } = await import('./three_scene.js');
            const canvas = document.getElementById('three-canvas');
            this.threeScene = new ThreeScene(canvas);
            console.log('[App] Three.js scene initialized');
            console.log('[App] ThreeScene methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(this.threeScene)));
        } catch (error) {
            console.error('[App] Three.js scene failed to load:', error);
            console.error('[App] This may be caused by CDN module version incompatibility');
            console.error('[App] Check that three-mesh-bvh version is compatible with three.js version');
            // Three.js is optional - UI continues without 3D mesh overlay
        }
    }

    /**
     * Position the A-pose SVG overlay based on user's top keypoint.
     * Centers horizontally and aligns top to keypoint position + head offset.
     * @param {Object} topKeypoint - {x, y} in normalized coordinates [0-1]
     * @param {number} frameAspect - Frame aspect ratio for cover calculation
     * @private
     */
    _positionAposeSvg(topKeypoint, frameAspect) {
        const aposeOverlay = document.querySelector('.apose-overlay');
        if (!aposeOverlay) return;

        // Get container dimensions
        const container = document.getElementById('app') || document.body;
        const containerRect = container.getBoundingClientRect();
        const w = containerRect.width;
        const h = containerRect.height;

        if (w === 0 || h === 0) return;

        // Calculate object-fit: cover transformation (same as keypoint renderer)
        const canvasAspect = w / h;
        const imgAspect = frameAspect || (4/3);

        let scaleX, scaleY, offsetX, offsetY;
        if (canvasAspect > imgAspect) {
            const scaledW = w;
            const scaledH = w / imgAspect;
            scaleX = scaledW;
            scaleY = scaledH;
            offsetX = 0;
            offsetY = (scaledH - h) / 2;
        } else {
            const scaledH = h;
            const scaledW = h * imgAspect;
            scaleX = scaledW;
            scaleY = scaledH;
            offsetX = (scaledW - w) / 2;
            offsetY = 0;
        }

        // Transform normalized keypoint to screen position
        const screenY = topKeypoint.y * scaleY - offsetY;

        // Add offset for head (nose is ~10% down from top of head)
        const headOffset = h * 0.08;
        const topPosition = Math.max(0, screenY - headOffset);

        // Calculate SVG height to fill from top position to near bottom
        const bottomMargin = h * 0.05;
        const svgHeight = Math.max(100, h - topPosition - bottomMargin);

        // Apply positioning - keep centered horizontally, align top to keypoint
        aposeOverlay.style.top = `${topPosition}px`;
        aposeOverlay.style.left = '50%';
        aposeOverlay.style.transform = 'translateX(-50%)';
        aposeOverlay.style.height = `${svgHeight}px`;

        console.log(`[App] A-pose SVG positioned: top=${topPosition.toFixed(0)}px, height=${svgHeight.toFixed(0)}px`);
    }

    /**
     * Handle user actions from the UI.
     * @param {string} action - Action name
     */
    handleUserAction(action) {
        console.log(`[App] User action: ${action}`);
        this.wsClient.sendAction(action);
    }
}

// Start the application
const app = new SpokenWardrobeApp();

// Export for debugging
window.SpokenWardrobeApp = app;
