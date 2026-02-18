/**
 * ShaderPlaneElement.js
 *
 * Creates shader-based planes for anamorphic compositions.
 * Transparent distortion portals, ripples, chromatic aberration, etc.
 */

import * as THREE from 'three';

// Shader library
const SHADERS = {
    // Ripple distortion effect
    distortion: {
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            uniform vec3 color;
            varying vec2 vUv;

            void main() {
                vec2 p = vUv - 0.5;
                float d = length(p);

                // Ripple pattern
                float ripple = sin(d * 20.0 - time * 3.0) * 0.5 + 0.5;

                // Fade at edges
                float alpha = (1.0 - smoothstep(0.3, 0.5, d)) * ripple * opacity;

                gl_FragColor = vec4(color, alpha);
            }
        `
    },

    // Chromatic aberration / RGB split
    chromatic: {
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            varying vec2 vUv;

            void main() {
                vec2 p = vUv - 0.5;
                float angle = atan(p.y, p.x);
                float d = length(p);

                // RGB channels offset based on angle
                float r = smoothstep(0.4, 0.5, d + sin(angle * 3.0 + time) * 0.1);
                float g = smoothstep(0.4, 0.5, d + sin(angle * 3.0 + time + 2.094) * 0.1);
                float b = smoothstep(0.4, 0.5, d + sin(angle * 3.0 + time + 4.188) * 0.1);

                float alpha = (r + g + b) / 3.0 * opacity;
                gl_FragColor = vec4(r, g, b, alpha * (1.0 - d * 2.0));
            }
        `
    },

    // Noise/static effect
    noise: {
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            uniform vec3 color;
            varying vec2 vUv;

            // Simple noise function
            float random(vec2 st) {
                return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
            }

            void main() {
                vec2 p = vUv - 0.5;
                float d = length(p);

                // Animated noise
                float n = random(vUv * 100.0 + time * 10.0);

                // Fade at edges
                float alpha = n * (1.0 - smoothstep(0.3, 0.5, d)) * opacity;

                gl_FragColor = vec4(color * n, alpha);
            }
        `
    },

    // Gradient glow
    glow: {
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            uniform vec3 color;
            uniform vec3 color2;
            varying vec2 vUv;

            void main() {
                vec2 p = vUv - 0.5;
                float d = length(p);

                // Pulsing glow
                float pulse = sin(time * 2.0) * 0.2 + 0.8;

                // Radial gradient
                float glow = 1.0 - smoothstep(0.0, 0.5, d);
                glow = pow(glow, 2.0) * pulse;

                // Color blend
                vec3 c = mix(color2, color, glow);

                gl_FragColor = vec4(c, glow * opacity);
            }
        `
    },

    // Diagonal lines (like reference images)
    diagonal: {
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            uniform vec3 color;
            uniform float lineWidth;
            uniform float angle;
            varying vec2 vUv;

            void main() {
                // Rotate UV
                float c = cos(angle);
                float s = sin(angle);
                vec2 rotUv = vec2(
                    vUv.x * c - vUv.y * s,
                    vUv.x * s + vUv.y * c
                );

                // Diagonal lines pattern
                float line = step(0.5, fract(rotUv.x * 10.0));

                gl_FragColor = vec4(color, line * opacity);
            }
        `
    }
};

export class ShaderPlaneElement {
    constructor(config) {
        this.config = config;
        this.mesh = null;
    }

    /**
     * Create the shader plane.
     * @returns {THREE.Mesh}
     */
    load() {
        const shaderName = this.config.shader || 'distortion';
        const shaderDef = SHADERS[shaderName];

        if (!shaderDef) {
            console.warn(`[ShaderPlaneElement] Unknown shader: ${shaderName}, using distortion`);
        }

        const shader = shaderDef || SHADERS.distortion;

        // Create geometry
        const width = this.config.width || 2;
        const height = this.config.height || 2;
        const geometry = new THREE.PlaneGeometry(width, height);

        // Create shader material
        const material = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                opacity: { value: this.config.opacity || 0.5 },
                color: { value: new THREE.Color(this.config.color || 0xffffff) },
                color2: { value: new THREE.Color(this.config.color2 || 0x000000) },
                lineWidth: { value: this.config.lineWidth || 0.1 },
                angle: { value: THREE.MathUtils.degToRad(this.config.angle || 45) }
            },
            vertexShader: shader.vertexShader,
            fragmentShader: shader.fragmentShader,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });

        this.mesh = new THREE.Mesh(geometry, material);

        // Store update function for animation
        this.mesh.userData.update = (time) => {
            material.uniforms.time.value = time;
        };

        // Apply initial rotation
        if (this.config.rotation) {
            this.mesh.rotation.z = THREE.MathUtils.degToRad(this.config.rotation);
        }

        return this.mesh;
    }

    /**
     * Get the mesh.
     */
    getObject() {
        return this.mesh;
    }
}

// Export shader definitions for custom use
export { SHADERS };
