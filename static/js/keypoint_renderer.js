/**
 * Keypoint Renderer for Spoken Wardrobe
 *
 * Renders BlazePose keypoints on a 2D canvas overlay.
 * Uses purple/blue theme colors to match the UI design.
 *
 * The canvas overlay sits above the Three.js canvas, ensuring
 * keypoints are always visible regardless of 3D mesh rendering.
 */

export class KeypointRenderer {
    /**
     * Create a keypoint renderer.
     * @param {HTMLCanvasElement} canvas - The canvas element to render on
     */
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');

        // Theme colors (matching UI)
        this.colors = {
            primary: '#8B5CF6',      // Purple
            secondary: '#3B82F6',    // Blue
            highlight: '#EC4899',    // Pink
            light: '#A78BFA',        // Light purple
            white: '#FFFFFF'
        };

        // BlazePose skeleton connections (pairs of landmark indices)
        this.connections = [
            // Torso
            [11, 12], [11, 23], [12, 24], [23, 24],
            // Left arm
            [11, 13], [13, 15],
            // Right arm
            [12, 14], [14, 16],
            // Left leg
            [23, 25], [25, 27],
            // Right leg
            [24, 26], [26, 28]
        ];

        // Key landmarks (larger, highlighted)
        this.keyLandmarks = new Set([0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]);

        // Visibility threshold
        this.visibilityThreshold = 0.5;

        // Initialize transform (will be calculated in render())
        this._transform = { scaleX: 1, scaleY: 1, offsetX: 0, offsetY: 0 };

