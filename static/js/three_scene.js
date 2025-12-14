/**
 * Three.js Scene for Spoken Wardrobe
 *
 * Handles 3D mesh rendering with skeletal animation.
 * Supports automatic skin weight transfer from pre-rigged body to clothing.
 *
 * Architecture:
 * 1. Load pre-rigged body mesh (9-bone skeleton)
 * 2. When Rodin mesh arrives, transfer skin weights
 * 3. Update skeleton bones from BlazePose data each frame
 * 4. GPU skinning deforms clothing automatically
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { SkinWeightTransfer } from './SkinWeightTransfer.js';
import { SkeletalAnimator } from './SkeletalAnimator.js';

export class ThreeScene {
    constructor(canvas) {
        this.canvas = canvas;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.clothingMesh = null;      // Original unrigged mesh (kept for reference)
        this.animationId = null;

        // Skeletal animation components
        this.bodyMesh = null;           // Pre-rigged body mesh (hidden unless debug)
        this.skinnedClothingMesh = null; // Clothing with transferred weights
        this.skeleton = null;           // Shared skeleton instance
        this.skeletalAnimator = null;   // Bone rotation updater
        this.weightTransfer = null;     // Weight transfer utility
        this.bodyMeshLoaded = false;    // Flag to track body mesh loading

        // Debug mode: show body mesh as wireframe (activated via ?debug=true URL param)
        this.debugMode = new URLSearchParams(window.location.search).get('debug') === 'true';

        // Skip skeletal animation mode (activated via ?noskel=true URL param)
        this.skipSkeletal = new URLSearchParams(window.location.search).get('noskel') === 'true';
        if (this.skipSkeletal) {
            console.log('[ThreeScene] Skeletal animation DISABLED via URL param');
        }

        // Target transform for smooth interpolation (fallback for rigid transform)
        this.targetTransform = {
            position: new THREE.Vector3(0, 0, 0),
            scale: 1.0,
            rotation: new THREE.Euler(0, 0, 0)
        };

        // Current transform (lerped)
        this.currentTransform = {
            position: new THREE.Vector3(0, 0, 0),
            scale: 1.0,
            rotation: new THREE.Euler(0, 0, 0)
        };

        // Base scale factor (set when mesh is loaded)
        this.baseScale = 1.0;

        // Use skeletal animation (set to true when body mesh loaded + weight transfer done)
        this.useSkeletalAnimation = false;

        // GLTF Loader instance
        this.gltfLoader = new GLTFLoader();

        this.init();
    }

    /**
     * Initialize the Three.js scene.
     */
    init() {
        // Scene
        this.scene = new THREE.Scene();

        // Camera - FOV 50° for larger mesh appearance (matching working version)
        this.camera = new THREE.PerspectiveCamera(
            50,
            window.innerWidth / window.innerHeight,
            0.01,
            100
        );
        // Position camera to look at torso level (body mesh origin is at feet)
        // Offset Y by ~0.8 units to center the torso on screen
        this.camera.position.set(0, 0.8, 2.5);
        this.camera.lookAt(0, 0.8, 0);

        // Renderer with transparency
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setClearColor(0x000000, 0); // Transparent background

        // Critical for PBR materials from Rodin API
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;

        // Enhanced lighting for PBR materials (4 lights like working version)
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        // Hemisphere light for natural sky/ground gradient
        const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.5);
        this.scene.add(hemisphereLight);

        // Main directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
        directionalLight.position.set(2, 2, 1);
        this.scene.add(directionalLight);

        // Fill light to reduce harsh shadows
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
        fillLight.position.set(-1, 1, -1);
        this.scene.add(fillLight);

        // Handle window resize
        window.addEventListener('resize', () => this.onResize());

        // Start animation loop
        this.animate();

        // Pre-load the rigged body mesh
        this.loadBodyMesh();

        if (this.debugMode) {
            console.log('[ThreeScene] Debug mode enabled - body mesh will be visible as wireframe');
        }

        console.log('[ThreeScene] Initialized');
    }

    /**
     * Load the pre-rigged body mesh (9-bone skeleton).
     * Called once at initialization. The body mesh provides the skeleton
     * that clothing meshes will be bound to.
     */
    async loadBodyMesh() {
        console.log('[ThreeScene] Loading pre-rigged body mesh...');

        try {
            // Load from static/models/ folder
            const gltf = await this.gltfLoader.loadAsync('/models/lowpoly_rigged_full_v1.glb');

            console.log('[ThreeScene] Body mesh GLTF loaded:', gltf);

            // Find the SkinnedMesh in the loaded scene
            let skinnedMesh = null;
            gltf.scene.traverse((child) => {
                if (child.isSkinnedMesh && !skinnedMesh) {
                    skinnedMesh = child;
                    console.log('[ThreeScene] Found SkinnedMesh:', child.name);
                }
            });

            if (!skinnedMesh) {
                console.error('[ThreeScene] No SkinnedMesh found in body GLB');
                return;
            }

            this.bodyMesh = skinnedMesh;
            this.skeleton = skinnedMesh.skeleton;

            // Log skeleton info
            console.log('[ThreeScene] Skeleton bones:', this.skeleton.bones.map(b => b.name));

            // Add body mesh to scene
            this.scene.add(gltf.scene);

            // Configure visibility based on debug mode
            if (this.debugMode) {
                // Show as red wireframe for debugging
                this.bodyMesh.material = new THREE.MeshBasicMaterial({
                    color: 0xff0000,
                    wireframe: true,
                    transparent: true,
                    opacity: 0.5
                });
                this.bodyMesh.visible = true;
                console.log('[ThreeScene] Body mesh visible as red wireframe (debug mode)');
            } else {
                // Hide body mesh in production
                this.bodyMesh.visible = false;
            }

            // Initialize weight transfer utility
            this.weightTransfer = new SkinWeightTransfer({
                useWeightInpainting: true,
                debugVisualization: this.debugMode
            });

            this.bodyMeshLoaded = true;
            console.log('[ThreeScene] Body mesh loaded successfully');

        } catch (error) {
            console.error('[ThreeScene] Failed to load body mesh:', error);
            // Continue without skeletal animation - fallback to rigid transform
            this.bodyMeshLoaded = false;
        }
    }

    /**
     * Handle window resize.
     */
    onResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    /**
     * Animation loop.
     */
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        // Get the active mesh (skinned or regular)
        const activeMesh = this.getActiveMesh();

        // Smooth interpolation of mesh transform
        if (activeMesh) {
            // Lerp position
            this.currentTransform.position.lerp(this.targetTransform.position, 0.1);
            activeMesh.position.copy(this.currentTransform.position);

            // Lerp scale (multiply by baseScale to maintain proper sizing)
            this.currentTransform.scale += (this.targetTransform.scale - this.currentTransform.scale) * 0.1;
            activeMesh.scale.setScalar(this.currentTransform.scale * this.baseScale);

            // Lerp rotation (simplified - just Y rotation)
            const currentY = activeMesh.rotation.y;
            const targetY = this.targetTransform.rotation.y;
            activeMesh.rotation.y = currentY + (targetY - currentY) * 0.1;
        }

        this.renderer.render(this.scene, this.camera);
    }

    /**
     * Load a mesh from base64-encoded GLB data.
     * If body mesh is loaded, performs automatic weight transfer
     * for skeletal animation support.
     *
     * @param {string} glbBase64 - Base64-encoded GLB file
     */
    async loadMeshFromBase64(glbBase64) {
        console.log('[ThreeScene] Loading mesh from base64...');
        console.log('[ThreeScene] Base64 length:', glbBase64.length);

        try {
            // Convert base64 to ArrayBuffer
            const binaryString = atob(glbBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            console.log(`[ThreeScene] GLB data size: ${bytes.length} bytes`);

            // Load GLB
            const gltf = await new Promise((resolve, reject) => {
                this.gltfLoader.parse(bytes.buffer, '', resolve, reject);
            });

            console.log('[ThreeScene] GLTF parsed, scene:', gltf.scene);

            // Remove existing meshes
            this._cleanupExistingMeshes();

            // Find the first mesh in the loaded scene
            let loadedMesh = null;
            gltf.scene.traverse((child) => {
                if (child.isMesh && !loadedMesh) {
                    loadedMesh = child;
                }
            });

            if (!loadedMesh) {
                console.error('[ThreeScene] No mesh found in loaded GLB');
                return;
            }

            // Store original clothing mesh
            this.clothingMesh = gltf.scene;

            // Calculate bounding box for auto-scaling
            const box = new THREE.Box3().setFromObject(this.clothingMesh);
            const size = box.getSize(new THREE.Vector3());
            const center = box.getCenter(new THREE.Vector3());

            console.log('[ThreeScene] Mesh bounds:', { size, center });

            // DON'T translate geometry - this breaks weight transfer coordinate matching
            // Instead, we'll position the mesh after weight transfer
            // Store center for later positioning
            this.geometryCenter = center.clone();

            // Scale to fit in view - target 1.5 units
            const maxDim = Math.max(size.x, size.y, size.z);
            const targetSize = 1.5;
            const scaleFactor = maxDim > 0 ? targetSize / maxDim : 1;

            console.log('[ThreeScene] Mesh bounds and scale:', {
                size: size,
                center: center,
                scaleFactor: scaleFactor
            });

            // Process materials
            let hasTexture = false;
            let meshCount = 0;
            this.clothingMesh.traverse((child) => {
                if (child.isMesh) {
                    meshCount++;
                    console.log('[ThreeScene] Found mesh child:', child.name || 'unnamed',
                                'vertices:', child.geometry?.attributes?.position?.count || 0);

                    if (child.material && child.material.map) {
                        console.log('[ThreeScene] Mesh has texture map');
                        hasTexture = true;
                    }

                    if (!child.material || child.material.opacity === 0) {
                        child.material = new THREE.MeshStandardMaterial({
                            color: 0x8b5cf6,
                            metalness: 0.2,
                            roughness: 0.7
                        });
                        console.log('[ThreeScene] Applied default material to mesh');
                    }

                    if (child.material) {
                        child.material.side = THREE.DoubleSide;
                        child.material.transparent = false;
                        child.material.visible = true;
                        child.material.needsUpdate = true;
                    }

                    child.visible = true;
                }
            });

            this.hasTexture = hasTexture;
            this.baseScale = scaleFactor;
            this.targetTransform.scale = 10.0;
            this.currentTransform.scale = 1.0;

            // Attempt skeletal animation setup if body mesh is loaded (unless disabled via URL)
            if (this.bodyMeshLoaded && this.weightTransfer && loadedMesh && !this.skipSkeletal) {
                try {
                    console.log('[ThreeScene] Attempting weight transfer for skeletal animation...');

                    // Get body mesh bounds to align clothing properly
                    const bodyBox = new THREE.Box3().setFromObject(this.bodyMesh);
                    const bodyCenter = bodyBox.getCenter(new THREE.Vector3());

                    console.log('[ThreeScene] Body mesh center:', bodyCenter.toArray());
                    console.log('[ThreeScene] Clothing mesh center:', center.toArray());

                    // Transfer weights from body to clothing
                    this.skinnedClothingMesh = this.weightTransfer.transfer(
                        this.bodyMesh,
                        loadedMesh
                    );

                    // Copy material
                    this.skinnedClothingMesh.material = loadedMesh.material.clone();
                    this.skinnedClothingMesh.material.side = THREE.DoubleSide;

                    // Position skinned mesh to align with body mesh
                    // The clothing mesh center should align with the body mesh center
                    // Offset = bodyCenter - (clothingCenter * scaleFactor)
                    const clothingCenterScaled = center.clone().multiplyScalar(scaleFactor);
                    const positionOffset = bodyCenter.clone().sub(clothingCenterScaled);

                    this.skinnedClothingMesh.position.copy(positionOffset);
                    this.skinnedClothingMesh.scale.setScalar(scaleFactor);

                    console.log('[ThreeScene] Position offset for alignment:', positionOffset.toArray());

                    console.log('[ThreeScene] Skinned mesh setup:', {
                        position: this.skinnedClothingMesh.position.toArray(),
                        scale: scaleFactor,
                        visible: true
                    });

                    // IMPORTANT: Ensure skinned mesh is visible
                    this.skinnedClothingMesh.visible = true;
                    this.skinnedClothingMesh.frustumCulled = false; // Prevent culling

                    // Add skinned mesh to scene
                    this.scene.add(this.skinnedClothingMesh);

                    // Hide the original unrigged mesh (Group)
                    this.clothingMesh.visible = false;
                    this.clothingMesh.traverse((child) => {
                        child.visible = false;
                    });

                    // Create skeletal animator
                    this.skeletalAnimator = new SkeletalAnimator(this.skeleton, {
                        smoothingFactor: 0.3,
                        debug: this.debugMode
                    });

                    this.useSkeletalAnimation = true;
                    console.log('[ThreeScene] Skeletal animation enabled');
                    console.log('[ThreeScene] Weight transfer stats:', this.weightTransfer.getStats());

                    // DEBUG: Add visible bounding box to verify mesh position
                    if (this.debugMode) {
                        const debugBox = new THREE.Box3().setFromObject(this.skinnedClothingMesh);
                        const debugHelper = new THREE.Box3Helper(debugBox, 0x00ff00);
                        this.scene.add(debugHelper);
                        console.log('[ThreeScene] DEBUG: Added bounding box helper (green)');
                    }

                } catch (weightError) {
                    console.error('[ThreeScene] Weight transfer failed, using rigid transform:', weightError);
                    this.useSkeletalAnimation = false;
                    this.scene.add(this.clothingMesh);
                }
            } else {
                // No body mesh or skeletal disabled - use rigid transform fallback
                const reason = this.skipSkeletal ? 'disabled via URL param' :
                               !this.bodyMeshLoaded ? 'body mesh not loaded' :
                               'weight transfer not ready';
                console.log(`[ThreeScene] Using rigid transform fallback (${reason})`);
                this.useSkeletalAnimation = false;
                this.clothingMesh.visible = true;
                this.scene.add(this.clothingMesh);
                console.log('[ThreeScene] ClothingMesh added to scene:', {
                    position: this.clothingMesh.position.toArray(),
                    scale: this.clothingMesh.scale.toArray(),
                    visible: this.clothingMesh.visible
                });
            }

            console.log('[ThreeScene] Mesh loaded and positioned, scale:', scaleFactor);
            console.log('[ThreeScene] Skeletal animation:', this.useSkeletalAnimation ? 'ENABLED' : 'DISABLED');
            console.log('[ThreeScene] Scene children count:', this.scene.children.length);

        } catch (error) {
            console.error('[ThreeScene] Error loading mesh:', error);
        }
    }

    /**
     * Cleanup existing meshes before loading new ones
     */
    _cleanupExistingMeshes() {
        // Remove original clothing mesh
        if (this.clothingMesh) {
            this.scene.remove(this.clothingMesh);
            this.clothingMesh.traverse((child) => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach(m => m.dispose());
                    } else {
                        child.material.dispose();
                    }
                }
            });
            this.clothingMesh = null;
        }

        // Remove skinned clothing mesh
        if (this.skinnedClothingMesh) {
            this.scene.remove(this.skinnedClothingMesh);
            if (this.skinnedClothingMesh.geometry) {
                this.skinnedClothingMesh.geometry.dispose();
            }
            if (this.skinnedClothingMesh.material) {
                this.skinnedClothingMesh.material.dispose();
            }
            this.skinnedClothingMesh = null;
        }

        // Reset animation state
        this.skeletalAnimator = null;
        this.useSkeletalAnimation = false;
    }

    /**
     * Reset mesh to center position for alignment phase (CALIBRATING).
     * Shows mesh at fixed center position without body tracking.
     */
    resetToCenter() {
        // Get the active mesh (skinned or regular)
        const activeMesh = this.getActiveMesh();

        if (!activeMesh) {
            console.warn('[ThreeScene] No mesh to reset');
            return;
        }

        // Reset target transforms to center
        this.targetTransform.position.set(0, 0, 0);
        this.targetTransform.scale = 1.0;
        this.targetTransform.rotation.set(0, 0, 0);

        // Apply immediately (bypass lerping for instant reset)
        activeMesh.position.set(0, 0, 0);
        activeMesh.scale.setScalar(this.baseScale);
        activeMesh.rotation.set(0, 0, 0);

        // Also reset current transform to prevent lerping back
        this.currentTransform.position.set(0, 0, 0);
        this.currentTransform.scale = 1.0;
        this.currentTransform.rotation.set(0, 0, 0);

        // If using skeletal animation, reset bones to rest pose
        if (this.useSkeletalAnimation && this.skeletalAnimator) {
            this.skeletalAnimator.reset();
        }

        console.log('[ThreeScene] Mesh reset to center, baseScale:', this.baseScale,
                    'skeletal:', this.useSkeletalAnimation);
    }

    /**
     * Apply a texture from a base64 image to the mesh.
     * Use this to apply the 2D preview image as a texture if the GLB has no texture.
     * @param {string} imageBase64 - Base64-encoded image (without data URL prefix)
     */
    applyTextureFromBase64(imageBase64) {
        if (!this.clothingMesh) {
            console.warn('[ThreeScene] No mesh to apply texture to');
            return;
        }

        const textureLoader = new THREE.TextureLoader();
        const dataUrl = `data:image/png;base64,${imageBase64}`;

        textureLoader.load(dataUrl, (texture) => {
            console.log('[ThreeScene] Applying custom texture to mesh');

            // Apply texture to all mesh children
            this.clothingMesh.traverse((child) => {
                if (child.isMesh) {
                    // Create new material with the texture
                    child.material = new THREE.MeshStandardMaterial({
                        map: texture,
                        side: THREE.DoubleSide,
                        metalness: 0.1,
                        roughness: 0.8
                    });
                    child.material.needsUpdate = true;
                }
            });

            this.hasTexture = true;
            console.log('[ThreeScene] Custom texture applied');
        }, undefined, (error) => {
            console.error('[ThreeScene] Error loading texture:', error);
        });
    }

    /**
     * Update mesh transform from calibration data.
     * Always applies rigid transform - this ensures mesh moves even if skeletal fails.
     * Skeletal animation (if working) will provide additional bone deformations.
     *
     * @param {object} calibration - Calibration data with position, scale, rotation
     */
    updateMeshTransform(calibration) {
        if (!calibration) return;

        // ALWAYS update rigid transform - this is the fallback that ensures mesh moves
        // Skeletal animation adds bone deformations on top of this base transform

        if (calibration.position) {
            this.targetTransform.position.set(
                calibration.position.x || 0,
                calibration.position.y || 0,
                calibration.position.z || 0
            );
        }

        if (calibration.scale !== undefined) {
            this.targetTransform.scale = calibration.scale;
        }

        if (calibration.rotation) {
            this.targetTransform.rotation.set(
                calibration.rotation.x || 0,
                calibration.rotation.y || 0,
                calibration.rotation.z || 0
            );
        }
    }

    /**
     * Update skeleton bones from BlazePose rotation data.
     * Called each frame during TRY_ON phase.
     *
     * @param {object} boneRotations - Dict mapping bone_name to {x, y, z, w} quaternion
     */
    updateBonesFromFrame(boneRotations) {
        if (!boneRotations) return;

        if (this.useSkeletalAnimation && this.skeletalAnimator) {
            this.skeletalAnimator.updateBones(boneRotations);
        }
    }

    /**
     * Check if skeletal animation is active
     * @returns {boolean}
     */
    isSkeletalAnimationEnabled() {
        return this.useSkeletalAnimation;
    }

    /**
     * Get the active mesh (skinned or regular)
     * @returns {THREE.Mesh|THREE.SkinnedMesh|null}
     */
    getActiveMesh() {
        if (this.useSkeletalAnimation && this.skinnedClothingMesh) {
            return this.skinnedClothingMesh;
        }
        return this.clothingMesh;
    }

    /**
     * Dispose of the scene and resources.
     */
    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        this._cleanupExistingMeshes();

        if (this.bodyMesh) {
            this.scene.remove(this.bodyMesh.parent || this.bodyMesh);
        }

        this.renderer.dispose();
    }
}
