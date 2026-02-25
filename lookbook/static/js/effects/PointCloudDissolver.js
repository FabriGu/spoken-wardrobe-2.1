/**
 * PointCloudDissolver.js
 *
 * Converts a mesh into a point cloud that can dissolve and reform.
 * Creates the signature "mesh breaking apart into particles" effect.
 *
 * Based on Three.js webgl_points_dynamic example.
 */

import * as THREE from 'three';

export class PointCloudDissolver {
    constructor(options = {}) {
        this.options = {
            // Particle appearance
            particleSize: options.particleSize || 0.02,
            particleColor: options.particleColor || 0xffffff,
            particleOpacity: options.particleOpacity || 0.8,

            // Dissolution behavior
            dissolveSpeed: options.dissolveSpeed || 1.0,
            reformSpeed: options.reformSpeed || 1.5,
            scatterRadius: options.scatterRadius || 2.0,
            turbulence: options.turbulence || 0.5,

            // Animation timing
            dissolveDuration: options.dissolveDuration || 2.0, // seconds
            reformDuration: options.reformDuration || 2.5,
            holdDuration: options.holdDuration || 1.0, // time to hold dissolved state

            // Visual style
            useAdditiveBlending: options.useAdditiveBlending !== false,
            sizeAttenuation: options.sizeAttenuation !== false,
            vertexColors: options.vertexColors || false,

            ...options
        };

        this.points = null;
        this.geometry = null;
        this.material = null;
        this.originalMesh = null;

        // Animation state
        this.state = 'solid'; // 'solid', 'dissolving', 'dissolved', 'reforming'
        this.progress = 0;
        this.time = 0;

        // Callbacks
        this.onDissolveComplete = null;
        this.onReformComplete = null;
    }

