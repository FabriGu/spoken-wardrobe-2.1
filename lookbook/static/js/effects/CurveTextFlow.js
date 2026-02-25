/**
 * CurveTextFlow.js
 *
 * Animates text along 3D curves orbiting around a mesh.
 * Creates the "words becoming form" effect where transcription
 * words flow along smooth bezier paths.
 *
 * Based on Three.js webgl_modifier_curve_instanced example.
 */

import * as THREE from 'three';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';

// Font cache shared across instances
const fontCache = new Map();

export class CurveTextFlow {
    constructor(options = {}) {
        this.options = {
            // Text appearance
            fontSize: options.fontSize || 0.15,
            fontDepth: options.fontDepth || 0.02,
            fontPath: options.fontPath ||
                'https://unpkg.com/three@0.160.0/examples/fonts/helvetiker_bold.typeface.json',
            textColor: options.textColor || 0xffffff,
            emissive: options.emissive || 0x222222,
            emissiveIntensity: options.emissiveIntensity || 0.3,

            // Curve configuration
            curveRadius: options.curveRadius || 1.5,
            curveHeight: options.curveHeight || 1.0,
            curveSegments: options.curveSegments || 64,
            numCurves: options.numCurves || 3,
            curveVariation: options.curveVariation || 0.3,

            // Animation
            orbitSpeed: options.orbitSpeed || 0.1,
            wordSpacing: options.wordSpacing || 0.3,
            staggerDelay: options.staggerDelay || 0.15,

            // Visual style
            useSprites: options.useSprites !== false, // Sprites are faster
            fadeInDuration: options.fadeInDuration || 1.0,

            ...options
        };

        this.group = new THREE.Group();
        this.curves = [];
        this.textObjects = [];
        this.font = null;
        this.time = 0;
        this.isPlaying = true;

        // Animation state per word
        this.wordStates = [];

        // Center point for orbiting
        this.centerPoint = new THREE.Vector3(0, 0, 0);
    }

    /**
     * Initialize with words and create curves
     * @param {string[]} words - Array of words to animate
     * @param {THREE.Vector3} center - Center point for orbiting
     * @returns {Promise<THREE.Group>} - The group containing all elements
     */
    async init(words, center = new THREE.Vector3(0, 0, 0)) {
        this.centerPoint.copy(center);
        this.words = words.filter(w => w.trim().length > 0);

        if (this.words.length === 0) {
            console.warn('[CurveTextFlow] No words provided');
            return this.group;
        }

        // Load font
        await this._loadFont();

        // Generate orbital curves
        this._generateCurves();

        // Create text for each word
        await this._createTextObjects();

        // Setup update function for animation loop
        this.group.userData.update = (time, deltaTime) => this.update(deltaTime);
        this.group.userData.curveTextFlow = this;

        console.log(`[CurveTextFlow] Initialized with ${this.words.length} words on ${this.curves.length} curves`);

        return this.group;
    }

    /**
     * Load the font
     */
    async _loadFont() {
        const { fontPath } = this.options;

        if (fontCache.has(fontPath)) {
            this.font = fontCache.get(fontPath);
            return;
        }

        return new Promise((resolve, reject) => {
            const loader = new FontLoader();
            loader.load(
                fontPath,
                (font) => {
                    this.font = font;
                    fontCache.set(fontPath, font);
                    resolve();
                },
                undefined,
                reject
            );
        });
    }

