/**
 * CameraManager - Single Camera to Multiple Destinations
 *
 * Manages a single camera stream and distributes frames to multiple
 * canvas destinations for parallel effect processing.
 */

export class CameraManager {
    constructor(config = {}) {
        this.config = {
            resolution: config.resolution || { w: 1920, h: 1080 },
            frameRate: config.frameRate || 30,
            // No facingMode - use whatever camera is available (external preferred)
            ...config
        };

        // Actual video dimensions (set after camera init)
        this.videoWidth = 0;
        this.videoHeight = 0;
        this.aspectRatio = 16 / 9;

        // Core elements
        this.videoElement = null;
        this.sourceCanvas = null;
        this.sourceCtx = null;
        this.stream = null;

        // Destinations (effect processors)
        this.destinations = new Map(); // id -> { canvas, ctx, effect }

        // State
        this.isRunning = false;
        this.animationId = null;
        this.lastFrameTime = 0;
        this.frameInterval = 1000 / this.config.frameRate;

        // Callbacks
        this.onFrameCallbacks = [];

        // Performance tracking
        this.fps = 0;
        this.frameCount = 0;
        this.fpsLastTime = 0;
    }

    /**
     * Initialize camera and start capture
     */
    async initialize(videoElementId = 'camera-source') {
        // Get video element
        this.videoElement = document.getElementById(videoElementId);
        if (!this.videoElement) {
            this.videoElement = document.createElement('video');
            this.videoElement.id = videoElementId;
            this.videoElement.autoplay = true;
            this.videoElement.playsInline = true;
            this.videoElement.muted = true;
            this.videoElement.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;';
            document.body.appendChild(this.videoElement);
        }

        // Create source canvas for frame capture
        this.sourceCanvas = document.createElement('canvas');
        this.sourceCanvas.width = this.config.resolution.w;
        this.sourceCanvas.height = this.config.resolution.h;
        this.sourceCtx = this.sourceCanvas.getContext('2d', { willReadFrequently: true });

        // Request camera access
        try {
            // Request high resolution without specifying facingMode
            // This allows external cameras to be used for full-body capture
            const constraints = {
                video: {
                    width: { ideal: this.config.resolution.w },
                    height: { ideal: this.config.resolution.h },
                    frameRate: { ideal: this.config.frameRate }
                    // NO facingMode - use default/external camera
                },
                audio: false
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoElement.srcObject = this.stream;

            // Wait for video to be ready
            await new Promise((resolve) => {
                this.videoElement.onloadedmetadata = () => {
                    this.videoElement.play();
                    resolve();
                };
            });

            // Store actual video dimensions
            this.videoWidth = this.videoElement.videoWidth;
            this.videoHeight = this.videoElement.videoHeight;
            this.aspectRatio = this.videoWidth / this.videoHeight;

            // Update source canvas to match actual video dimensions
            this.sourceCanvas.width = this.videoWidth;
            this.sourceCanvas.height = this.videoHeight;

            console.log('[CameraManager] Camera initialized:', {
                width: this.videoWidth,
                height: this.videoHeight,
                aspectRatio: this.aspectRatio.toFixed(2)
            });

            return true;
        } catch (error) {
            console.error('[CameraManager] Failed to access camera:', error);
            throw error;
        }
    }

    /**
     * Add a destination canvas that will receive processed frames
     * @param {string} id - Unique identifier for this destination
     * @param {HTMLCanvasElement} canvas - Canvas element to render to
     * @param {object} effect - Effect processor with processFrame(imageData) method
     */
    addDestination(id, canvas, effect = null) {
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        this.destinations.set(id, { canvas, ctx, effect });
        console.log(`[CameraManager] Added destination: ${id}`);
    }

    /**
     * Remove a destination
     * @param {string} id - Destination identifier
     */
    removeDestination(id) {
        this.destinations.delete(id);
        console.log(`[CameraManager] Removed destination: ${id}`);
    }

    /**
     * Update effect for a destination
     * @param {string} id - Destination identifier
     * @param {object} effect - New effect processor
     */
    setEffect(id, effect) {
        const dest = this.destinations.get(id);
        if (dest) {
            dest.effect = effect;
        }
    }

    /**
     * Start the frame capture and distribution loop
     */
    start() {
        if (this.isRunning) return;

        this.isRunning = true;
        this.lastFrameTime = performance.now();
        this.fpsLastTime = performance.now();
        this.frameCount = 0;

        this._captureLoop();
        console.log('[CameraManager] Started capture loop');
    }

    /**
     * Stop the frame capture loop
     */
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        console.log('[CameraManager] Stopped capture loop');
    }

