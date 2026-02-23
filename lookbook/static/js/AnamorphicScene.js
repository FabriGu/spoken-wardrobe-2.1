/**
 * AnamorphicScene.js
 *
 * Enhanced Three.js scene manager for the Dreamwear Lookbook.
 * Integrates advanced shaders, mesh animation, and chaotic compositions.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { AnamorphicProjector } from './AnamorphicProjector.js';
import { ElementFactory } from './ElementFactory.js';

// Bold color palette from reference images
const BOLD_COLORS = [
    0xFF1493, // Deep Pink
    0x00CED1, // Dark Turquoise
    0xFFD700, // Gold
    0xFF4500, // Orange Red
    0x9400D3, // Dark Violet
    0x00FF7F, // Spring Green
    0xFF6347, // Tomato
    0x1E90FF, // Dodger Blue
    0xFF69B4, // Hot Pink
    0x32CD32, // Lime Green
    0x8b5cf6, // Purple (from existing CSS)
    0xec4899, // Pink (from existing CSS)
];

export class AnamorphicScene {
    constructor(container) {
        this.container = container;
        this.elements = [];     // All composition elements
        this.animatedElements = []; // Elements with update() methods
        this.meshAnimators = []; // MeshAnimator instances

        // Initialize Three.js
        this.initScene();
        this.initCamera();
        this.initRenderer();
        this.initControls();
        this.initLighting();
        this.initPostProcessing();

        // Create projector
        this.projector = new AnamorphicProjector(this.camera);

        // Create element factory
        this.elementFactory = new ElementFactory();

        // Track time for animations
        this.clock = new THREE.Clock();

        // Start animation loop
        this.animate();

        // Handle resize
        window.addEventListener('resize', () => this.onResize());

        console.log('[AnamorphicScene] Initialized');
    }

    initScene() {
        this.scene = new THREE.Scene();

        // Default bold background
        this.setBackgroundColor(BOLD_COLORS[Math.floor(Math.random() * BOLD_COLORS.length)]);
    }

    initCamera() {
        // Camera at FOV 50 (matching existing project)
        this.camera = new THREE.PerspectiveCamera(
            50,
            window.innerWidth / window.innerHeight,
            0.1,
            1000
        );

        // Default anamorphic viewpoint - looking at origin from Z=10
        this.camera.position.set(0, 0, 10);
        this.camera.lookAt(0, 0, 0);
    }

    initRenderer() {
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            preserveDrawingBuffer: true, // Needed for screenshots
            powerPreference: 'high-performance'
        });

        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Color management
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;

        this.container.appendChild(this.renderer.domElement);
    }

    initControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.enabled = true;
        this.controls.enableZoom = true;
        this.controls.enablePan = false;
        this.controls.minDistance = 2;
        this.controls.maxDistance = 30;

        // Store initial view
        this.anamorphicPosition = this.camera.position.clone();
        this.anamorphicTarget = new THREE.Vector3(0, 0, 0);
    }

    initLighting() {
        // Ambient light for overall illumination
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        // Hemisphere light for natural sky/ground gradient
        const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.5);
        this.scene.add(hemisphereLight);

        // Main directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
        directionalLight.position.set(5, 10, 5);
        this.scene.add(directionalLight);

        // Fill light
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
        fillLight.position.set(-5, 5, -5);
        this.scene.add(fillLight);
        
        // Rim light for dramatic edges
        const rimLight = new THREE.DirectionalLight(0xffffff, 0.6);
        rimLight.position.set(0, 5, -10);
        this.scene.add(rimLight);
    }

    initPostProcessing() {
        // Store post-processing settings (actual implementation would use EffectComposer)
        this.postProcessing = {
            bloom: true,
            chromaticAberration: 0.5,
            vignette: true
        };
    }

    /**
     * Set the background color with fog.
     * @param {number} color - Hex color value
     */
    setBackgroundColor(color) {
        this.scene.background = new THREE.Color(color);
        this.scene.fog = new THREE.Fog(color, 10, 60);
        
        // Update fog color to match background
        if (this.scene.fog) {
            this.scene.fog.color.set(color);
        }
    }

    /**
     * Load and display a composition from config.
     * @param {object} config - Composition configuration object
     */
    async loadComposition(config) {
        console.log('[AnamorphicScene] Loading composition:', config.id);

        // Clear existing elements
        this.clearElements();

        // Set background
        if (config.background?.color) {
            const color = new THREE.Color(config.background.color);
            this.setBackgroundColor(color.getHex());
        } else {
            // Random bold color
            this.setBackgroundColor(BOLD_COLORS[Math.floor(Math.random() * BOLD_COLORS.length)]);
        }

        // Set anamorphic camera position
        if (config.camera?.position) {
            this.anamorphicPosition = new THREE.Vector3(...config.camera.position);
            this.camera.position.copy(this.anamorphicPosition);
        }

        // Load all elements
        for (const elementConfig of config.elements || []) {
            try {
                const element = await this.elementFactory.create(elementConfig);

                if (element) {
                    // Position using anamorphic projection
                    if (elementConfig.target_2d) {
                        this.projector.positionElement(
                            element,
                            elementConfig.target_2d,
                            elementConfig.depth_range || { min: 4, max: 15 },
                            elementConfig.scale || 0.2
                        );
                    }

                    // Apply rotation if specified
                    if (elementConfig.rotation) {
                        this.projector.applyRotation(element, elementConfig.rotation);
                    }

                    // Make image planes billboard (face camera)
                    if (elementConfig.type === 'image_plane' && elementConfig.billboard !== false) {
                        this.projector.makeBillboard(element);
                    }

                    // Add to scene
                    this.scene.add(element);
                    this.elements.push(element);

                    // Track animated elements
                    if (element.userData.update) {
                        this.animatedElements.push(element);
                    }
                    
                    // Track mesh animators
                    if (element.userData.animator) {
                        this.meshAnimators.push(element.userData.animator);
                    }
                    
                    // Recursively find animated children (for groups)
                    element.traverse((child) => {
                        if (child.userData.update && !this.animatedElements.includes(child)) {
                            this.animatedElements.push(child);
                        }
                        if (child.userData.animator) {
                            this.meshAnimators.push(child.userData.animator);
                        }
                    });
                }
            } catch (error) {
                console.error('[AnamorphicScene] Failed to create element:', elementConfig, error);
            }
        }

        console.log(`[AnamorphicScene] Loaded ${this.elements.length} elements, ${this.animatedElements.length} animated`);
    }

    /**
     * Create a MAXIMUM CHAOS test composition.
     */
    createTestComposition() {
        console.log('[AnamorphicScene] Creating MAXIMUM CHAOS test composition');

        this.clearElements();
        this.setBackgroundColor(0x000000); // Black for high contrast

        // Create MANY overlapping elements
        const colors = [0xFF1493, 0x00CED1, 0xFFD700, 0xFF4500, 0x9400D3, 0x00FF7F, 0xFF6347, 0x1E90FF];
        
        // 1. Center chaotic cluster
        for (let i = 0; i < 15; i++) {
            const geometry = new THREE.BoxGeometry(1, 1, 1);
            const material = new THREE.MeshStandardMaterial({
                color: colors[i % colors.length],
                metalness: 0.3 + Math.random() * 0.5,
                roughness: Math.random(),
                emissive: colors[i % colors.length],
                emissiveIntensity: 0.1 + Math.random() * 0.3,
                wireframe: Math.random() > 0.6
            });
            const mesh = new THREE.Mesh(geometry, material);

            // Chaotic positions - overlapping in center
            const target2D = {
                x: 0.3 + Math.random() * 0.4,  // 0.3 to 0.7 (center-biased)
                y: 0.3 + Math.random() * 0.4
            };

            this.projector.positionElement(
                mesh,
                target2D,
                { min: 3 + Math.random() * 3, max: 6 + Math.random() * 4 },
                0.1 + Math.random() * 0.25
            );

            // Random rotation
            mesh.rotation.set(
                Math.random() * Math.PI,
                Math.random() * Math.PI,
                Math.random() * Math.PI
            );

            this.scene.add(mesh);
            this.elements.push(mesh);
            
            // Chaotic animation
            const originalY = mesh.position.y;
            const originalRot = mesh.rotation.clone();
            const floatSpeed = 0.5 + Math.random() * 2;
            const floatAmp = 0.03 + Math.random() * 0.1;
            
            mesh.userData.update = (time) => {
                mesh.position.y = originalY + Math.sin(time * floatSpeed + i) * floatAmp;
                mesh.rotation.x = originalRot.x + Math.sin(time * 0.5 + i) * 0.1;
                mesh.rotation.y = originalRot.y + Math.cos(time * 0.3 + i) * 0.1;
            };
            this.animatedElements.push(mesh);
        }

        // 2. MANY shader planes - covering the space
        const shaderNames = ['dreamBlur', 'glitch', 'kineticLiquid', 'chromatic', 'noiseField', 'scanLine', 'voronoi', 'particleCloud', 'holographic', 'ripple', 'mandala'];
        
        for (let i = 0; i < 20; i++) {
            const geometry = new THREE.PlaneGeometry(1, 1);
            const material = new THREE.MeshBasicMaterial({
                color: colors[i % colors.length],
                transparent: true,
                opacity: 0.15 + Math.random() * 0.3,
                side: THREE.DoubleSide,
                blending: THREE.AdditiveBlending
            });
            const plane = new THREE.Mesh(geometry, material);
            
            // Random positions everywhere
            const pos = {
                x: 0.1 + Math.random() * 0.8,
                y: 0.1 + Math.random() * 0.8
            };
            
            this.projector.positionElement(
                plane,
                pos,
                { min: 2 + Math.random() * 5, max: 8 + Math.random() * 10 },
                0.2 + Math.random() * 0.4
            );
            
            // Random rotation
            plane.rotation.z = Math.random() * Math.PI * 2;
            
            // Animation
            const originalRot = plane.rotation.z;
            const rotSpeed = (Math.random() - 0.5) * 0.5;
            
            plane.userData.update = (time) => {
                plane.rotation.z = originalRot + Math.sin(time * rotSpeed) * 0.2;
            };
            
            this.scene.add(plane);
            this.elements.push(plane);
            this.animatedElements.push(plane);
        }

        // 3. Diagonal strips cutting through
        for (let i = 0; i < 5; i++) {
            const geometry = new THREE.PlaneGeometry(15, 0.2 + Math.random() * 0.3);
            const material = new THREE.MeshBasicMaterial({
                color: colors[i % colors.length],
                transparent: true,
                opacity: 0.3 + Math.random() * 0.4,
                side: THREE.DoubleSide
            });
            const strip = new THREE.Mesh(geometry, material);
            
            this.projector.positionElement(
                strip,
                { x: 0.5, y: 0.5 },
                { min: 1 + i * 0.5, max: 2 + i * 0.5 },
                1.0
            );
            
            strip.rotation.z = (Math.PI / 4) + (Math.random() - 0.5);
            
            this.scene.add(strip);
            this.elements.push(strip);
        }

        // 4. Text chaos - many labels at all angles
        const texts = ['CHAOS', 'DREAM', 'NOISE', 'OVERLAP', 'DENSE', 'GLITCH', 'FLOW', 'VOID', 'STATIC', 'BROKEN', 'REPEAT'];
        const rotations = [0, 0, 90, -90, 45, -45, 180, 30, -30, 60, -60, 120, -120];
        
        for (let i = 0; i < 12; i++) {
            const text = texts[i % texts.length];
            const sprite = this.createTextSprite(text, colors[i % colors.length]);
            
            this.projector.positionElement(
                sprite,
                { x: 0.1 + Math.random() * 0.8, y: 0.1 + Math.random() * 0.8 },
                { min: 3 + Math.random() * 5, max: 6 + Math.random() * 8 },
                0.15 + Math.random() * 0.2
            );
            
            sprite.material.rotation = rotations[i % rotations.length] * (Math.PI / 180);
            
            // Float animation
            const originalY = sprite.position.y;
            const floatSpeed = 0.3 + Math.random();
            
            sprite.userData.update = (time) => {
                sprite.position.y = originalY + Math.sin(time * floatSpeed + i) * 0.05;
            };
            
            this.scene.add(sprite);
            this.elements.push(sprite);
            this.animatedElements.push(sprite);
        }

        // 5. Vertical edge text
        const leftText = this.createTextSprite('MAXIMUM CHAOS DENSITY OVERLAP NOISE', 0xffffff);
        this.projector.positionElement(
            leftText,
            { x: 0.05, y: 0.5 },
            { min: 5, max: 8 },
            0.15
        );
        leftText.material.rotation = -Math.PI / 2;
        this.scene.add(leftText);
        this.elements.push(leftText);

        const rightText = this.createTextSprite('DREAMWEAR LOOKBOOK 2024', 0xff1493);
        this.projector.positionElement(
            rightText,
            { x: 0.95, y: 0.5 },
            { min: 6, max: 10 },
            0.12
        );
        rightText.material.rotation = Math.PI / 2;
        this.scene.add(rightText);
        this.elements.push(rightText);

        console.log('[AnamorphicScene] MAXIMUM CHAOS test created with', this.elements.length, 'elements');
    }

    /**
     * Create a simple text sprite (2D text that faces camera).
     */
    createTextSprite(text, color = 0xffffff) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 512;
        canvas.height = 128;

        context.fillStyle = 'transparent';
        context.fillRect(0, 0, canvas.width, canvas.height);

        context.font = 'Bold 80px Helvetica';
        context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, canvas.width / 2, canvas.height / 2);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true
        });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(4, 1, 1);

        return sprite;
    }

    /**
     * Clear all composition elements from the scene.
     */
    clearElements() {
        // Stop any ongoing animations
        this.animatedElements = [];
        this.meshAnimators = [];

        for (const element of this.elements) {
            this.scene.remove(element);

            // Dispose geometry and materials
            if (element.geometry) element.geometry.dispose();
            if (element.material) {
                if (Array.isArray(element.material)) {
                    element.material.forEach(m => m.dispose());
                } else {
                    element.material.dispose();
                }
            }

            // Handle group children
            if (element.traverse) {
                element.traverse((child) => {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(m => m.dispose());
                        } else {
                            child.material.dispose();
                        }
                    }
                });
            }
        }

        this.elements = [];
    }

    /**
     * Snap camera to the anamorphic viewpoint with smooth animation.
     */
    snapToAnamorphicView(duration = 1.0) {
        const startPos = this.camera.position.clone();
        const startTarget = this.controls.target.clone();
        const startTime = performance.now();

        const animate = () => {
            const elapsed = (performance.now() - startTime) / 1000;
            const t = Math.min(elapsed / duration, 1);

            // Ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);

            // Interpolate position
            this.camera.position.lerpVectors(startPos, this.anamorphicPosition, eased);

            // Interpolate target
            this.controls.target.lerpVectors(startTarget, this.anamorphicTarget, eased);

            if (t < 1) {
                requestAnimationFrame(animate);
            }
        };

        animate();
    }

    /**
     * Enable/disable orbit controls.
     */
    enableOrbit(enabled) {
        this.controls.enabled = enabled;
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
        requestAnimationFrame(() => this.animate());

        // Get delta time
        const deltaTime = this.clock.getDelta();
        const time = this.clock.getElapsedTime();

        // Update controls
        this.controls.update();

        // Update animated elements (shaders, meshes, etc.)
        for (const element of this.animatedElements) {
            if (element.userData.update) {
                try {
                    element.userData.update(time, deltaTime);
                } catch (e) {
                    console.warn('Animation update error:', e);
                }
            }
        }
        
        // Update mesh animators directly
        for (const animator of this.meshAnimators) {
            if (animator && animator.update) {
                try {
                    animator.update(deltaTime);
                } catch (e) {
                    console.warn('Animator update error:', e);
                }
            }
        }

        // Render
        this.renderer.render(this.scene, this.camera);
    }

    /**
     * Dispose of the scene and release resources.
     */
    dispose() {
        this.clearElements();
        this.renderer.dispose();
        this.controls.dispose();
    }
}

export default AnamorphicScene;