    /**
     * Generate smooth closed curves for text to follow
     */
    _generateCurves() {
        const { numCurves, curveRadius, curveHeight, curveVariation, curveSegments } = this.options;

        for (let c = 0; c < numCurves; c++) {
            // Create points for a wavy orbital path
            const points = [];
            const numPoints = 8;
            const angleOffset = (c / numCurves) * Math.PI * 2 / numCurves;
            const heightOffset = (c - numCurves / 2) * (curveHeight / numCurves);

            for (let i = 0; i < numPoints; i++) {
                const angle = (i / numPoints) * Math.PI * 2 + angleOffset;

                // Add variation to radius and height
                const radiusVar = curveRadius + (Math.sin(angle * 3 + c) * curveVariation);
                const heightVar = heightOffset + Math.sin(angle * 2 + c * 0.5) * curveVariation * 0.5;

                points.push(new THREE.Vector3(
                    this.centerPoint.x + Math.cos(angle) * radiusVar,
                    this.centerPoint.y + heightVar,
                    this.centerPoint.z + Math.sin(angle) * radiusVar
                ));
            }

            // Create smooth closed curve
            const curve = new THREE.CatmullRomCurve3(points);
            curve.curveType = 'centripetal';
            curve.closed = true;
            curve.tension = 0.5;

            this.curves.push(curve);

            // Visualize curve (debug, can be removed)
            if (this.options.showCurves) {
                const curvePoints = curve.getPoints(curveSegments);
                const curveGeometry = new THREE.BufferGeometry().setFromPoints(curvePoints);
                const curveMaterial = new THREE.LineBasicMaterial({
                    color: 0x444444,
                    transparent: true,
                    opacity: 0.3
                });
                const curveLine = new THREE.Line(curveGeometry, curveMaterial);
                this.group.add(curveLine);
            }
        }
    }

    /**
     * Create text objects for each word
     */
    async _createTextObjects() {
        const { useSprites, fontSize, fontDepth, textColor, emissive, emissiveIntensity, staggerDelay } = this.options;

        for (let i = 0; i < this.words.length; i++) {
            const word = this.words[i];
            const curveIndex = i % this.curves.length;
            const curve = this.curves[curveIndex];

            let textObj;

            if (useSprites) {
                textObj = this._createTextSprite(word);
            } else {
                textObj = this._createText3D(word);
            }

            // Initial position on curve
            const t = (i / this.words.length) % 1;
            const point = curve.getPointAt(t);
            textObj.position.copy(point);

            // Store state for animation
            this.wordStates.push({
                object: textObj,
                curveIndex: curveIndex,
                t: t,
                speedMultiplier: 0.8 + Math.random() * 0.4, // Slight speed variation
                fadeProgress: 0,
                delay: i * staggerDelay
            });

            // Start invisible for fade-in
            textObj.material.opacity = 0;
            textObj.material.transparent = true;

            this.textObjects.push(textObj);
            this.group.add(textObj);
        }
    }

    /**
     * Create a sprite-based text (2D, always faces camera)
     */
    _createTextSprite(word) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        const fontSize = 64;
        const fontFamily = 'Helvetica, Arial, sans-serif';

        // Measure text
        context.font = `Bold ${fontSize}px ${fontFamily}`;
        const metrics = context.measureText(word.toUpperCase());
        const textWidth = metrics.width;

        // Size canvas
        canvas.width = Math.ceil(textWidth) + 40;
        canvas.height = fontSize + 40;

        // Draw text with glow effect
        context.font = `Bold ${fontSize}px ${fontFamily}`;
        context.textAlign = 'center';
        context.textBaseline = 'middle';

        // Glow
        context.shadowColor = '#ffffff';
        context.shadowBlur = 15;
        context.fillStyle = '#ffffff';

        context.fillText(word.toUpperCase(), canvas.width / 2, canvas.height / 2);

