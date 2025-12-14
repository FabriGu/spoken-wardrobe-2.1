/**
 * 3D Mesh Loading Animation
 *
 * Renders wireframe meshes with a pulsing wave effect for the 3D generation loading screen.
 * Cycles through multiple example meshes with seamless rotation transitions.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class MeshLoadingAnimation {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.currentWireframe = null;
        this.nextWireframe = null;
        this.animationId = null;
        this.clock = new THREE.Clock();
        this.isRunning = false;

        // Mesh cycling
        this.meshPaths = [];
        this.currentMeshIndex = 0;
        this.meshSwitchInterval = 3000; // 3 seconds
        this.lastSwitchTime = 0;
        this.isFading = false;
        this.fadeProgress = 0;
        this.fadeDuration = 0.8; // seconds

        // Shared rotation state for seamless transitions
        this.rotationY = 0;
        this.rotationX = 0;

        // Loader
        this.loader = new GLTFLoader();
    }

    /**
     * Initialize the Three.js scene.
     */
    async init() {
        // Create scene
        this.scene = new THREE.Scene();

        // Create camera
        this.camera = new THREE.PerspectiveCamera(
            45,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            100
        );
        this.camera.position.set(0, 0, 3);

        // Create renderer with transparency
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setClearColor(0x000000, 0);
        this.container.appendChild(this.renderer.domElement);

        // Discover all mesh files
        await this._discoverMeshes();

        // Load first mesh
        if (this.meshPaths.length > 0) {
            await this._loadMeshAtIndex(0, true);
        } else {
            this._createFallbackGeometry();
        }

        // Handle resize
        window.addEventListener('resize', () => this._onResize());

        console.log('[MeshLoadingAnimation] Initialized with', this.meshPaths.length, 'meshes');
    }

    /**
     * Discover all mesh files in the generated mesh folder.
     * @private
     */
    async _discoverMeshes() {
        // Predefined list of mesh files for cycling animation
        this.meshPaths = [
            'assets/example_mesh.glb',
            'assets/meshes/mesh_1.glb',
            'assets/meshes/mesh_2.glb',
            'assets/meshes/mesh_3.glb'
        ];
    }

    /**
     * Load a mesh at the given index.
     * @private
     */
    async _loadMeshAtIndex(index, immediate = false) {
        const path = this.meshPaths[index % this.meshPaths.length];

        return new Promise((resolve) => {
            this.loader.load(
                path,
                (gltf) => {
                    let mesh = null;
                    gltf.scene.traverse((child) => {
                        if (child.isMesh && !mesh) {
                            mesh = child;
                        }
                    });

                    if (mesh) {
                        const wireframe = this._createWireframe(mesh.geometry);

                        if (immediate) {
                            if (this.currentWireframe) {
                                this.scene.remove(this.currentWireframe);
                                this.currentWireframe.geometry.dispose();
                                this.currentWireframe.material.dispose();
                            }
                            this.currentWireframe = wireframe;
                            this.scene.add(wireframe);
                        } else {
                            this.nextWireframe = wireframe;
                        }
                    }
                    resolve(true);
                },
                undefined,
                () => {
                    // Failed to load, skip this mesh
                    resolve(false);
                }
            );
        });
    }

    /**
     * Create a wireframe with pulsing shader from geometry.
     * @private
     */
    _createWireframe(geometry) {
        const wireframeGeometry = new THREE.WireframeGeometry(geometry);

        // Custom shader material for pulsing wave with lower opacity
        const shaderMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                color: { value: new THREE.Color(0x00d4ff) },
                waveSpeed: { value: 1.2 },
                waveWidth: { value: 2.5 },
                fadeOpacity: { value: 1.0 }
            },
            vertexShader: `
                varying vec3 vPosition;
                void main() {
                    vPosition = position;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 color;
                uniform float waveSpeed;
                uniform float waveWidth;
                uniform float fadeOpacity;
                varying vec3 vPosition;

                void main() {
                    // Create wave based on Y position
                    float wave = sin((vPosition.y * waveWidth) - (time * waveSpeed)) * 0.5 + 0.5;

                    // Add some variation based on position
                    float variation = sin(vPosition.x * 3.0 + time * 0.5) * 0.1;

                    // Calculate alpha with wave effect - LOWER minimum opacity (0.02)
                    float alpha = 0.02 + wave * 0.98 + variation;
                    alpha = clamp(alpha, 0.02, 1.0);

                    // Apply fade opacity for mesh transitions
                    alpha *= fadeOpacity;

                    // Add subtle color shift
                    vec3 finalColor = color;
                    finalColor.r += wave * 0.15;
                    finalColor.b += (1.0 - wave) * 0.1;

                    gl_FragColor = vec4(finalColor, alpha);
                }
            `,
            transparent: true,
            depthTest: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });

        const wireframe = new THREE.LineSegments(wireframeGeometry, shaderMaterial);

        // Center and scale the wireframe - LARGER scale (2.0)
        const box = new THREE.Box3().setFromObject(wireframe);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 2.0 / maxDim; // Larger scale

        wireframe.scale.setScalar(scale);
        wireframe.position.sub(center.multiplyScalar(scale));

        return wireframe;
    }

    /**
     * Create fallback geometry if mesh loading fails.
     * @private
     */
    _createFallbackGeometry() {
        const geometry = new THREE.IcosahedronGeometry(1, 2);
        this.currentWireframe = this._createWireframe(geometry);
        this.scene.add(this.currentWireframe);
    }

    /**
     * Start the animation loop.
     */
    start() {
        if (this.isRunning) return;
        this.isRunning = true;

        // Show the canvas element if it was hidden
        if (this.renderer && this.renderer.domElement) {
            this.renderer.domElement.style.display = 'block';
        }

        this.clock.start();
        this.lastSwitchTime = this.clock.getElapsedTime() * 1000;
        this._animate();
        console.log('[MeshLoadingAnimation] Started');
    }

    /**
     * Stop the animation loop and hide the canvas.
     */
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        // Clear the canvas to prevent bleed-through to other states
        if (this.renderer) {
            this.renderer.clear();
            // Also hide the canvas element
            if (this.renderer.domElement) {
                this.renderer.domElement.style.display = 'none';
            }
        }

        console.log('[MeshLoadingAnimation] Stopped');
    }

    /**
     * Animation loop.
     * @private
     */
    _animate() {
        if (!this.isRunning) return;

        const elapsedTime = this.clock.getElapsedTime();
        const currentTime = elapsedTime * 1000;

        // Check if we need to switch meshes
        if (currentTime - this.lastSwitchTime > this.meshSwitchInterval && !this.isFading && this.meshPaths.length > 1) {
            this._startMeshTransition();
        }

        // Handle mesh transition fading
        if (this.isFading) {
            this.fadeProgress += this.clock.getDelta() / this.fadeDuration;

            if (this.fadeProgress >= 1.0) {
                this._completeMeshTransition();
            } else {
                // Update fade opacity on current wireframe
                if (this.currentWireframe && this.currentWireframe.material.uniforms) {
                    this.currentWireframe.material.uniforms.fadeOpacity.value = 1.0 - this.fadeProgress;
                }
                // Update fade opacity on next wireframe
                if (this.nextWireframe && this.nextWireframe.material.uniforms) {
                    this.nextWireframe.material.uniforms.fadeOpacity.value = this.fadeProgress;
                }
            }
        }

        // Update shader uniforms
        if (this.currentWireframe && this.currentWireframe.material.uniforms) {
            this.currentWireframe.material.uniforms.time.value = elapsedTime;
        }
        if (this.nextWireframe && this.nextWireframe.material.uniforms) {
            this.nextWireframe.material.uniforms.time.value = elapsedTime;
        }

        // Slow rotation - update shared rotation state
        this.rotationY = elapsedTime * 0.3;
        this.rotationX = Math.sin(elapsedTime * 0.2) * 0.1;

        // Apply rotation to current wireframe
        if (this.currentWireframe) {
            this.currentWireframe.rotation.y = this.rotationY;
            this.currentWireframe.rotation.x = this.rotationX;
        }

        // Apply same rotation to next wireframe (seamless)
        if (this.nextWireframe) {
            this.nextWireframe.rotation.y = this.rotationY;
            this.nextWireframe.rotation.x = this.rotationX;
        }

        this.renderer.render(this.scene, this.camera);
        this.animationId = requestAnimationFrame(() => this._animate());
    }

    /**
     * Start transitioning to the next mesh.
     * @private
     */
    async _startMeshTransition() {
        this.isFading = true;
        this.fadeProgress = 0;
        this.currentMeshIndex = (this.currentMeshIndex + 1) % this.meshPaths.length;

        // Load next mesh
        const loaded = await this._loadMeshAtIndex(this.currentMeshIndex, false);

        if (loaded && this.nextWireframe) {
            // Add to scene with 0 opacity
            this.nextWireframe.material.uniforms.fadeOpacity.value = 0;
            this.scene.add(this.nextWireframe);
        } else {
            // Failed to load, cancel transition
            this.isFading = false;
            this.lastSwitchTime = this.clock.getElapsedTime() * 1000;
        }
    }

    /**
     * Complete the mesh transition.
     * @private
     */
    _completeMeshTransition() {
        // Remove old wireframe
        if (this.currentWireframe) {
            this.scene.remove(this.currentWireframe);
            this.currentWireframe.geometry.dispose();
            this.currentWireframe.material.dispose();
        }

        // Set next as current
        this.currentWireframe = this.nextWireframe;
        this.nextWireframe = null;

        // Reset fade state
        if (this.currentWireframe && this.currentWireframe.material.uniforms) {
            this.currentWireframe.material.uniforms.fadeOpacity.value = 1.0;
        }

        this.isFading = false;
        this.fadeProgress = 0;
        this.lastSwitchTime = this.clock.getElapsedTime() * 1000;
    }

    /**
     * Handle window resize.
     * @private
     */
    _onResize() {
        if (!this.container || !this.renderer || !this.camera) return;

        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    /**
     * Clean up resources.
     */
    dispose() {
        this.stop();

        if (this.currentWireframe) {
            this.currentWireframe.geometry.dispose();
            this.currentWireframe.material.dispose();
            this.scene.remove(this.currentWireframe);
        }

        if (this.nextWireframe) {
            this.nextWireframe.geometry.dispose();
            this.nextWireframe.material.dispose();
            this.scene.remove(this.nextWireframe);
        }

        if (this.renderer) {
            this.renderer.dispose();
            if (this.renderer.domElement.parentNode) {
                this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
            }
        }

        window.removeEventListener('resize', this._onResize);
        console.log('[MeshLoadingAnimation] Disposed');
    }
}
