/**
 * Act 1: The Dream - Wireframe Runway Scene
 *
 * A minimalist Three.js scene showing:
 * - Wireframe runway geometry extending into the distance
 * - User's 2D silhouette (via BodyPix) walking down the runway
 * - Speech capture UI overlay
 */

import * as THREE from 'three';

export class Act1Runway {
    constructor(canvasId = 'runway-canvas') {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas #${canvasId} not found`);
        }

        // Three.js core
        this.scene = null;
        this.camera = null;
        this.renderer = null;

        // Scene objects
        this.runway = null;
        this.silhouettePlane = null;
        this.silhouetteTexture = null;

        // BodyPix
        this.bodyPixModel = null;
        this.bodyPixReady = false;

        // Camera feed
        this.videoElement = null;
        this.silhouetteCanvas = null;
        this.silhouetteCtx = null;

        // Animation state
        this.isRunning = false;
        this.animationId = null;
        this.walkProgress = 0;
        this.walkSpeed = 0.001;

        // Callbacks
        this.onComplete = null;

        console.log('[Act1Runway] Created');
    }

    /**
     * Initialize the runway scene
     */
    async init(videoElement) {
        this.videoElement = videoElement;

        // Create silhouette canvas
        this.silhouetteCanvas = document.createElement('canvas');
        this.silhouetteCanvas.width = 512;
        this.silhouetteCanvas.height = 512;
        this.silhouetteCtx = this.silhouetteCanvas.getContext('2d');

        // Setup Three.js
        this._setupThreeJS();
        this._createRunway();
        this._createSilhouette();

        // Load BodyPix
        await this._loadBodyPix();

        // Handle resize
        window.addEventListener('resize', () => this._onResize());

        console.log('[Act1Runway] Initialized');
    }

    /**
     * Setup Three.js renderer, scene, camera
     */
    _setupThreeJS() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x000000);

        // Camera - perspective looking down the runway
        const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
        this.camera.position.set(0, 2, 8);
        this.camera.lookAt(0, 1.5, -20);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true
        });
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    }

    /**
     * Create wireframe runway geometry
     */
    _createRunway() {
        const runwayGroup = new THREE.Group();

        // Main runway surface (wireframe grid)
        const runwayGeom = new THREE.PlaneGeometry(6, 60, 12, 120);
        const runwayMat = new THREE.MeshBasicMaterial({
            color: 0x9b59b6, // Purple accent
            wireframe: true,
            transparent: true,
            opacity: 0.4
        });
        const runwayMesh = new THREE.Mesh(runwayGeom, runwayMat);
        runwayMesh.rotation.x = -Math.PI / 2;
        runwayMesh.position.set(0, 0, -25);
        runwayGroup.add(runwayMesh);

        // Side rails
        const railGeom = new THREE.BoxGeometry(0.1, 0.5, 60);
        const railMat = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            wireframe: true,
            transparent: true,
            opacity: 0.3
        });

        const leftRail = new THREE.Mesh(railGeom, railMat);
        leftRail.position.set(-3, 0.25, -25);
        runwayGroup.add(leftRail);

        const rightRail = new THREE.Mesh(railGeom, railMat);
        rightRail.position.set(3, 0.25, -25);
        runwayGroup.add(rightRail);

        // Vertical posts along sides
        const postGeom = new THREE.BoxGeometry(0.1, 3, 0.1);
        const postMat = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            wireframe: true,
            transparent: true,
            opacity: 0.2
        });

        for (let z = 0; z > -50; z -= 5) {
            const leftPost = new THREE.Mesh(postGeom, postMat);
            leftPost.position.set(-3, 1.5, z);
            runwayGroup.add(leftPost);

            const rightPost = new THREE.Mesh(postGeom, postMat);
            rightPost.position.set(3, 1.5, z);
            runwayGroup.add(rightPost);
        }

        // Horizon line
        const horizonGeom = new THREE.PlaneGeometry(20, 0.02);
        const horizonMat = new THREE.MeshBasicMaterial({
            color: 0x9b59b6,
            transparent: true,
            opacity: 0.6
        });
        const horizon = new THREE.Mesh(horizonGeom, horizonMat);
        horizon.position.set(0, 2, -55);
        runwayGroup.add(horizon);

        this.runway = runwayGroup;
        this.scene.add(runwayGroup);
    }

    /**
     * Create silhouette plane (user's 2D shape)
     */
    _createSilhouette() {
        // Texture from silhouette canvas
        this.silhouetteTexture = new THREE.CanvasTexture(this.silhouetteCanvas);
        this.silhouetteTexture.minFilter = THREE.LinearFilter;
        this.silhouetteTexture.magFilter = THREE.LinearFilter;

        // Plane geometry for silhouette
        const planeGeom = new THREE.PlaneGeometry(2, 3);
        const planeMat = new THREE.MeshBasicMaterial({
            map: this.silhouetteTexture,
            transparent: true,
            side: THREE.DoubleSide
        });

        this.silhouettePlane = new THREE.Mesh(planeGeom, planeMat);
        this.silhouettePlane.position.set(0, 1.5, 0);
        this.scene.add(this.silhouettePlane);
    }

    /**
     * Load BodyPix model
     */
    async _loadBodyPix() {
        if (typeof bodyPix === 'undefined') {
            console.warn('[Act1Runway] BodyPix not loaded, waiting...');
            // Wait for BodyPix to load
            await new Promise(resolve => {
                const check = setInterval(() => {
                    if (typeof bodyPix !== 'undefined') {
                        clearInterval(check);
                        resolve();
                    }
                }, 100);
            });
        }

        console.log('[Act1Runway] Loading BodyPix model...');
        this.bodyPixModel = await bodyPix.load({
            architecture: 'MobileNetV1',
            outputStride: 16,
            multiplier: 0.75,
            quantBytes: 2
        });
        this.bodyPixReady = true;
        console.log('[Act1Runway] BodyPix ready');
    }

    /**
     * Start the runway experience
     */
    start() {
        if (this.isRunning) return;

        this.isRunning = true;
        this.walkProgress = 0;
        this._animate();
        console.log('[Act1Runway] Started');
    }

    /**
     * Stop the runway
     */
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        console.log('[Act1Runway] Stopped');
    }

    /**
     * Animation loop
     */
    _animate() {
        if (!this.isRunning) return;

        // Update silhouette from camera
        this._updateSilhouette();

        // Animate walk (silhouette moves toward camera)
        this.walkProgress += this.walkSpeed;
        const z = THREE.MathUtils.lerp(-30, 5, Math.min(this.walkProgress, 1));
        this.silhouettePlane.position.z = z;

        // Scale up as approaching
        const scale = THREE.MathUtils.lerp(0.3, 1.2, Math.min(this.walkProgress, 1));
        this.silhouettePlane.scale.set(scale, scale, 1);

        // Render
        this.renderer.render(this.scene, this.camera);

        this.animationId = requestAnimationFrame(() => this._animate());
    }

    /**
     * Update silhouette texture from camera + BodyPix
     */
    async _updateSilhouette() {
        if (!this.bodyPixReady || !this.videoElement || this.videoElement.readyState < 2) {
            return;
        }

        try {
            // Segment the person
            const segmentation = await this.bodyPixModel.segmentPerson(this.videoElement, {
                flipHorizontal: false,
                internalResolution: 'medium',
                segmentationThreshold: 0.7
            });

            // Draw to silhouette canvas
            const ctx = this.silhouetteCtx;
            const w = this.silhouetteCanvas.width;
            const h = this.silhouetteCanvas.height;

            // Clear
            ctx.clearRect(0, 0, w, h);

            // Scale video to canvas
            const vw = this.videoElement.videoWidth;
            const vh = this.videoElement.videoHeight;
            const scale = Math.min(w / vw, h / vh);
            const sw = vw * scale;
            const sh = vh * scale;
            const sx = (w - sw) / 2;
            const sy = (h - sh) / 2;

            // Draw video frame
            ctx.drawImage(this.videoElement, sx, sy, sw, sh);

            // Get image data
            const imageData = ctx.getImageData(0, 0, w, h);
            const data = imageData.data;

            // Create silhouette (white fill, transparent background)
            const maskData = segmentation.data;
            const maskW = segmentation.width;
            const maskH = segmentation.height;

            for (let y = 0; y < h; y++) {
                for (let x = 0; x < w; x++) {
                    const idx = (y * w + x) * 4;

                    // Map canvas coords to mask coords
                    const mx = Math.floor((x - sx) / scale);
                    const my = Math.floor((y - sy) / scale);

                    let isPerson = false;
                    if (mx >= 0 && mx < maskW && my >= 0 && my < maskH) {
                        isPerson = maskData[my * maskW + mx] === 1;
                    }

                    if (isPerson) {
                        // White silhouette
                        data[idx] = 255;
                        data[idx + 1] = 255;
                        data[idx + 2] = 255;
                        data[idx + 3] = 255;
                    } else {
                        // Transparent
                        data[idx + 3] = 0;
                    }
                }
            }

            ctx.putImageData(imageData, 0, 0);

            // Update Three.js texture
            this.silhouetteTexture.needsUpdate = true;

        } catch (error) {
            // Silently fail on segmentation errors
        }
    }

    /**
     * Handle window resize
     */
    _onResize() {
        if (!this.renderer || !this.camera) return;

        const width = this.canvas.clientWidth;
        const height = this.canvas.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    /**
     * Cleanup
     */
    dispose() {
        this.stop();

        if (this.renderer) {
            this.renderer.dispose();
        }

        if (this.scene) {
            this.scene.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach(m => m.dispose());
                    } else {
                        obj.material.dispose();
                    }
                }
            });
        }

        window.removeEventListener('resize', this._onResize);
        console.log('[Act1Runway] Disposed');
    }
}
