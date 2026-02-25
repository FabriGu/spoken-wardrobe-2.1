/**
 * ImagePlaneElement.js
 *
 * Enhanced image planes with URL loading and shader effects support.
 * Handles both local files and on-demand web images.
 */

import * as THREE from 'three';

export class ImagePlaneElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
    }

    /**
     * Load the image and create a plane mesh.
     * Supports both local paths and URLs.
     * @returns {Promise<THREE.Mesh>}
     */
    async load() {
        const path = this.config.path;
        
        // Check if it's a URL or local path
        const isUrl = path.startsWith('http://') || path.startsWith('https://');
        
        const texture = await this.loadTexture(path, isUrl);
        
        if (!texture) {
            console.warn('[ImagePlaneElement] Failed to load texture:', path);
            // Create placeholder
            return this.createPlaceholder();
        }

        // Calculate aspect ratio
        const aspect = texture.image ? (texture.image.width / texture.image.height) : 1;

        // Create plane geometry
        const geometry = new THREE.PlaneGeometry(aspect, 1);

        // Create material
        const materialConfig = {
            map: texture,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: this.config.opacity !== undefined ? this.config.opacity : 1.0
        };

        // Use basic material for unlit look, or standard for lit
        const MaterialClass = this.config.unlit
            ? THREE.MeshBasicMaterial
            : THREE.MeshStandardMaterial;

        const material = new MaterialClass(materialConfig);

        this.mesh = new THREE.Mesh(geometry, material);

        // Apply initial rotation
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }

        // Store config
        this.mesh.userData.imageConfig = this.config;
        
        // Add floating animation if configured
        if (this.config.animated !== false) {
            this.addFloatingAnimation();
        }

        return this.mesh;
    }

    /**
     * Load texture from path or URL
     */
    loadTexture(path, isUrl) {
        return new Promise((resolve) => {
            const loader = new THREE.TextureLoader();
            
            // Set crossOrigin for URLs
            if (isUrl || this.config.crossOrigin) {
                loader.setCrossOrigin('anonymous');
            }
            
            loader.load(
                path,
                (texture) => {
                    texture.colorSpace = THREE.SRGBColorSpace;
                    resolve(texture);
                },
                undefined, // onProgress
                (error) => {
                    console.warn('[ImagePlaneElement] Load failed:', path, error);
                    resolve(null);
                }
            );
        });
    }

    /**
     * Create placeholder when image fails to load
     */
    createPlaceholder() {
        const geometry = new THREE.PlaneGeometry(1, 1);
        const material = new THREE.MeshBasicMaterial({
            color: this.config.placeholderColor || 0x333333,
            transparent: true,
            opacity: (this.config.opacity || 0.5) * 0.5,
            side: THREE.DoubleSide
        });
        
        this.mesh = new THREE.Mesh(geometry, material);
        
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }
        
        return this.mesh;
    }

    /**
     * Add floating animation
     */
    addFloatingAnimation() {
        const floatSpeed = this.config.floatSpeed || 0.3 + Math.random() * 0.5;
        const floatAmp = this.config.floatAmplitude || 0.02 + Math.random() * 0.03;
        const rotSpeed = this.config.rotationSpeed || 0.1 + Math.random() * 0.3;
        
        const originalY = this.mesh.position.y;
        const originalRotZ = this.mesh.rotation.z;
        
        this.mesh.userData.update = (time) => {
            // Float
            this.mesh.position.y = originalY + Math.sin(time * floatSpeed) * floatAmp;
            
            // Gentle rotation drift
            this.mesh.rotation.z = originalRotZ + Math.sin(time * rotSpeed * 0.5) * 0.02;
        };
    }

    /**
     * Create from base64 data
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
     * Get the mesh
     */
    getObject() {
        return this.mesh;
    }
}

export default ImagePlaneElement;
