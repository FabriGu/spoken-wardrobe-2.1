/**
 * ImagePlaneElement.js
 *
 * Enhanced image planes with URL loading and shader effects support.
 * Handles both local files and on-demand web images.
 * Supports spotlight illumination and bob animations.
 */

import * as THREE from 'three';

export class ImagePlaneElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
        this.group = null;
        this.spotlight = null;
        this.originalY = 0;
    }

    /**
     * Load the image and create a plane mesh.
     * Supports both local paths and URLs.
     * @returns {Promise<THREE.Group>} - Returns a group containing the mesh and optional spotlight
     */
    async load() {
        const path = this.config.path;

        // Create group to hold mesh + spotlight
        this.group = new THREE.Group();

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

        // Use standard material when spotlight is enabled for proper lighting
        const useStandardMaterial = this.config.spotlight?.enabled || !this.config.unlit;
        const MaterialClass = useStandardMaterial
            ? THREE.MeshStandardMaterial
            : THREE.MeshBasicMaterial;

        const material = new MaterialClass(materialConfig);

        this.mesh = new THREE.Mesh(geometry, material);

        // Apply initial rotation
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }

        // Add mesh to group
        this.group.add(this.mesh);

        // Add spotlight if configured
        if (this.config.spotlight?.enabled) {
            this.addSpotlight();
        }

        // Store config and type
        this.group.userData.imageConfig = this.config;
        this.group.userData.type = 'image_plane';

        // Add animation (floating or bob)
        if (this.config.bobAnimation?.enabled) {
            this.addBobAnimation();
        } else if (this.config.animated !== false) {
            this.addFloatingAnimation();
        }

        return this.group;
    }

    /**
     * Add spotlight pointing at the image
     */
    addSpotlight() {
        const spotConfig = this.config.spotlight;

        // Create spotlight
        this.spotlight = new THREE.SpotLight(
            0xffffff,
            spotConfig.intensity || 0.4
        );
        this.spotlight.angle = Math.PI / 6;
        this.spotlight.penumbra = 0.5;
        this.spotlight.decay = 2;
        this.spotlight.distance = spotConfig.distance || 5;

        // Position spotlight above and in front of image
        this.spotlight.position.set(0, 0.8, 1.5);

        // Create target for spotlight (at mesh position)
        const target = new THREE.Object3D();
        target.position.copy(this.mesh.position);
        this.spotlight.target = target;

        this.group.add(this.spotlight);
        this.group.add(target);

        console.log('[ImagePlaneElement] Spotlight added');
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
        if (!this.group) {
            this.group = new THREE.Group();
        }

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

        this.group.add(this.mesh);
        this.group.userData.type = 'image_plane';

        return this.group;
    }

    /**
     * Add floating animation (legacy)
     */
    addFloatingAnimation() {
        const floatSpeed = this.config.floatSpeed || 0.3 + Math.random() * 0.5;
        const floatAmp = this.config.floatAmplitude || 0.02 + Math.random() * 0.03;
        const rotSpeed = this.config.rotationSpeed || 0.1 + Math.random() * 0.3;

        this.originalY = this.mesh.position.y;
        const originalRotZ = this.mesh.rotation.z;
        const spotlight = this.spotlight;

        this.group.userData.update = (time) => {
            // Float
            this.mesh.position.y = this.originalY + Math.sin(time * floatSpeed) * floatAmp;

            // Gentle rotation drift
            this.mesh.rotation.z = originalRotZ + Math.sin(time * rotSpeed * 0.5) * 0.02;

            // Update spotlight target to follow mesh
            if (spotlight && spotlight.target) {
                spotlight.target.position.copy(this.mesh.position);
            }
        };
    }

    /**
     * Add bob animation with configurable parameters
     * More controlled than floating animation
     */
    addBobAnimation() {
        const bobConfig = this.config.bobAnimation;
        const amplitude = bobConfig.amplitude || 0.02;
        const speed = bobConfig.speed || 0.3;
        const offset = bobConfig.offset || 0;

        this.originalY = this.mesh.position.y;
        const spotlight = this.spotlight;

        this.group.userData.update = (time) => {
            // Simple sine wave bob
            this.mesh.position.y = this.originalY + Math.sin(time * speed + offset) * amplitude;

            // Update spotlight target to follow mesh
            if (spotlight && spotlight.target) {
                spotlight.target.position.copy(this.mesh.position);
            }
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
     * Get the object (group containing mesh + spotlight)
     */
    getObject() {
        return this.group || this.mesh;
    }
}


export default ImagePlaneElement;
