/**
 * Text3DElement.js
 *
 * Creates 3D text geometry for anamorphic compositions.
 * Words float in space as physical objects.
 */

import * as THREE from 'three';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';

// Cache loaded fonts
const fontCache = new Map();

export class Text3DElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
    }

    /**
     * Load font and create 3D text mesh.
     * @returns {Promise<THREE.Mesh>} - The text mesh
     */
    async load() {
        // Get or load font
        const fontPath = this.config.fontPath ||
            'https://unpkg.com/three@0.160.0/examples/fonts/helvetiker_bold.typeface.json';

        let font = fontCache.get(fontPath);
        if (!font) {
            font = await this.loadFont(fontPath);
            fontCache.set(fontPath, font);
        }

        // Create text geometry
        const text = this.config.text || 'DREAM';
        const geometry = new TextGeometry(text.toUpperCase(), {
            font: font,
            size: this.config.size || 0.5,
            height: this.config.depth || 0.1,
            curveSegments: 12,
            bevelEnabled: this.config.bevel !== false,
            bevelThickness: 0.02,
            bevelSize: 0.01,
            bevelOffset: 0,
            bevelSegments: 5
        });

        // Center the geometry
        geometry.computeBoundingBox();
        geometry.center();

        // Create material
        const color = this.config.color || 0xffffff;
        const material = this.config.unlit
            ? new THREE.MeshBasicMaterial({ color })
            : new THREE.MeshStandardMaterial({
                color,
                metalness: this.config.metalness || 0.3,
                roughness: this.config.roughness || 0.4,
                emissive: this.config.emissive || 0x000000,
                emissiveIntensity: this.config.emissiveIntensity || 0
            });

        this.mesh = new THREE.Mesh(geometry, material);

        // Store config
        this.mesh.userData.textConfig = this.config;

        return this.mesh;
    }

    /**
     * Load a font file.
     * @param {string} path - Font JSON path
     * @returns {Promise<Font>}
     */
    loadFont(path) {
        return new Promise((resolve, reject) => {
            const loader = new FontLoader();
            loader.load(path, resolve, undefined, reject);
        });
    }

    /**
     * Create simple sprite text (2D, always faces camera).
     * Faster alternative to 3D geometry.
     */
    static createSprite(text, config = {}) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        const fontSize = config.fontSize || 64;
        const fontFamily = config.fontFamily || 'Helvetica, Arial, sans-serif';
        const color = config.color || '#ffffff';

        // Measure text to size canvas
        context.font = `Bold ${fontSize}px ${fontFamily}`;
        const metrics = context.measureText(text.toUpperCase());
        const textWidth = metrics.width;

        canvas.width = Math.ceil(textWidth) + 20;
        canvas.height = fontSize + 20;

        // Draw text
        context.font = `Bold ${fontSize}px ${fontFamily}`;
        context.fillStyle = color;
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text.toUpperCase(), canvas.width / 2, canvas.height / 2);

        // Create sprite
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;

        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true
        });

        const sprite = new THREE.Sprite(material);

        // Scale based on canvas aspect
        const aspect = canvas.width / canvas.height;
        sprite.scale.set(aspect * (config.scale || 1), config.scale || 1, 1);

        return sprite;
    }

    /**
     * Get the mesh.
     */
    getObject() {
        return this.mesh;
    }
}
