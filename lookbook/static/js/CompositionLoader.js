/**
 * CompositionLoader.js
 *
 * Loads composition configuration files and manages composition state.
 */

export class CompositionLoader {
    constructor(basePath = '/compositions') {
        this.basePath = basePath;
        this.compositions = [];  // List of available composition IDs
        this.currentIndex = 0;
    }

    /**
     * Load a composition config by ID.
     * @param {string} id - Composition ID (timestamp)
     * @returns {Promise<object>} - Composition configuration
     */
    async loadConfig(id) {
        // Handle 'test' ID for test composition
        if (id === 'test') {
            return this.getTestConfig();
        }

        const url = `${this.basePath}/${id}.json`;

        try {
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const config = await response.json();
            return config;

        } catch (error) {
            console.error(`[CompositionLoader] Failed to load ${url}:`, error);
            // Return test config as fallback
            return this.getTestConfig();
        }
    }

    /**
     * Load the list of available compositions.
     * @returns {Promise<Array>} - Array of composition IDs
     */
    async loadCompositionList() {
        try {
            const response = await fetch(`${this.basePath}/index.json`);
            if (response.ok) {
                this.compositions = await response.json();
            }
        } catch (error) {
            console.warn('[CompositionLoader] Could not load composition list');
            this.compositions = [];
        }

        return this.compositions;
    }

    /**
     * Get the next composition ID.
     */
    getNext() {
        if (this.compositions.length === 0) return null;
        this.currentIndex = (this.currentIndex + 1) % this.compositions.length;
        return this.compositions[this.currentIndex];
    }

    /**
     * Get the previous composition ID.
     */
    getPrev() {
        if (this.compositions.length === 0) return null;
        this.currentIndex = (this.currentIndex - 1 + this.compositions.length) % this.compositions.length;
        return this.compositions[this.currentIndex];
    }

    /**
     * Get a test composition config for development.
     */
    getTestConfig() {
        return {
            id: 'test',
            transcription: 'Make me a red t-shirt with dreams floating around',
            keywords: ['red', 't-shirt', 'dreams', 'floating'],
            background: {
                color: '#FF1493'
            },
            camera: {
                position: [0, 0, 10],
                fov: 50,
                target: [0, 0, 0]
            },
            elements: [
                // Central clothing mesh (using a real one if available)
                {
                    type: 'glb_mesh',
                    path: '/comfyui_generated_mesh/1765268852/clothing_mesh.glb',
                    target_2d: { x: 0.5, y: 0.5 },
                    depth_range: { min: 4, max: 6 },
                    scale: 0.35
                },
                // Floating text
                {
                    type: 'text_3d',
                    text: 'RED',
                    target_2d: { x: 0.2, y: 0.25 },
                    depth_range: { min: 6, max: 10 },
                    scale: 0.15,
                    color: 0xffffff,
                    rotation: 15
                },
                {
                    type: 'text_3d',
                    text: 'DREAM',
                    target_2d: { x: 0.8, y: 0.7 },
                    depth_range: { min: 8, max: 12 },
                    scale: 0.12,
                    color: 0xffff00,
                    rotation: -10
                },
                // Shader distortion plane
                {
                    type: 'shader_plane',
                    shader: 'chromatic',
                    target_2d: { x: 0.15, y: 0.6 },
                    depth_range: { min: 5, max: 8 },
                    scale: 0.2,
                    opacity: 0.4
                },
                // Another shader
                {
                    type: 'shader_plane',
                    shader: 'glow',
                    target_2d: { x: 0.85, y: 0.3 },
                    depth_range: { min: 7, max: 12 },
                    scale: 0.25,
                    opacity: 0.3,
                    color: 0xff69b4,
                    color2: 0x8b5cf6
                },
                // Diagonal cut
                {
                    type: 'shader_plane',
                    shader: 'diagonal',
                    target_2d: { x: 0.5, y: 0.5 },
                    depth_range: { min: 2, max: 3 },
                    width: 10,
                    height: 0.3,
                    scale: 1.0,
                    opacity: 0.8,
                    color: 0xffff00,
                    angle: 45,
                    rotation: 45
                }
            ]
        };
    }
}
