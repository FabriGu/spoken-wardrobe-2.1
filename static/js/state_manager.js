/**
 * Frontend State Manager for Spoken Wardrobe UI
 *
 * Manages UI state transitions, showing/hiding state screens,
 * and coordinating visual updates.
 *
 * States:
 *   - IDLE: Welcome screen
 *   - LISTENING: Listening for speech
 *   - RECORDING: Recording audio
 *   - TRANSCRIBING: Processing audio
 *   - A_POSE: A-pose capture
 *   - CAPTURING: Capturing body frame
 *   - GENERATING_2D: 2D generation
 *   - GENERATING_3D: 3D generation
 *   - PREVIEW: Show 2D preview
 *   - CALIBRATING: Mesh calibration
 *   - TRY_ON: 3D mesh overlay
 *   - ERROR: Error state
 */

export class UIStateManager {
    constructor() {
        this.currentState = 'IDLE';
        this.stateData = {};
        this.stateScreens = {};
        this.waveformBars = [];

        // Store mask image for preview cropping
        this._previewMaskSrc = null;

        // Initialize
        this._initStateScreens();
        this._initWaveform();
        this._initEventListeners();
    }

    /**
     * Cache references to all state screen elements.
     * @private
     */
    _initStateScreens() {
        const states = [
            'idle', 'listening', 'recording', 'transcribing',
            'a_pose', 'capturing', 'generating_2d', 'generating_3d',
            'preview', 'calibrating', 'try_on', 'error'
        ];

        states.forEach(state => {
            const el = document.getElementById(`state-${state}`);
            if (el) {
                this.stateScreens[state.toUpperCase()] = el;
            }
        });

        console.log('[StateManager] Initialized screens:', Object.keys(this.stateScreens));
    }

    /**
     * Initialize waveform visualization bars.
     * @private
     */
    _initWaveform() {
        const waveformContainers = [
            document.getElementById('waveform'),
            document.getElementById('waveform-recording')
        ];

        waveformContainers.forEach(container => {
            if (!container) return;

            // Create 20 bars
            for (let i = 0; i < 20; i++) {
                const bar = document.createElement('div');
                bar.className = 'waveform-bar';
                bar.style.height = '10px';
                container.appendChild(bar);
                this.waveformBars.push(bar);
            }
        });
    }

