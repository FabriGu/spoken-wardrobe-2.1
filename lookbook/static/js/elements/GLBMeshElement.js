/**
 * GLBMeshElement.js
 *
 * Loads and manages GLB/GLTF 3D meshes for anamorphic compositions.
 * Used primarily for the clothing meshes from Rodin API.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class GLBMeshElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
        this.loader = new GLTFLoader();
    }

    /**
     * Load the GLB mesh.
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
        const { wireframe, color, opacity, emissive } = this.config;

        this.mesh.traverse((child) => {
            if (child.isMesh) {
                // Option: wireframe mode for ethereal look
                if (wireframe) {
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

                        // Add emissive glow if specified
                        if (emissive && child.material.emissive) {
                            child.material.emissive = new THREE.Color(emissive);
                            child.material.emissiveIntensity = 0.3;
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
    }

    /**
     * Get the loaded mesh.
     */
    getObject() {
        return this.mesh;
    }
}
