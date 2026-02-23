/**
 * ShaderPlaneElement.js
 *
 * Enhanced shader-based planes for anamorphic compositions.
 * Uses the ShaderLibrary for varied, animated effects.
 */

import * as THREE from 'three';
import { shaderLibrary } from '../shaders/ShaderLibrary.js';

export class ShaderPlaneElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
        this.material = null;
    }

    /**
     * Create the shader plane with library shaders.
     * @returns {THREE.Mesh}
     */
    load() {
        const shaderName = this.config.shader || 'dreamBlur';
        let libraryResult = this.getShaderFromLibrary(shaderName);
        
        if (!libraryResult) {
            console.warn(`[ShaderPlaneElement] Shader "${shaderName}" not found, using random`);
            const random = shaderLibrary.getRandom();
            libraryResult = { shader: random.shader, uniforms: random.preset };
        }

        const { shader, uniforms } = libraryResult;

        // Create geometry
        const width = this.config.width || 2;
        const height = this.config.height || 2;
        const geometry = new THREE.PlaneGeometry(width, height, 32, 32);

        // Create shader material
        this.material = new THREE.ShaderMaterial({
            uniforms: uniforms,
            vertexShader: shader.vertexShader,
            fragmentShader: shader.fragmentShader,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: this.getBlendingMode(this.config.blendMode),
            alphaTest: 0.01
        });

        this.mesh = new THREE.Mesh(geometry, this.material);

        // Store update function for animation
        this.mesh.userData.update = (time) => {
            this.material.uniforms.time.value = time;
            
            // Optional: Add mouse interaction
            if (this.config.reactive && this.mesh.userData.mousePos) {
                const mouse = this.mesh.userData.mousePos;
                this.material.uniforms.time.value += mouse.x * 0.1;
            }
        };

        // Apply initial rotation
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }

        // Store shader info
        this.mesh.userData.shaderInfo = {
            name: shaderName,
            description: shader.description,
            originalConfig: this.config
        };

        // Add subtle floating animation if configured
        if (this.config.animated !== false) {
            this.addFloatingAnimation();
        }

        return this.mesh;
    }

    /**
     * Get shader from library, handling various selection modes
     */
    getShaderFromLibrary(shaderName) {
        // Map legacy shader names to new ones
        const legacyMap = {
            'glow': 'dreamBlur',
            'diagonal': 'glitch',
            'distortion': 'ripple',
            'noise': 'noiseField'
        };
        
        // Convert legacy names
        if (legacyMap[shaderName]) {
            shaderName = legacyMap[shaderName];
        }
        
        // Handle special selectors
        if (shaderName === 'random') {
            const random = shaderLibrary.getRandom();
            return { shader: random.shader, uniforms: random.preset };
        }
        
        if (shaderName.startsWith('mood:')) {
            const mood = shaderName.split(':')[1];
            const moodResult = shaderLibrary.getForMood(mood);
            return { shader: moodResult.shader, uniforms: moodResult.preset };
        }

        // Get specific shader
        let shader = shaderLibrary.get(shaderName);
        
        // Fallback if shader not found
        if (!shader) {
            console.warn(`[ShaderPlaneElement] Shader "${shaderName}" not found, using random`);
            const random = shaderLibrary.getRandom();
            shader = random.shader;
            return { shader: shader, uniforms: random.preset };
        }
        if (shader) {
            // Apply custom uniforms from config or use preset
            let uniforms;
            if (this.config.uniforms) {
                uniforms = shaderLibrary.applyPreset(shader, this.config.uniforms);
            } else if (this.config.presetIndex !== undefined) {
                const preset = shader.presets[this.config.presetIndex % shader.presets.length];
                uniforms = shaderLibrary.applyPreset(shader, preset);
            } else {
                // Random preset
                const preset = shader.presets[Math.floor(Math.random() * shader.presets.length)];
                uniforms = shaderLibrary.applyPreset(shader, preset);
            }
            
            // Override opacity if specified
            if (this.config.opacity !== undefined && uniforms.opacity) {
                uniforms.opacity.value = this.config.opacity;
            }
            
            return { shader, uniforms };
        }

        return null;
    }

    /**
     * Get blending mode from string
     */
    getBlendingMode(mode) {
        switch (mode) {
            case 'additive': return THREE.AdditiveBlending;
            case 'multiply': return THREE.MultiplyBlending;
            case 'subtractive': return THREE.SubtractiveBlending;
            default: return THREE.AdditiveBlending;
        }
    }

    /**
     * Add subtle floating/breathing animation
     */
    addFloatingAnimation() {
        const baseScale = this.config.scale || 1.0;
        const floatSpeed = this.config.floatSpeed || 0.5;
        const floatAmount = this.config.floatAmount || 0.05;
        
        const originalScale = this.mesh.scale.clone();
        
        this.mesh.userData.animateFloat = (time) => {
            // Breathing scale
            const breath = Math.sin(time * floatSpeed) * floatAmount + 1.0;
            this.mesh.scale.copy(originalScale).multiplyScalar(breath);
            
            // Gentle rotation drift
            if (this.config.rotationDrift) {
                this.mesh.rotation.z += Math.sin(time * floatSpeed * 0.3) * 0.001;
            }
        };
        
        // Chain with existing update
        const existingUpdate = this.mesh.userData.update;
        this.mesh.userData.update = (time) => {
            existingUpdate(time);
            if (this.mesh.userData.animateFloat) {
                this.mesh.userData.animateFloat(time);
            }
        };
    }

    /**
     * Create a multi-shader composition (multiple planes with different shaders)
     * @static
     */
    static createMultiShader(configs) {
        const group = new THREE.Group();
        
        configs.forEach((config, index) => {
            const element = new ShaderPlaneElement({
                ...config,
                shader: config.shader || 'random'
            });
            
            const mesh = element.load();
            
            // Stagger depth slightly
            if (mesh.position.z === 0) {
                mesh.position.z = -index * 0.5;
            }
            
            group.add(mesh);
        });
        
        return group;
    }

    /**
     * Get the mesh.
     */
    getObject() {
        return this.mesh;
    }

    /**
     * Update shader uniform
     */
    setUniform(name, value) {
        if (this.material && this.material.uniforms[name]) {
            this.material.uniforms[name].value = value;
        }
    }

    /**
     * Dispose of resources
     */
    dispose() {
        if (this.geometry) this.geometry.dispose();
        if (this.material) this.material.dispose();
    }
}

export default ShaderPlaneElement;