    /**
     * Initialize UI event listeners.
     * @private
     */
    _initEventListeners() {
        // Restart button
        const restartBtn = document.getElementById('btn-restart');
        if (restartBtn) {
            restartBtn.addEventListener('click', () => {
                this.onUserAction?.('restart');
            });
        }

        // Retry button (error state)
        const retryBtn = document.getElementById('btn-retry');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.onUserAction?.('restart');
            });
        }
    }

    /**
     * Transition to a new state.
     * @param {string} newState - Target state name
     * @param {object} data - State-specific data
     */
    transition(newState, data = {}) {
        const normalizedState = newState.toUpperCase();

        // Check if state screen exists
        if (!this.stateScreens[normalizedState]) {
            console.warn(`[StateManager] Unknown state: ${normalizedState}`);
            return;
        }

        const oldState = this.currentState;
        console.log(`[StateManager] ${oldState} -> ${normalizedState}`);

        // Hide current state
        if (this.stateScreens[this.currentState]) {
            this.stateScreens[this.currentState].classList.remove('active');
        }

        // Update state
        this.currentState = normalizedState;
        this.stateData = data;

        // Show new state
        this.stateScreens[normalizedState].classList.add('active');

        // Toggle body classes for states that need canvas visibility (controls z-index)
        document.body.classList.toggle('try-on-active', normalizedState === 'TRY_ON');
        document.body.classList.toggle('calibrating-active', normalizedState === 'CALIBRATING');
        document.body.classList.toggle('generating-3d-active', normalizedState === 'GENERATING_3D');

        // Run state-specific initialization
        this._onEnterState(normalizedState, data);

        // Notify listeners of state change
        if (this.onStateChange) {
            this.onStateChange(normalizedState, oldState);
        }
    }

    /**
     * Handle state-specific initialization.
     * @private
     */
    _onEnterState(state, data) {
        switch (state) {
            case 'A_POSE':
                this._startCountdown('apose-countdown', data.countdown || 3);
                break;

            case 'CAPTURING':
                // Trigger flash effect and polaroid animation
                this._triggerCaptureSequence(data.captured_frame);
                break;

            case 'CALIBRATING':
                this._startCountdown('calibration-countdown', data.countdown || 3);
                break;

            case 'RECORDING':
                this._startRecordingTimer(data.duration || 10);
                break;

            case 'GENERATING_2D':
                this._resetProgress('2d');
                break;

            case 'GENERATING_3D':
                this._resetProgress('3d');
                break;

            case 'ERROR':
                this._showError(data.error_message || 'An error occurred');
                break;

            case 'PREVIEW':
                this._startPreviewSequence();
                break;

            case 'TRY_ON':
                this._startTryOnAnimation();
                break;
        }
    }

    /**
     * Trigger the capture sequence: flash -> polaroid -> shrink to loading.
     * @private
     */
    _triggerCaptureSequence(capturedFrame) {
        const flashOverlay = document.getElementById('flash-overlay');
        const polaroidContainer = document.getElementById('polaroid-container');
        const polaroidImage = document.getElementById('polaroid-image');
        const cameraFeed = document.getElementById('camera-feed');

        // Get the current camera frame if not provided
        const frameSource = capturedFrame || (cameraFeed ? cameraFeed.src : null);

        // Step 1: Flash effect
        if (flashOverlay) {
            flashOverlay.classList.add('flash');

            // Remove flash class after animation
            setTimeout(() => {
                flashOverlay.classList.remove('flash');
            }, 600);
        }

        // Step 2: Show polaroid with captured frame (after flash peaks)
        if (polaroidContainer && polaroidImage && frameSource) {
            setTimeout(() => {
                polaroidImage.src = frameSource;
                polaroidContainer.classList.remove('hidden');

                // Step 3: Start shrink animation after a brief moment
                setTimeout(() => {
                    polaroidContainer.classList.add('animate-morph');

                    // Step 4: Hide polaroid after animation completes
                    setTimeout(() => {
                        polaroidContainer.classList.add('hidden');
                        polaroidContainer.classList.remove('animate-morph');
                    }, 2000);
                }, 800);
            }, 150); // Start after flash peaks at 15%
        }
    }

    /**
     * Trigger just the flash effect (without polaroid).
     * @private
     */
    _triggerFlash() {
        const flashOverlay = document.getElementById('flash-overlay');
        if (flashOverlay) {
            flashOverlay.classList.add('flash');
            setTimeout(() => {
                flashOverlay.classList.remove('flash');
            }, 600);
        }
    }

    /**
     * Start the two-stage preview sequence.
     * Stage 1: Show full image with "Extracting Clothing" and pulsing glow
     * Stage 2: Show masked/cropped clothing with "Preview Complete" and constant glow
     * Uses canvas compositing to apply mask and show only clothing area.
     * @private
     */
    _startPreviewSequence() {
        const title = document.getElementById('preview-title');
        const status = document.getElementById('preview-status');
        const fullImg = document.getElementById('preview-image-full');
        const croppedImg = document.getElementById('preview-image-cropped');
        const container = document.querySelector('.preview-image-container');

        // Clear any existing timeout from previous sequence
        if (this._previewTimeout) {
            clearTimeout(this._previewTimeout);
        }

        // Stage 1: Show full generated image with extracting state (pulsing glow)
        if (title) title.textContent = 'Clothing Preview Generated';
        if (status) status.textContent = 'Extracting clothing from image...';
        if (fullImg) fullImg.classList.add('active');
        if (croppedImg) croppedImg.classList.remove('active');
        if (container) {
            container.classList.add('extracting');
            container.classList.remove('complete');
        }

        // Stage 2: After 10 seconds, apply mask and show cropped clothing
        this._previewTimeout = setTimeout(() => {
            if (title) title.textContent = 'Preview Complete';
            if (status) status.textContent = 'Your clothing design is ready';

            // Apply mask to create cropped image
            if (fullImg && croppedImg && this._previewMaskSrc) {
                this._applyMaskToPreview(fullImg.src, this._previewMaskSrc, croppedImg);
            }

            if (fullImg) fullImg.classList.remove('active');
            if (croppedImg) croppedImg.classList.add('active');
            if (container) {
                container.classList.remove('extracting');
                container.classList.add('complete');
            }
        }, 10000);
    }

    /**
     * Apply a mask to the preview image using canvas compositing.
     * The mask should be white where clothing is, black elsewhere.
     * Only the white areas of the mask will be visible in the result.
     * @private
     * @param {string} imageSrc - Source URL/data of the full image
     * @param {string} maskSrc - Source URL/data of the mask image
     * @param {HTMLImageElement} targetImg - Image element to receive the result
     */
    _applyMaskToPreview(imageSrc, maskSrc, targetImg) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        const sourceImg = new Image();
        const maskImg = new Image();

        let loadedCount = 0;

        const onBothLoaded = () => {
            loadedCount++;
            if (loadedCount < 2) return;

            // Set canvas to image size
            canvas.width = sourceImg.width;
            canvas.height = sourceImg.height;

            // Draw the source image first
            ctx.drawImage(sourceImg, 0, 0);

            // Apply mask using 'destination-in' composite operation
            // This keeps pixels only where the mask is opaque (white)
            ctx.globalCompositeOperation = 'destination-in';
            ctx.drawImage(maskImg, 0, 0, canvas.width, canvas.height);

            // Reset composite operation
            ctx.globalCompositeOperation = 'source-over';

            // Set the result as the target image source
            targetImg.src = canvas.toDataURL('image/png');
            targetImg.dataset.customSrc = 'true';

            console.log('[StateManager] Applied mask to preview image');
        };

        sourceImg.onload = onBothLoaded;
        maskImg.onload = onBothLoaded;

        sourceImg.src = imageSrc;
        maskImg.src = maskSrc;
    }

    /**
     * Start the Virtual Try-On animation (text center to corner).
     * @private
     */
    _startTryOnAnimation() {
        const header = document.querySelector('.try-on-header');
        if (!header) return;

        // Clear any existing animation timeouts
        if (this._tryOnAnimationTimeout) {
            clearTimeout(this._tryOnAnimationTimeout);
        }

        // Step 1: Remove all animation classes and force centered state
        header.classList.remove('animate', 'in-corner');

        // Force a DOM reflow to ensure CSS is recalculated
        // This is critical for the animation to work properly on subsequent calls
        void header.offsetHeight;

        // Step 2: Enable transitions after a brief delay (allows centered state to render)
        setTimeout(() => {
            header.classList.add('animate');
        }, 50);

        // Step 3: After 4 seconds of being centered, animate to corner
        this._tryOnAnimationTimeout = setTimeout(() => {
            header.classList.add('in-corner');
        }, 4000);
    }

    /**
     * Start a countdown animation using Date.now() for accurate timing.
     * Uses actual elapsed time instead of setInterval callback counting
     * to avoid timer drift issues.
     * @private
     */
    _startCountdown(elementId, seconds) {
        const el = document.getElementById(elementId);
        if (!el) return;

        // Clear any existing countdown interval
        if (this._countdownInterval) {
            clearInterval(this._countdownInterval);
        }

        // Reset opacity
        el.style.opacity = '1';

        // Record start time for accurate elapsed calculation
        const startTime = Date.now();
        const totalDuration = seconds * 1000; // Convert to ms

        // Show initial number
        el.textContent = seconds;

        // Use shorter interval (100ms) and calculate actual remaining time
        this._countdownInterval = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const remaining = totalDuration - elapsed;

            // Calculate which number to display (1 to seconds)
            // remaining 2500-3000ms = show 3, 1500-2500ms = show 2, 500-1500ms = show 1, <500ms = show 1
            const displayNumber = Math.max(1, Math.ceil(remaining / 1000));

            el.textContent = displayNumber;

            // Stop when time is up (but keep showing "1")
            if (remaining <= 0) {
                el.textContent = '1';
                clearInterval(this._countdownInterval);
                this._countdownInterval = null;
            }
        }, 100); // Check every 100ms for smooth updates
    }

    /**
     * Start the recording timer.
     * @private
     */
    _startRecordingTimer(duration) {
        const el = document.getElementById('recording-timer');
        if (!el) return;

        let remaining = duration;
        el.textContent = remaining;

        const interval = setInterval(() => {
            remaining--;
            if (remaining <= 0) {
                clearInterval(interval);
            }
            el.textContent = remaining;
        }, 1000);
    }

    /**
     * Reset progress ring.
     * @private
     */
    _resetProgress(stage) {
        const ring = document.getElementById(`progress-ring-${stage}`);
        const text = document.getElementById(`progress-text-${stage}`);

        if (ring) {
            ring.style.strokeDashoffset = 326.73; // Full circumference
        }
        if (text) {
            text.textContent = '0%';
        }
    }

    /**
     * Update progress ring.
     * @param {string} stage - '2d' or '3d'
     * @param {number} percent - Progress percentage (0-100)
     * @param {string} message - Optional status message
     */
    updateProgress(stage, percent, message = '') {
        const ring = document.getElementById(`progress-ring-${stage}`);
        const text = document.getElementById(`progress-text-${stage}`);
        const status = document.getElementById(`status-${stage}`);

        if (ring) {
            // Calculate stroke-dashoffset
            const circumference = 326.73;
            const offset = circumference - (percent / 100) * circumference;
            ring.style.strokeDashoffset = offset;
        }

        if (text) {
            text.textContent = `${Math.round(percent)}%`;
        }

        if (status && message) {
            status.textContent = message;
        }
    }

    /**
     * Update waveform visualization with audio level (fallback).
     * @param {number} level - Audio level (0.0-1.0)
     */
    updateWaveform(level) {
        this.waveformBars.forEach((bar, index) => {
            // Create varied heights based on level and bar position
            const variation = Math.sin(Date.now() / 100 + index * 0.5);
            const height = 10 + (level * 60) * (0.5 + 0.5 * variation);
            bar.style.height = `${height}px`;
        });
    }

    /**
     * Update waveform visualization with real frequency data from Web Audio API.
     * @param {Uint8Array} frequencyData - Array of frequency bin values (0-255)
     */
    updateWaveformFromFrequencyData(frequencyData) {
        const barCount = this.waveformBars.length;
        const dataLength = frequencyData.length;

        // Map frequency data to waveform bars
        // We have 32 frequency bins (from fftSize=64) and 40 bars (20 per waveform container)
        this.waveformBars.forEach((bar, index) => {
            // Map bar index to frequency data index (with some overlap for smoother look)
            const dataIndex = Math.floor((index % 20) * dataLength / 20);
            const value = frequencyData[dataIndex];

            // Convert 0-255 to pixel height (min 4px, max 70px)
            const height = 4 + (value / 255) * 66;
            bar.style.height = `${height}px`;
        });
    }

    /**
     * Update the camera feed image.
     * Updates both the persistent background and the legacy camera-feed element.
     * @param {string} base64Image - Base64 encoded JPEG image
     */
    updateCameraFeed(base64Image) {
        const dataUrl = `data:image/jpeg;base64,${base64Image}`;

        // Update persistent camera background (always visible)
        const cameraBackground = document.getElementById('camera-background');
        if (cameraBackground) {
            cameraBackground.src = dataUrl;
        }

        // Also update legacy camera-feed element (for polaroid capture source only)
        // NOTE: Do NOT set display:block - it must stay hidden to not cover Three.js canvas
        const legacyFeed = document.getElementById('camera-feed');
        if (legacyFeed) {
            legacyFeed.src = dataUrl;
            // legacyFeed stays display:none - it's only a data source for polaroid capture
        }
    }

    /**
     * Update the transcription overlay text.
     * @param {string} text - Transcribed text
     * @param {boolean} isFinal - Whether this is the final transcription
     */
    updateTranscription(text, isFinal = true) {
        // Update overlay transcription
        const overlay = document.getElementById('transcription-overlay');
        const textEl = document.getElementById('transcription-text');

        if (overlay && textEl) {
            textEl.textContent = text;
            overlay.classList.toggle('hidden', !text);
        }

        // Update live transcription in recording state
        const liveTranscription = document.getElementById('live-transcription');
        if (liveTranscription && text) {
            liveTranscription.textContent = `"${text}"`;
        }
    }

    /**
     * Update the full preview image (uncropped).
     * @param {string} base64Image - Base64 encoded image
     */
    updatePreviewImage(base64Image) {
        const img = document.getElementById('preview-image-full');
        if (img) {
            img.src = `data:image/png;base64,${base64Image}`;
        }
    }

    /**
     * Update the cropped preview image (clothing only).
     * @param {string} base64Image - Base64 encoded image
     */
    updatePreviewImageCropped(base64Image) {
        const img = document.getElementById('preview-image-cropped');
        if (img) {
            img.src = `data:image/png;base64,${base64Image}`;
            img.dataset.customSrc = 'true'; // Mark that a custom cropped image was provided
        }
    }

    /**
     * Store the mask image for preview cropping.
     * The mask will be applied in Stage 2 of the preview sequence.
     * @param {string} base64Mask - Base64 encoded mask image (white=clothing, black=background)
     */
    updatePreviewMask(base64Mask) {
        this._previewMaskSrc = `data:image/png;base64,${base64Mask}`;
        console.log('[StateManager] Received preview mask');
    }

    /**
     * Show error message.
     * @private
     */
    _showError(message) {
        const el = document.getElementById('error-message');
        if (el) {
            el.textContent = message;
        }
    }

    /**
     * Get the current state.
     * @returns {string} Current state name
     */
    getState() {
        return this.currentState;
    }

    /**
     * Check if currently in a specific state.
     * @param {string} state - State to check
     * @returns {boolean}
     */
    isState(state) {
        return this.currentState === state.toUpperCase();
    }

    /**
     * Callback for user actions (to be set by app).
     * @type {function}
     */
    onUserAction = null;

    /**
     * Callback for state changes (to be set by app).
     * Called with (newState, oldState) parameters.
     * @type {function}
     */
    onStateChange = null;
}
