/**
 * ScreenshotCapture.js
 *
 * High-resolution screenshot capture for print output.
 * Captures the anamorphic view as a print-ready PNG.
 */

import * as THREE from 'three';

export class ScreenshotCapture {
    constructor(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;
    }

    /**
     * Capture a high-resolution screenshot.
     *
     * @param {number} width - Output width in pixels
     * @param {number} height - Output height in pixels
     * @param {string} filename - Optional filename (auto-generated if not provided)
     * @returns {string} - Data URL of the captured image
     */
    captureHighRes(width = 4096, height = 4096, filename = null) {
        console.log(`[ScreenshotCapture] Capturing at ${width}x${height}`);

        // Store original settings
        const originalSize = this.renderer.getSize(new THREE.Vector2());
        const originalPixelRatio = this.renderer.getPixelRatio();
        const originalAspect = this.camera.aspect;

        try {
            // Configure for high-res render
            this.renderer.setSize(width, height);
            this.renderer.setPixelRatio(1);

            // Update camera aspect
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();

            // Render
            this.renderer.render(this.scene, this.camera);

            // Capture as data URL
            const dataURL = this.renderer.domElement.toDataURL('image/png');

            // Trigger download
            const downloadFilename = filename ||
                `dreamwear_lookbook_${Date.now()}.png`;

            this.triggerDownload(dataURL, downloadFilename);

            console.log('[ScreenshotCapture] Capture complete');
            return dataURL;

        } finally {
            // Restore original settings
            this.renderer.setSize(originalSize.x, originalSize.y);
            this.renderer.setPixelRatio(originalPixelRatio);
            this.camera.aspect = originalAspect;
            this.camera.updateProjectionMatrix();
        }
    }

    /**
     * Capture at various print-friendly resolutions.
     */
    captureForPrint(dpi = 300, widthInches = 8.5, heightInches = 11) {
        const width = Math.round(widthInches * dpi);
        const height = Math.round(heightInches * dpi);
        return this.captureHighRes(width, height);
    }

    /**
     * Capture square format (ideal for lookbook pages).
     */
    captureSquare(size = 4096) {
        return this.captureHighRes(size, size);
    }

    /**
     * Trigger browser download of an image.
     */
    triggerDownload(dataURL, filename) {
        const link = document.createElement('a');
        link.download = filename;
        link.href = dataURL;
        link.style.display = 'none';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /**
     * Capture and return as Blob (for programmatic use).
     */
    async captureAsBlob(width = 4096, height = 4096) {
        // Store original settings
        const originalSize = this.renderer.getSize(new THREE.Vector2());
        const originalPixelRatio = this.renderer.getPixelRatio();
        const originalAspect = this.camera.aspect;

        try {
            // Configure for high-res render
            this.renderer.setSize(width, height);
            this.renderer.setPixelRatio(1);

            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();

            // Render
            this.renderer.render(this.scene, this.camera);

            // Get as blob
            return new Promise((resolve) => {
                this.renderer.domElement.toBlob(resolve, 'image/png');
            });

        } finally {
            // Restore original settings
            this.renderer.setSize(originalSize.x, originalSize.y);
            this.renderer.setPixelRatio(originalPixelRatio);
            this.camera.aspect = originalAspect;
            this.camera.updateProjectionMatrix();
        }
    }
}