    /**
     * Register callback for each frame
     * @param {function} callback - Function called with (sourceCanvas, timestamp)
     */
    onFrame(callback) {
        this.onFrameCallbacks.push(callback);
    }

    /**
     * Get current frame as ImageData
     */
    getCurrentFrame() {
        return this.sourceCtx.getImageData(
            0, 0,
            this.sourceCanvas.width,
            this.sourceCanvas.height
        );
    }

    /**
     * Get current frame as base64 JPEG
     */
    getCurrentFrameBase64() {
        return this.sourceCanvas.toDataURL('image/jpeg', 0.8);
    }

    /**
     * Internal capture loop
     */
    _captureLoop() {
        if (!this.isRunning) return;

        const now = performance.now();
        const elapsed = now - this.lastFrameTime;

        // Frame rate limiting
        if (elapsed >= this.frameInterval) {
            this.lastFrameTime = now - (elapsed % this.frameInterval);

            // Capture frame from video to source canvas
            this.sourceCtx.drawImage(
                this.videoElement,
                0, 0,
                this.sourceCanvas.width,
                this.sourceCanvas.height
            );

            // Get source image data once for efficiency
            const sourceImageData = this.getCurrentFrame();

            // Distribute to all destinations
            this._distributeFrame(sourceImageData, now);

            // Call frame callbacks
            for (const callback of this.onFrameCallbacks) {
                try {
                    callback(this.sourceCanvas, now);
                } catch (error) {
                    console.error('[CameraManager] Frame callback error:', error);
                }
            }

            // Update FPS
            this.frameCount++;
            if (now - this.fpsLastTime >= 1000) {
                this.fps = this.frameCount;
                this.frameCount = 0;
                this.fpsLastTime = now;
            }
        }

        this.animationId = requestAnimationFrame(() => this._captureLoop());
    }

    /**
     * Distribute frame to all destinations
     */
    _distributeFrame(sourceImageData, timestamp) {
        for (const [id, dest] of this.destinations) {
            try {
                if (dest.effect && typeof dest.effect.processFrame === 'function') {
                    // Effect processor handles the frame
                    dest.effect.processFrame(sourceImageData, dest.canvas, dest.ctx, timestamp);
                } else {
                    // No effect - draw with proper aspect ratio (contain, not stretch)
                    this._drawContain(dest.canvas, dest.ctx);
                }
            } catch (error) {
                console.error(`[CameraManager] Error processing destination ${id}:`, error);
            }
        }
    }

    /**
     * Draw source to destination with "contain" behavior (preserve aspect ratio)
     */
    _drawContain(destCanvas, destCtx) {
        const srcW = this.sourceCanvas.width;
        const srcH = this.sourceCanvas.height;
        const dstW = destCanvas.width;
        const dstH = destCanvas.height;

        const srcAspect = srcW / srcH;
        const dstAspect = dstW / dstH;

        let drawW, drawH, drawX, drawY;

        if (srcAspect > dstAspect) {
            // Source is wider - fit to width, letterbox top/bottom
            drawW = dstW;
            drawH = dstW / srcAspect;
            drawX = 0;
            drawY = (dstH - drawH) / 2;
        } else {
            // Source is taller - fit to height, pillarbox left/right
            drawH = dstH;
            drawW = dstH * srcAspect;
            drawX = (dstW - drawW) / 2;
            drawY = 0;
        }

        // Clear with black
        destCtx.fillStyle = '#000';
        destCtx.fillRect(0, 0, dstW, dstH);

        // Draw centered
        destCtx.drawImage(this.sourceCanvas, drawX, drawY, drawW, drawH);
    }

    /**
     * Get current FPS
     */
    getFPS() {
        return this.fps;
    }

    /**
     * Cleanup resources
     */
    dispose() {
        this.stop();

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }

        this.destinations.clear();
        this.onFrameCallbacks = [];

        console.log('[CameraManager] Disposed');
    }
}
