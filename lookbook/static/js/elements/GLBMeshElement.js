/**
 * GLBMeshElement.js
 *
 * Enhanced GLB/GLTF mesh loader with animation support.
 * Integrates MeshAnimator for breathing, floating, and glitch effects.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshAnimator } from '../animation/MeshAnimator.js';

export class GLBMeshElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
        this.loader = new GLTFLoader();
        this.animator = null;
    }

    /**
     * Load the GLB mesh with optional animation.
     * @returns {Promise<THREE.Object3D>} - The loaded mesh
     */
    async load() {
        return new Promise((resolve, reject) => {
            this.loader.load(
                this.config.path,
                (gltf) => {
                    this.mesh = gltf.scene;

                    // Apply visual style
                    this.applyStyle();

                    // Calculate and center the mesh
                    this.centerMesh();

                    // Setup animation if enabled
                    if (this.config.animation !== false) {
                        this.setupAnimation();
                    }

                    resolve(this.mesh);
                },
                (progress) => {
                    // Loading progress
                },
                (error) => {
                    console.error('[GLBMeshElement] Load error:', error);
                    reject(error);
                }
            );
        });
    }

    /**
     * Apply visual style to the mesh.
     */
    applyStyle() {
        const { wireframe, color, opacity, emissive, metalness, roughness, plain } = this.config;

        this.mesh.traverse((child) => {
            if (child.isMesh) {
                // Plain mode: keep original material unchanged (no shader effects)
                if (plain) {
                    if (child.material) {
                        child.material.side = THREE.DoubleSide;
                        child.material.needsUpdate = true;
                    }
                }
                // Option: wireframe mode for ethereal look
                else if (wireframe) {
                    child.material = new THREE.MeshBasicMaterial({
                        color: color || 0xffffff,
                        wireframe: true,
                        transparent: opacity !== undefined,
                        opacity: opacity || 1.0
                    });
                } else {
                    // Enhance existing material
                    if (child.material) {
                        child.material.side = THREE.DoubleSide;

                        // Apply custom material properties
                        if (metalness !== undefined) {
                            child.material.metalness = metalness;
                        }
                        if (roughness !== undefined) {
                            child.material.roughness = roughness;
                        }

                        // Add emissive glow if specified
                        if (emissive) {
                            if (!child.material.emissive) {
                                child.material.emissive = new THREE.Color();
                            }
                            child.material.emissive.set(emissive);
                            child.material.emissiveIntensity = 0.3;
                        }

                        // Apply base color if specified
                        if (color) {
                            child.material.color.set(color);
                        }

                        // Apply opacity
                        if (opacity !== undefined) {
                            child.material.transparent = true;
                            child.material.opacity = opacity;
                        }

                        child.material.needsUpdate = true;
                    }
                }

                child.visible = true;
                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
    }

    /**
     * Center the mesh geometry on its bounding box.
     */
    centerMesh() {
        const box = new THREE.Box3().setFromObject(this.mesh);
        const center = box.getCenter(new THREE.Vector3());

        // Offset to center
        this.mesh.position.sub(center);

        // Store original bounds for reference
        this.mesh.userData.originalBounds = {
            center: center.clone(),
            size: box.getSize(new THREE.Vector3())
        };
        
        // Store original transform for animation
        this.mesh.userData.originalPosition = this.mesh.position.clone();
        this.mesh.userData.originalRotation = this.mesh.rotation.clone();
        this.mesh.userData.originalScale = this.mesh.scale.clone();
    }

    /**
     * Setup animation system
     */
    setupAnimation() {
        // Get animation preset from config
        const preset = this.config.animationPreset || 'dreamy';
        
        // Create animator
        this.animator = MeshAnimator.create(this.mesh, preset);
        
        // Store reference for scene update loop
        this.mesh.userData.animator = this.animator;
        this.mesh.userData.update = (time, deltaTime) => {
            if (this.animator) {
                this.animator.update(deltaTime || 0.016);
            }
        };
        
        // Store animation info
        this.mesh.userData.animationInfo = {
            preset: preset,
            enabled: true
        };
    }

    /**
     * Change animation preset dynamically
     */
    setAnimationPreset(preset) {
        if (this.animator) {
            // Create new animator with different preset
            this.animator = MeshAnimator.create(this.mesh, preset);
            this.mesh.userData.animator = this.animator;
            this.mesh.userData.animationInfo.preset = preset;
        }
    }

    /**
     * Set animation intensity (0-1)
     */
    setAnimationIntensity(intensity) {
        if (this.animator) {
            this.animator.setIntensity(intensity);
        }
    }

    /**
     * Toggle animation on/off
     */
    toggleAnimation(enabled) {
        if (this.animator) {
            this.mesh.userData.animationInfo.enabled = enabled;
            // Update function will check this flag
            const originalUpdate = this.mesh.userData.update;
            this.mesh.userData.update = (time, deltaTime) => {
                if (enabled && this.animator) {
                    this.animator.update(deltaTime || 0.016);
                }
            };
        }
    }

    /**
     * Get the loaded mesh.
     */
    getObject() {
        return this.mesh;
    }

    /**
     * Get the animator instance
     */
    getAnimator() {
        return this.animator;
    }

    /**
     * Dispose of resources
     */
    dispose() {
        this.mesh.traverse((child) => {
            if (child.isMesh) {
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach(m => m.dispose());
                    } else {
                        child.material.dispose();
                    }
                }
            }
        });
    }
}

export default GLBMeshElement;
