/**
 * Era 1: Roberts Edge Detection (1963)
 *
 * The first edge detection algorithm, developed by Lawrence Roberts.
 * Uses a 2x2 cross operator to detect edges.
 *
 * AESTHETIC:
 * - Green edges on black (CRT phosphor look)
 * - Low resolution (authentic 1960s feel)
 * - Visible scanlines
 */

export class Era1Roberts {
    constructor() {
        this.name = 'Roberts Edge (1963)';

        // Downscale resolution for authentic 1960s feel
        this.targetWidth = 160;
        this.targetHeight = 120;

        // Offscreen canvases for processing
        this.smallCanvas = document.createElement('canvas');
        this.smallCanvas.width = this.targetWidth;
        this.smallCanvas.height = this.targetHeight;
        this.smallCtx = this.smallCanvas.getContext('2d', { willReadFrequently: true });

        // Edge detection threshold
        this.threshold = 30;

        // Green CRT phosphor color
        this.edgeColor = { r: 0, g: 255, b: 0 };
    }

    /**
     * Process a frame through Roberts edge detection
     * @param {ImageData} sourceImageData - Source image data
     * @param {HTMLCanvasElement} destCanvas - Destination canvas
     * @param {CanvasRenderingContext2D} destCtx - Destination context
     * @param {number} timestamp - Frame timestamp
     */
    processFrame(sourceImageData, destCanvas, destCtx, timestamp) {
        const srcWidth = sourceImageData.width;
        const srcHeight = sourceImageData.height;

        // Step 1: Downscale source to small canvas
        // Create temp canvas from imageData
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = srcWidth;
        tempCanvas.height = srcHeight;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.putImageData(sourceImageData, 0, 0);

        // Draw scaled down
        this.smallCtx.drawImage(tempCanvas, 0, 0, this.targetWidth, this.targetHeight);

        // Step 2: Get small image data and convert to grayscale
        const smallData = this.smallCtx.getImageData(0, 0, this.targetWidth, this.targetHeight);
        const gray = this._toGrayscale(smallData);

        // Step 3: Apply Roberts cross operator
        const edges = this._robertsCross(gray, this.targetWidth, this.targetHeight);

        // Step 4: Create output image (green edges on black)
        const output = this._createOutputImage(edges, this.targetWidth, this.targetHeight);

        // Step 5: Put back to small canvas
        this.smallCtx.putImageData(output, 0, 0);

        // Step 6: Draw scaled up to destination with nearest-neighbor (pixelated)
        destCtx.imageSmoothingEnabled = false;
        destCtx.fillStyle = '#000';
        destCtx.fillRect(0, 0, destCanvas.width, destCanvas.height);

        // Calculate centered position preserving aspect ratio
        const srcAspect = this.targetWidth / this.targetHeight;
        const dstAspect = destCanvas.width / destCanvas.height;
        let drawW, drawH, drawX, drawY;

        if (srcAspect > dstAspect) {
            drawW = destCanvas.width;
            drawH = destCanvas.width / srcAspect;
            drawX = 0;
            drawY = (destCanvas.height - drawH) / 2;
        } else {
            drawH = destCanvas.height;
            drawW = destCanvas.height * srcAspect;
            drawX = (destCanvas.width - drawW) / 2;
            drawY = 0;
        }

        destCtx.drawImage(this.smallCanvas, drawX, drawY, drawW, drawH);

        // Step 7: Add scanlines
        this._addScanlines(destCtx, destCanvas.width, destCanvas.height, drawY, drawH);
    }

    /**
     * Convert image data to grayscale array
     */
    _toGrayscale(imageData) {
        const data = imageData.data;
        const gray = new Uint8Array(data.length / 4);

        for (let i = 0; i < gray.length; i++) {
            const idx = i * 4;
            // Standard luminance formula
            gray[i] = Math.round(0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2]);
        }

        return gray;
    }

    /**
     * Apply Roberts cross edge detection operator
     * Roberts uses two 2x2 kernels:
     * Gx = [+1  0]    Gy = [0  +1]
     *      [0  -1]         [-1  0]
     */
    _robertsCross(gray, width, height) {
        const edges = new Uint8Array(width * height);

        for (let y = 0; y < height - 1; y++) {
            for (let x = 0; x < width - 1; x++) {
                const idx = y * width + x;

                // Get 2x2 pixel neighborhood
                const p00 = gray[idx];
                const p10 = gray[idx + 1];
                const p01 = gray[idx + width];
                const p11 = gray[idx + width + 1];

                // Roberts cross gradients
                const gx = p00 - p11;
                const gy = p10 - p01;

                // Gradient magnitude
                const magnitude = Math.sqrt(gx * gx + gy * gy);

                // Threshold to binary edge
                edges[idx] = magnitude > this.threshold ? 255 : 0;
            }
        }

        return edges;
    }

    /**
     * Create output image with green edges on black background
     */
    _createOutputImage(edges, width, height) {
        const output = new ImageData(width, height);
        const data = output.data;

        for (let i = 0; i < edges.length; i++) {
            const idx = i * 4;
            const edge = edges[i];

            if (edge > 0) {
                // Green CRT phosphor color
                data[idx] = this.edgeColor.r;
                data[idx + 1] = this.edgeColor.g;
                data[idx + 2] = this.edgeColor.b;
                data[idx + 3] = 255;
            } else {
                // Black background
                data[idx] = 0;
                data[idx + 1] = 0;
                data[idx + 2] = 0;
                data[idx + 3] = 255;
            }
        }

        return output;
    }

    /**
     * Add CRT scanlines effect
     */
    _addScanlines(ctx, width, height, startY, drawHeight) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';

        // Draw horizontal lines every 3 pixels
        const lineSpacing = 3;
        for (let y = startY; y < startY + drawHeight; y += lineSpacing) {
            ctx.fillRect(0, y, width, 1);
        }
    }
}
