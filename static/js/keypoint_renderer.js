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
     */
    render(landmarks) {
        if (!landmarks || landmarks.length === 0) {
            this.clear();
            return;
        }

        this._resizeCanvas();
        this.clear();

        const w = this.canvas.width;
        const h = this.canvas.height;

        // Draw connections first (so keypoints are on top)
        this._drawConnections(landmarks, w, h);

        // Draw keypoints
        this._drawKeypoints(landmarks, w, h);
    }

    /**
     * Draw skeleton connections.
     * @private
     */
    _drawConnections(landmarks, w, h) {
        this.ctx.strokeStyle = this.colors.secondary;
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';

        for (const [startIdx, endIdx] of this.connections) {
            const start = landmarks[startIdx];
            const end = landmarks[endIdx];

            if (!start || !end) continue;
            if (start.visibility < this.visibilityThreshold) continue;
            if (end.visibility < this.visibilityThreshold) continue;

            // Scale normalized [0-1] coordinates to canvas pixels
            const x1 = start.x * w;
            const y1 = start.y * h;
            const x2 = end.x * w;
            const y2 = end.y * h;

            // Draw glow effect (wider, lighter line behind)
            this.ctx.strokeStyle = this.colors.light;
            this.ctx.lineWidth = 4;
            this.ctx.globalAlpha = 0.3;
            this.ctx.beginPath();
            this.ctx.moveTo(x1, y1);
            this.ctx.lineTo(x2, y2);
            this.ctx.stroke();

            // Draw main line
            this.ctx.strokeStyle = this.colors.secondary;
            this.ctx.lineWidth = 2;
            this.ctx.globalAlpha = 1.0;
            this.ctx.beginPath();
            this.ctx.moveTo(x1, y1);
            this.ctx.lineTo(x2, y2);
            this.ctx.stroke();
        }
    }

    /**
     * Draw keypoint dots.
     * @private
     */
    _drawKeypoints(landmarks, w, h) {
        for (let i = 0; i < landmarks.length; i++) {
            const lm = landmarks[i];
            if (!lm || lm.visibility < this.visibilityThreshold) continue;

            // Scale normalized [0-1] coordinates to canvas pixels
            const x = lm.x * w;
            const y = lm.y * h;

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
}