        // Create texture and sprite
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;

        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            opacity: 1,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });

        const sprite = new THREE.Sprite(material);

        // Scale based on desired size
        const aspect = canvas.width / canvas.height;
        const scale = this.options.fontSize * 2;
        sprite.scale.set(aspect * scale, scale, 1);

        sprite.userData.word = word;

        return sprite;
    }

    /**
     * Create 3D text geometry
     */
    _createText3D(word) {
        const { fontSize, fontDepth, textColor, emissive, emissiveIntensity } = this.options;

        const geometry = new TextGeometry(word.toUpperCase(), {
            font: this.font,
            size: fontSize,
            height: fontDepth,
            curveSegments: 8,
            bevelEnabled: true,
            bevelThickness: 0.005,
            bevelSize: 0.003,
            bevelSegments: 3
        });

        geometry.computeBoundingBox();
        geometry.center();

        const material = new THREE.MeshStandardMaterial({
            color: textColor,
            emissive: emissive,
            emissiveIntensity: emissiveIntensity,
            metalness: 0.1,
            roughness: 0.3,
            transparent: true,
            opacity: 1
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.userData.word = word;

        return mesh;
    }

    /**
     * Update animation
     */
    update(deltaTime) {
        if (!this.isPlaying) return;

        this.time += deltaTime;

        const { orbitSpeed, fadeInDuration } = this.options;

        for (const state of this.wordStates) {
            // Wait for stagger delay
            if (this.time < state.delay) continue;

            const activeTime = this.time - state.delay;

            // Fade in
            if (state.fadeProgress < 1) {
                state.fadeProgress = Math.min(1, activeTime / fadeInDuration);
                state.object.material.opacity = this._easeOutCubic(state.fadeProgress);
            }

            // Move along curve
            state.t += deltaTime * orbitSpeed * state.speedMultiplier;
            state.t = state.t % 1;

            const curve = this.curves[state.curveIndex];
            const point = curve.getPointAt(state.t);

            // Smooth position update
            state.object.position.lerp(point, 0.1);

            // Orient text to face outward from center (for 3D text)
            if (!this.options.useSprites) {
                const tangent = curve.getTangentAt(state.t);
                state.object.lookAt(
                    point.x + tangent.x,
                    point.y + tangent.y,
                    point.z + tangent.z
                );
            }
        }
    }

    /**
     * Set the center point for orbiting
     */
    setCenter(center) {
        const offset = new THREE.Vector3().subVectors(center, this.centerPoint);
        this.centerPoint.copy(center);

        // Update all curve points
        for (const curve of this.curves) {
            for (const point of curve.points) {
                point.add(offset);
            }
        }
    }

    /**
     * Set orbit speed
     */
    setSpeed(speed) {
        this.options.orbitSpeed = speed;
    }

    /**
     * Pause animation
     */
    pause() {
        this.isPlaying = false;
    }

    /**
     * Resume animation
     */
    play() {
        this.isPlaying = true;
    }

    /**
     * Fade out all text
     */
    fadeOut(duration = 1.0) {
        const startOpacities = this.wordStates.map(s => s.object.material.opacity);
        const startTime = this.time;

        return new Promise((resolve) => {
            const fadeUpdate = () => {
                const elapsed = this.time - startTime;
                const progress = Math.min(1, elapsed / duration);

                for (let i = 0; i < this.wordStates.length; i++) {
                    this.wordStates[i].object.material.opacity =
                        startOpacities[i] * (1 - this._easeInCubic(progress));
                }

                if (progress < 1) {
                    requestAnimationFrame(fadeUpdate);
                } else {
                    resolve();
                }
            };
            fadeUpdate();
        });
    }

    /**
     * Converge all words toward a point (mesh transformation effect)
     */
    convergeToPoint(target, duration = 2.0) {
        const startPositions = this.textObjects.map(obj => obj.position.clone());
        const startTime = this.time;

        return new Promise((resolve) => {
            const convergeUpdate = () => {
                const elapsed = this.time - startTime;
                const progress = Math.min(1, elapsed / duration);
                const easedProgress = this._easeInOutCubic(progress);

                for (let i = 0; i < this.textObjects.length; i++) {
                    const obj = this.textObjects[i];
                    obj.position.lerpVectors(startPositions[i], target, easedProgress);

                    // Scale down as we converge
                    const scale = 1 - easedProgress * 0.9;
                    if (obj.isSprite) {
                        obj.scale.multiplyScalar(0.99);
                    } else {
                        obj.scale.setScalar(scale);
                    }

                    // Fade out near the end
                    if (progress > 0.7) {
                        obj.material.opacity = 1 - (progress - 0.7) / 0.3;
                    }
                }

                if (progress < 1) {
                    requestAnimationFrame(convergeUpdate);
                } else {
                    resolve();
                }
            };
            convergeUpdate();
        });
    }

    /**
     * Get the group containing all text objects
     */
    getObject() {
        return this.group;
    }

    /**
     * Easing functions
     */
    _easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    _easeInCubic(t) {
        return t * t * t;
    }

    _easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    /**
     * Dispose all resources
     */
    dispose() {
        for (const obj of this.textObjects) {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        }

        this.textObjects = [];
        this.wordStates = [];
        this.curves = [];
    }
}

export default CurveTextFlow;
