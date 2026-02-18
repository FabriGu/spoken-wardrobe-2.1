/**
 * ImagePlaneElement.js
 *
 * Creates image planes for anamorphic compositions.
 * Used for found imagery, body frames, generated clothing images, etc.
 */

import * as THREE from 'three';

export class ImagePlaneElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
    }

    /**
     * Load the image and create a plane mesh.
     * @returns {Promise<THREE.Mesh>} - The image plane mesh
     */
    async load() {
        const texture = await new THREE.TextureLoader().loadAsync(this.config.path);

        // Calculate aspect ratio
        const aspect = texture.image.width / texture.image.height;

        // Create plane geometry (1 unit base height)
        const geometry = new THREE.PlaneGeometry(aspect, 1);

        // Create material with various options
        const materialConfig = {
            map: texture,
            side: THREE.DoubleSide,
            transparent: true
        };

        // Apply visual effects
        if (this.config.posterize) {
            // For posterization, we'd use a custom shader
            // For now, just increase contrast via tone mapping
            texture.encoding = THREE.sRGBEncoding;
        }

        if (this.config.opacity !== undefined) {
            materialConfig.opacity = this.config.opacity;
        }

        // Use basic material for unlit look, or standard for lit
        const MaterialClass = this.config.unlit
            ? THREE.MeshBasicMaterial
            : THREE.MeshStandardMaterial;

        const material = new MaterialClass(materialConfig);

        this.mesh = new THREE.Mesh(geometry, material);

        // Apply initial rotation (Z-axis rotation for 2D plane)
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }

        // Store config for reference
        this.mesh.userData.imageConfig = this.config;

        return this.mesh;
    }

    /**
     * Create from base64 data instead of URL.
     * @param {string} base64Data - Base64-encoded image data
     * @returns {Promise<THREE.Mesh>}
     */
    async loadFromBase64(base64Data) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => {
                const texture = new THREE.Texture(image);
                texture.needsUpdate = true;

                const aspect = image.width / image.height;
                const geometry = new THREE.PlaneGeometry(aspect, 1);

                const material = new THREE.MeshBasicMaterial({
                    map: texture,
                    side: THREE.DoubleSide,
                    transparent: true
                });

                this.mesh = new THREE.Mesh(geometry, material);
                resolve(this.mesh);
            };
            image.onerror = reject;
            image.src = `data:image/png;base64,${base64Data}`;
        });
    }

    /**
     * Get the mesh.
     */
    getObject() {
        return this.mesh;
    }
}