        // Resize canvas to match display size
        this._resizeCanvas();
        window.addEventListener('resize', () => this._resizeCanvas());
    }

    /**
     * Resize canvas to match its display size.
     * @private
     */
    _resizeCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        if (this.canvas.width !== rect.width || this.canvas.height !== rect.height) {
            this.canvas.width = rect.width;
            this.canvas.height = rect.height;
        }
    }

    /**
     * Clear the canvas.
     */
    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * Render keypoints and skeleton connections.
     * @param {Array} landmarks - Array of {x, y, visibility} objects (33 landmarks)
     * @param {number} frameAspect - Original frame aspect ratio (width/height)
     */
    render(landmarks, frameAspect = null) {
        if (!landmarks || landmarks.length === 0) {
            this.clear();
            return;
        }

        this._resizeCanvas();
        this.clear();

        const w = this.canvas.width;
        const h = this.canvas.height;

        if (w === 0 || h === 0) return;  // Canvas not ready

        // Calculate object-fit: cover transformation
        // The camera feed uses object-fit: cover, so we need to match that
        const canvasAspect = w / h;
        const imgAspect = frameAspect || (4/3);  // Default to 4:3 if not provided

        let scaleX, scaleY, offsetX, offsetY;

        if (canvasAspect > imgAspect) {
            // Canvas is wider than image - image scaled by width, height cropped
            const scaledW = w;
            const scaledH = w / imgAspect;
            scaleX = scaledW;
            scaleY = scaledH;
            offsetX = 0;
            offsetY = (scaledH - h) / 2;
        } else {
            // Canvas is taller than image - image scaled by height, width cropped
            const scaledH = h;
            const scaledW = h * imgAspect;
            scaleX = scaledW;
            scaleY = scaledH;
            offsetX = (scaledW - w) / 2;
            offsetY = 0;
        }

        // Store transform for drawing methods
        this._transform = { scaleX, scaleY, offsetX, offsetY };

        // Draw connections first (so keypoints are on top)
        this._drawConnections(landmarks);

        // Draw keypoints
        this._drawKeypoints(landmarks);
    }

    /**
     * Transform normalized coordinates to canvas pixels accounting for object-fit: cover.
     * @private
     */
    _transformCoord(normX, normY) {
        const { scaleX, scaleY, offsetX, offsetY } = this._transform;
        // Map normalized [0-1] coords to scaled image, then offset for centering
        const x = normX * scaleX - offsetX;
        const y = normY * scaleY - offsetY;
        return { x, y };
    }

    /**
     * Draw skeleton connections.
     * @private
     */
    _drawConnections(landmarks) {
        this.ctx.strokeStyle = this.colors.secondary;
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';

        for (const [startIdx, endIdx] of this.connections) {
            const start = landmarks[startIdx];
            const end = landmarks[endIdx];

            if (!start || !end) continue;
            if (start.visibility < this.visibilityThreshold) continue;
            if (end.visibility < this.visibilityThreshold) continue;

            // Transform normalized coordinates to canvas pixels (accounting for object-fit: cover)
            const p1 = this._transformCoord(start.x, start.y);
            const p2 = this._transformCoord(end.x, end.y);

            // Draw glow effect (wider, lighter line behind)
            this.ctx.strokeStyle = this.colors.light;
            this.ctx.lineWidth = 4;
            this.ctx.globalAlpha = 0.3;
            this.ctx.beginPath();
            this.ctx.moveTo(p1.x, p1.y);
            this.ctx.lineTo(p2.x, p2.y);
            this.ctx.stroke();

            // Draw main line
            this.ctx.strokeStyle = this.colors.secondary;
            this.ctx.lineWidth = 2;
            this.ctx.globalAlpha = 1.0;
            this.ctx.beginPath();
            this.ctx.moveTo(p1.x, p1.y);
            this.ctx.lineTo(p2.x, p2.y);
            this.ctx.stroke();
        }
    }

    /**
     * Draw keypoint dots.
     * @private
     */
    _drawKeypoints(landmarks) {
        for (let i = 0; i < landmarks.length; i++) {
            const lm = landmarks[i];
            if (!lm || lm.visibility < this.visibilityThreshold) continue;

            // Transform normalized coordinates to canvas pixels (accounting for object-fit: cover)
            const { x, y } = this._transformCoord(lm.x, lm.y);

            const isKey = this.keyLandmarks.has(i);

            if (isKey) {
                // Key landmarks: larger purple dots with glow
                // Outer glow
                this.ctx.beginPath();
                this.ctx.arc(x, y, 10, 0, Math.PI * 2);
                this.ctx.strokeStyle = this.colors.light;
                this.ctx.lineWidth = 2;
                this.ctx.globalAlpha = 0.5;
                this.ctx.stroke();

                // Main fill
                this.ctx.beginPath();
                this.ctx.arc(x, y, 6, 0, Math.PI * 2);
                this.ctx.fillStyle = this.colors.primary;
                this.ctx.globalAlpha = 1.0;
                this.ctx.fill();

                // White center dot
                this.ctx.beginPath();
                this.ctx.arc(x, y, 2, 0, Math.PI * 2);
                this.ctx.fillStyle = this.colors.white;
                this.ctx.fill();
            } else {
                // Secondary landmarks: smaller blue dots
                this.ctx.beginPath();
                this.ctx.arc(x, y, 3, 0, Math.PI * 2);
                this.ctx.fillStyle = this.colors.secondary;
                this.ctx.globalAlpha = 0.8;
                this.ctx.fill();
            }
        }

        this.ctx.globalAlpha = 1.0;
    }

    /**
     * Get the top-most visible keypoint Y position (for A-pose alignment).
     * Returns the Y coordinate of the nose (landmark 0) or highest visible point.
     * @param {Array} landmarks - Array of {x, y, visibility} objects
     * @returns {Object|null} {x, y} in normalized coordinates or null if no landmarks
     */
    getTopKeypoint(landmarks) {
        if (!landmarks || landmarks.length === 0) return null;

        // Prefer nose (landmark 0) as it's the top of the tracked body
        const nose = landmarks[0];
        if (nose && nose.visibility >= this.visibilityThreshold) {
            return { x: nose.x, y: nose.y };
        }

        // Fallback: find highest visible keypoint
        let topY = 1;
        let topX = 0.5;
        for (const lm of landmarks) {
            if (lm && lm.visibility >= this.visibilityThreshold && lm.y < topY) {
                topY = lm.y;
                topX = lm.x;
            }
        }
        return topY < 1 ? { x: topX, y: topY } : null;
    }
}
