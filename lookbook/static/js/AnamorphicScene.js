/**
 * AnamorphicScene.js
 *
 * Main Three.js scene manager for the Dreamwear Lookbook.
 * Creates anamorphic compositions where 3D elements align into
 * 2D collages from specific viewpoints.
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

        // Initialize Three.js
        this.initScene();
        this.initCamera();
        this.initRenderer();
        this.initControls();
        this.initLighting();

        // Create projector
        this.projector = new AnamorphicProjector(this.camera);

        // Create element factory
        this.elementFactory = new ElementFactory();

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
            preserveDrawingBuffer: true // Needed for screenshots
        });

        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Color management
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;

        this.container.appendChild(this.renderer.domElement);
    }

    initControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.enabled = true; // Start with orbit enabled

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
    }

    /**
     * Set the background color with fog.
     * @param {number} color - Hex color value
     */
    setBackgroundColor(color) {
        this.scene.background = new THREE.Color(color);
        this.scene.fog = new THREE.Fog(color, 15, 50);
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
                }
            } catch (error) {
                console.error('[AnamorphicScene] Failed to create element:', elementConfig, error);
            }
        }

        console.log(`[AnamorphicScene] Loaded ${this.elements.length} elements`);
    }

    /**
     * Create a test composition with basic shapes.
     * Useful for verifying the anamorphic effect works.
     */
    createTestComposition() {
        console.log('[AnamorphicScene] Creating test composition');

        this.clearElements();
        this.setBackgroundColor(0xFF1493); // Deep pink

        // Create test elements at different positions
        const testPositions = [
            { target2D: { x: 0.5, y: 0.5 }, color: 0xffffff, size: 0.3 },  // Center
            { target2D: { x: 0.2, y: 0.2 }, color: 0x00ffff, size: 0.15 }, // Top-left
            { target2D: { x: 0.8, y: 0.2 }, color: 0xffff00, size: 0.15 }, // Top-right
            { target2D: { x: 0.2, y: 0.8 }, color: 0xff00ff, size: 0.15 }, // Bottom-left
            { target2D: { x: 0.8, y: 0.8 }, color: 0x00ff00, size: 0.15 }, // Bottom-right
        ];

        testPositions.forEach((config, index) => {
            // Create a simple box
            const geometry = new THREE.BoxGeometry(1, 1, 1);
            const material = new THREE.MeshStandardMaterial({
                color: config.color,
                metalness: 0.3,
                roughness: 0.7
            });
            const mesh = new THREE.Mesh(geometry, material);

            // Position using anamorphic projection
            this.projector.positionElement(
                mesh,
                config.target2D,
                { min: 4 + index * 2, max: 6 + index * 2 }, // Vary depth
                config.size
            );

            this.scene.add(mesh);
            this.elements.push(mesh);
        });

        // Add a text label at center for reference
        const textSprite = this.createTextSprite('DREAM', 0xffffff);
        this.projector.positionElement(
            textSprite,
            { x: 0.5, y: 0.3 },
            { min: 3, max: 4 },
            0.3
        );
        this.scene.add(textSprite);
        this.elements.push(textSprite);

        console.log('[AnamorphicScene] Test composition created with', this.elements.length, 'elements');
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
        this.animatedElements = [];
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

        // Update controls
        this.controls.update();

        // Update animated elements (shaders, etc.)
        const time = performance.now() * 0.001;
        for (const element of this.animatedElements) {
            if (element.userData.update) {
                element.userData.update(time);
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