    /**
     * Create point cloud from a mesh
     * @param {THREE.Object3D} mesh - Source mesh or group
     * @returns {THREE.Points} - The point cloud object
     */
    createFromMesh(mesh) {
        this.originalMesh = mesh;

        // Collect all vertices from the mesh hierarchy
        const vertices = [];
        const colors = [];

        mesh.traverse((child) => {
            if (child.isMesh && child.geometry) {
                const geo = child.geometry;
                const positionAttr = geo.attributes.position;

                // Get world matrix for proper positioning
                child.updateWorldMatrix(true, false);
                const worldMatrix = child.matrixWorld;

                // Extract vertex colors if available
                const colorAttr = geo.attributes.color;
                const hasColors = colorAttr && this.options.vertexColors;

                for (let i = 0; i < positionAttr.count; i++) {
                    const vertex = new THREE.Vector3(
                        positionAttr.getX(i),
                        positionAttr.getY(i),
                        positionAttr.getZ(i)
                    );

                    // Transform to world space
                    vertex.applyMatrix4(worldMatrix);
                    vertices.push(vertex.x, vertex.y, vertex.z);

                    if (hasColors) {
                        colors.push(
                            colorAttr.getX(i),
                            colorAttr.getY(i),
                            colorAttr.getZ(i)
                        );
                    }
                }
            }
        });

        console.log(`[PointCloudDissolver] Created from ${vertices.length / 3} vertices`);

        // Create geometry
        this.geometry = new THREE.BufferGeometry();

        // Current positions (will be animated)
        const positions = new Float32Array(vertices);
        this.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        this.geometry.attributes.position.setUsage(THREE.DynamicDrawUsage);

        // Store initial positions (target for reformation)
        const initialPositions = new Float32Array(vertices);
        this.geometry.setAttribute('initialPosition', new THREE.BufferAttribute(initialPositions, 3));

        // Random values for dissolution direction
        const randomDirections = new Float32Array(vertices.length);
        for (let i = 0; i < randomDirections.length; i += 3) {
            // Random direction on unit sphere
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            randomDirections[i] = Math.sin(phi) * Math.cos(theta);
            randomDirections[i + 1] = Math.sin(phi) * Math.sin(theta);
            randomDirections[i + 2] = Math.cos(phi);
        }
        this.geometry.setAttribute('randomDir', new THREE.BufferAttribute(randomDirections, 3));

        // Random speed multipliers for organic feel
        const randomSpeeds = new Float32Array(vertices.length / 3);
        for (let i = 0; i < randomSpeeds.length; i++) {
            randomSpeeds[i] = 0.5 + Math.random();
        }
        this.geometry.setAttribute('randomSpeed', new THREE.BufferAttribute(randomSpeeds, 1));

        // Vertex colors if available
        if (colors.length > 0) {
            this.geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(colors), 3));
        }

        // Create material
        this.material = new THREE.PointsMaterial({
            size: this.options.particleSize,
            color: this.options.particleColor,
            transparent: true,
            opacity: this.options.particleOpacity,
            blending: this.options.useAdditiveBlending ? THREE.AdditiveBlending : THREE.NormalBlending,
            sizeAttenuation: this.options.sizeAttenuation,
            vertexColors: colors.length > 0 && this.options.vertexColors,
            depthWrite: false
        });

        // Create points object
        this.points = new THREE.Points(this.geometry, this.material);
        this.points.userData.dissolver = this;
        this.points.userData.update = (time, deltaTime) => this.update(deltaTime);

        return this.points;
    }

    /**
     * Start dissolution animation
     */
    dissolve() {
        if (this.state === 'solid' || this.state === 'reforming') {
            this.state = 'dissolving';
            this.progress = this.state === 'reforming' ? 1 - this.progress : 0;
            console.log('[PointCloudDissolver] Starting dissolution');
        }
    }

    /**
     * Start reformation animation
     */
    reform() {
        if (this.state === 'dissolved' || this.state === 'dissolving') {
            this.state = 'reforming';
            this.progress = this.state === 'dissolving' ? 1 - this.progress : 0;
            console.log('[PointCloudDissolver] Starting reformation');
        }
    }

    /**
     * Toggle between dissolved and solid states
     */
    toggle() {
        if (this.state === 'solid' || this.state === 'reforming') {
            this.dissolve();
        } else {
            this.reform();
        }
    }

    /**
     * Set dissolution progress directly (0 = solid, 1 = dissolved)
     */
    setProgress(progress) {
        this.progress = Math.max(0, Math.min(1, progress));
        this._updatePositions();
    }

    /**
     * Update animation
     */
    update(deltaTime) {
        this.time += deltaTime;

        if (this.state === 'dissolving') {
            this.progress += deltaTime / this.options.dissolveDuration;

            if (this.progress >= 1) {
                this.progress = 1;
                this.state = 'dissolved';
                if (this.onDissolveComplete) this.onDissolveComplete();
            }

            this._updatePositions();
        }
        else if (this.state === 'reforming') {
            this.progress += deltaTime / this.options.reformDuration;

            if (this.progress >= 1) {
                this.progress = 1;
                this.state = 'solid';
                if (this.onReformComplete) this.onReformComplete();
            }

            this._updatePositions();
        }
        else if (this.state === 'dissolved') {
            // Add subtle turbulence while dissolved
            this._addTurbulence(deltaTime);
        }
    }

    /**
     * Update particle positions based on progress
     */
    _updatePositions() {
        if (!this.geometry) return;

        const positions = this.geometry.attributes.position.array;
        const initial = this.geometry.attributes.initialPosition.array;
        const randomDir = this.geometry.attributes.randomDir.array;
        const randomSpeed = this.geometry.attributes.randomSpeed.array;

        const { scatterRadius, turbulence } = this.options;

        // Easing function for smooth animation
        const easeProgress = this._easeInOutCubic(this.progress);

        for (let i = 0; i < positions.length; i += 3) {
            const idx = i / 3;
            const speed = randomSpeed[idx];

            // Calculate dissolved position
            const dissolvedX = initial[i] + randomDir[i] * scatterRadius * speed;
            const dissolvedY = initial[i + 1] + randomDir[i + 1] * scatterRadius * speed + this.progress * 0.5; // Rise up
            const dissolvedZ = initial[i + 2] + randomDir[i + 2] * scatterRadius * speed;

            // Add turbulence
            const turbulenceScale = turbulence * easeProgress;
            const turbX = Math.sin(this.time * 2 + idx * 0.1) * turbulenceScale;
            const turbY = Math.cos(this.time * 1.5 + idx * 0.15) * turbulenceScale;
            const turbZ = Math.sin(this.time * 1.8 + idx * 0.12) * turbulenceScale;

            // Interpolate between initial and dissolved
            if (this.state === 'dissolving' || this.state === 'dissolved') {
                positions[i] = initial[i] + (dissolvedX - initial[i] + turbX) * easeProgress;
                positions[i + 1] = initial[i + 1] + (dissolvedY - initial[i + 1] + turbY) * easeProgress;
                positions[i + 2] = initial[i + 2] + (dissolvedZ - initial[i + 2] + turbZ) * easeProgress;
            } else {
                // Reforming - inverse interpolation
                const reformProgress = 1 - this._easeInOutCubic(1 - this.progress);
                positions[i] = dissolvedX + (initial[i] - dissolvedX) * reformProgress;
                positions[i + 1] = dissolvedY + (initial[i + 1] - dissolvedY) * reformProgress;
                positions[i + 2] = dissolvedZ + (initial[i + 2] - dissolvedZ) * reformProgress;
            }
        }

        this.geometry.attributes.position.needsUpdate = true;
    }

    /**
     * Add turbulence to dissolved particles
     */
    _addTurbulence(deltaTime) {
        if (!this.geometry) return;

        const positions = this.geometry.attributes.position.array;
        const { turbulence } = this.options;

        for (let i = 0; i < positions.length; i += 3) {
            const idx = i / 3;
            positions[i] += Math.sin(this.time * 2 + idx * 0.1) * turbulence * deltaTime;
            positions[i + 1] += Math.cos(this.time * 1.5 + idx * 0.15) * turbulence * deltaTime;
            positions[i + 2] += Math.sin(this.time * 1.8 + idx * 0.12) * turbulence * deltaTime;
        }

        this.geometry.attributes.position.needsUpdate = true;
    }

    /**
     * Easing function
     */
    _easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    /**
     * Set particle color
     */
    setColor(color) {
        if (this.material) {
            this.material.color.set(color);
        }
    }

    /**
     * Set particle size
     */
    setSize(size) {
        if (this.material) {
            this.material.size = size;
        }
    }

    /**
     * Set opacity
     */
    setOpacity(opacity) {
        if (this.material) {
            this.material.opacity = opacity;
        }
    }

    /**
     * Show/hide the original mesh (for smooth transitions)
     */
    setMeshVisible(visible) {
        if (this.originalMesh) {
            this.originalMesh.visible = visible;
        }
    }

    /**
     * Get current state
     */
    getState() {
        return this.state;
    }

    /**
     * Get current progress
     */
    getProgress() {
        return this.progress;
    }

    /**
     * Dispose resources
     */
    dispose() {
        if (this.geometry) {
            this.geometry.dispose();
        }
        if (this.material) {
            this.material.dispose();
        }
    }
}

export default PointCloudDissolver;
