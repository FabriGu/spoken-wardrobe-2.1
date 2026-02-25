/**
 * PostProcessingManager.js
 *
 * Handles post-processing effects for the Dreamwear Lookbook.
 * Implements bloom, film grain, vignette, and chromatic aberration
 * for the "dreamy, unfinished" aesthetic.
 *
 * Uses Three.js EffectComposer with custom passes.
 */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

/**
 * Film grain + vignette + chromatic aberration combined shader
 */
const FilmShader = {
    uniforms: {
        'tDiffuse': { value: null },
        'time': { value: 0.0 },
        'intensity': { value: 0.5 },           // Overall effect intensity
        'grainIntensity': { value: 0.08 },     // Film grain strength
        'scanlineIntensity': { value: 0.05 },  // Scanline visibility
        'scanlineCount': { value: 800.0 },     // Number of scanlines
        'vignetteIntensity': { value: 0.3 },   // Vignette darkness
        'vignetteRadius': { value: 0.8 },      // Vignette radius
        'chromaticAberration': { value: 0.003 }, // RGB split amount
        'flickerIntensity': { value: 0.02 }    // Random brightness variation
    },

    vertexShader: /* glsl */`
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,

    fragmentShader: /* glsl */`
        uniform sampler2D tDiffuse;
        uniform float time;
        uniform float intensity;
        uniform float grainIntensity;
        uniform float scanlineIntensity;
        uniform float scanlineCount;
        uniform float vignetteIntensity;
        uniform float vignetteRadius;
        uniform float chromaticAberration;
        uniform float flickerIntensity;

        varying vec2 vUv;

        // Random function for grain
        float random(vec2 st) {
            return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
        }

        void main() {
            vec2 uv = vUv;

            // Chromatic aberration - split RGB channels
            float aberration = chromaticAberration * intensity;
            vec2 dir = (uv - 0.5) * aberration;

            float r = texture2D(tDiffuse, uv + dir).r;
            float g = texture2D(tDiffuse, uv).g;
            float b = texture2D(tDiffuse, uv - dir).b;

            vec3 color = vec3(r, g, b);

            // Film grain
            float grain = random(uv * time * 100.0) * grainIntensity * intensity;
            color += vec3(grain - grainIntensity * 0.5 * intensity);

            // Scanlines
            float scanline = sin(uv.y * scanlineCount + time * 5.0) * 0.5 + 0.5;
            color -= scanline * scanlineIntensity * intensity;

            // Vignette
            vec2 vignetteUV = uv * (1.0 - uv.yx);
            float vignette = vignetteUV.x * vignetteUV.y * 15.0;
            vignette = pow(vignette, vignetteIntensity * intensity + 0.1);
            color *= mix(1.0 - vignetteIntensity * intensity, 1.0, clamp(vignette / vignetteRadius, 0.0, 1.0));

            // Flicker (random brightness variation)
            float flicker = 1.0 + (random(vec2(time * 10.0, 0.0)) - 0.5) * flickerIntensity * intensity;
            color *= flicker;

            gl_FragColor = vec4(color, 1.0);
        }
    `
};

/**
 * Focus/depth of field shader (simplified)
 */
const FocusShader = {
    uniforms: {
        'tDiffuse': { value: null },
        'screenWidth': { value: 1024.0 },
        'screenHeight': { value: 1024.0 },
        'sampleDistance': { value: 0.94 },
        'waveFactor': { value: 0.00125 }
    },

    vertexShader: /* glsl */`
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,

    fragmentShader: /* glsl */`
        uniform sampler2D tDiffuse;
        uniform float screenWidth;
        uniform float screenHeight;
        uniform float sampleDistance;
        uniform float waveFactor;

        varying vec2 vUv;

        void main() {
            vec4 color, orgColor;
            orgColor = texture2D(tDiffuse, vUv);

            // Distance from center
            float dist = length(vUv - 0.5);

            // Only blur edges
            if (dist < 0.35) {
                gl_FragColor = orgColor;
                return;
            }

            float blurAmount = (dist - 0.35) * 2.0;

            vec2 d = vec2(1.0 / screenWidth, 1.0 / screenHeight) * sampleDistance * blurAmount;

            color = texture2D(tDiffuse, vUv);
            color += texture2D(tDiffuse, vUv + vec2(d.x, 0.0));
            color += texture2D(tDiffuse, vUv + vec2(-d.x, 0.0));
            color += texture2D(tDiffuse, vUv + vec2(0.0, d.y));
            color += texture2D(tDiffuse, vUv + vec2(0.0, -d.y));
            color += texture2D(tDiffuse, vUv + vec2(d.x, d.y));
            color += texture2D(tDiffuse, vUv + vec2(-d.x, d.y));
            color += texture2D(tDiffuse, vUv + vec2(d.x, -d.y));
            color += texture2D(tDiffuse, vUv + vec2(-d.x, -d.y));

            gl_FragColor = color / 9.0;
        }
    `
};

export class PostProcessingManager {
    constructor(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;

        this.composer = null;
        this.passes = {};
        this.enabled = true;

        // Default settings
        this.settings = {
            bloom: {
                enabled: true,
                strength: 0.8,
                radius: 0.4,
                threshold: 0.6
            },
            film: {
                enabled: true,
                intensity: 0.6,
                grainIntensity: 0.06,
                scanlineIntensity: 0.03,
                vignetteIntensity: 0.25,
                chromaticAberration: 0.002
            },
            focus: {
                enabled: false,
                sampleDistance: 0.94
            }
        };

        this._init();
    }

    _init() {
        const size = this.renderer.getSize(new THREE.Vector2());

        // Create composer
        this.composer = new EffectComposer(this.renderer);

        // Render pass (renders the scene)
        const renderPass = new RenderPass(this.scene, this.camera);
        this.composer.addPass(renderPass);
        this.passes.render = renderPass;

        // Bloom pass
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(size.x, size.y),
            this.settings.bloom.strength,
            this.settings.bloom.radius,
            this.settings.bloom.threshold
        );
        this.composer.addPass(bloomPass);
        this.passes.bloom = bloomPass;

        // Film pass (grain + vignette + chromatic aberration)
        const filmPass = new ShaderPass(FilmShader);
        filmPass.uniforms.intensity.value = this.settings.film.intensity;
        filmPass.uniforms.grainIntensity.value = this.settings.film.grainIntensity;
        filmPass.uniforms.scanlineIntensity.value = this.settings.film.scanlineIntensity;
        filmPass.uniforms.vignetteIntensity.value = this.settings.film.vignetteIntensity;
        filmPass.uniforms.chromaticAberration.value = this.settings.film.chromaticAberration;
        this.composer.addPass(filmPass);
        this.passes.film = filmPass;

        // Focus pass (optional edge blur)
        const focusPass = new ShaderPass(FocusShader);
        focusPass.uniforms.screenWidth.value = size.x;
        focusPass.uniforms.screenHeight.value = size.y;
        focusPass.enabled = this.settings.focus.enabled;
        this.composer.addPass(focusPass);
        this.passes.focus = focusPass;

        // Output pass (handles color space conversion)
        const outputPass = new OutputPass();
        this.composer.addPass(outputPass);
        this.passes.output = outputPass;

        console.log('[PostProcessingManager] Initialized with bloom, film grain, vignette');
    }

    /**
     * Update effects (call in animation loop)
     */
    update(time) {
        if (this.passes.film && this.passes.film.enabled) {
            this.passes.film.uniforms.time.value = time;
        }
    }

    /**
     * Render with post-processing
     */
    render() {
        if (this.enabled && this.composer) {
            this.composer.render();
        } else {
            this.renderer.render(this.scene, this.camera);
        }
    }

    /**
     * Handle window resize
     */
    resize(width, height) {
        if (this.composer) {
            this.composer.setSize(width, height);
        }

        if (this.passes.focus) {
            this.passes.focus.uniforms.screenWidth.value = width;
            this.passes.focus.uniforms.screenHeight.value = height;
        }
    }

    /**
     * Enable/disable all post-processing
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }

    /**
     * Configure bloom effect
     */
    setBloom(options) {
        if (!this.passes.bloom) return;

        if (options.enabled !== undefined) {
            this.passes.bloom.enabled = options.enabled;
            this.settings.bloom.enabled = options.enabled;
        }
        if (options.strength !== undefined) {
            this.passes.bloom.strength = options.strength;
            this.settings.bloom.strength = options.strength;
        }
        if (options.radius !== undefined) {
            this.passes.bloom.radius = options.radius;
            this.settings.bloom.radius = options.radius;
        }
        if (options.threshold !== undefined) {
            this.passes.bloom.threshold = options.threshold;
            this.settings.bloom.threshold = options.threshold;
        }
    }

    /**
     * Configure film effect (grain, vignette, chromatic aberration)
     */
    setFilm(options) {
        if (!this.passes.film) return;

        const uniforms = this.passes.film.uniforms;

        if (options.enabled !== undefined) {
            this.passes.film.enabled = options.enabled;
            this.settings.film.enabled = options.enabled;
        }
        if (options.intensity !== undefined) {
            uniforms.intensity.value = options.intensity;
            this.settings.film.intensity = options.intensity;
        }
        if (options.grainIntensity !== undefined) {
            uniforms.grainIntensity.value = options.grainIntensity;
            this.settings.film.grainIntensity = options.grainIntensity;
        }
        if (options.scanlineIntensity !== undefined) {
            uniforms.scanlineIntensity.value = options.scanlineIntensity;
            this.settings.film.scanlineIntensity = options.scanlineIntensity;
        }
        if (options.vignetteIntensity !== undefined) {
            uniforms.vignetteIntensity.value = options.vignetteIntensity;
            this.settings.film.vignetteIntensity = options.vignetteIntensity;
        }
        if (options.chromaticAberration !== undefined) {
            uniforms.chromaticAberration.value = options.chromaticAberration;
            this.settings.film.chromaticAberration = options.chromaticAberration;
        }
    }

    /**
     * Configure focus/depth of field effect
     */
    setFocus(options) {
        if (!this.passes.focus) return;

        if (options.enabled !== undefined) {
            this.passes.focus.enabled = options.enabled;
            this.settings.focus.enabled = options.enabled;
        }
        if (options.sampleDistance !== undefined) {
            this.passes.focus.uniforms.sampleDistance.value = options.sampleDistance;
            this.settings.focus.sampleDistance = options.sampleDistance;
        }
    }

    /**
     * Apply a preset configuration
     */
    applyPreset(presetName) {
        const presets = {
            // Dreamy, ethereal feel
            dreamy: {
                bloom: { enabled: true, strength: 1.2, radius: 0.6, threshold: 0.4 },
                film: { enabled: true, intensity: 0.5, grainIntensity: 0.04, scanlineIntensity: 0.0, vignetteIntensity: 0.35, chromaticAberration: 0.003 },
                focus: { enabled: true, sampleDistance: 0.96 }
            },

            // Raw, unfinished look
            raw: {
                bloom: { enabled: true, strength: 0.5, radius: 0.3, threshold: 0.7 },
                film: { enabled: true, intensity: 0.8, grainIntensity: 0.1, scanlineIntensity: 0.06, vignetteIntensity: 0.2, chromaticAberration: 0.004 },
                focus: { enabled: false }
            },

            // Clean, minimal processing
            clean: {
                bloom: { enabled: true, strength: 0.3, radius: 0.2, threshold: 0.85 },
                film: { enabled: true, intensity: 0.2, grainIntensity: 0.02, scanlineIntensity: 0.0, vignetteIntensity: 0.15, chromaticAberration: 0.001 },
                focus: { enabled: false }
            },

            // VHS/analog aesthetic
            vhs: {
                bloom: { enabled: true, strength: 0.6, radius: 0.5, threshold: 0.5 },
                film: { enabled: true, intensity: 1.0, grainIntensity: 0.12, scanlineIntensity: 0.1, vignetteIntensity: 0.3, chromaticAberration: 0.006 },
                focus: { enabled: false }
            },

            // Glitch/digital corruption
            glitch: {
                bloom: { enabled: true, strength: 0.9, radius: 0.7, threshold: 0.3 },
                film: { enabled: true, intensity: 0.9, grainIntensity: 0.15, scanlineIntensity: 0.08, vignetteIntensity: 0.1, chromaticAberration: 0.01 },
                focus: { enabled: false }
            },

            // No effects
            none: {
                bloom: { enabled: false },
                film: { enabled: false },
                focus: { enabled: false }
            }
        };

        const preset = presets[presetName];
        if (preset) {
            if (preset.bloom) this.setBloom(preset.bloom);
            if (preset.film) this.setFilm(preset.film);
            if (preset.focus) this.setFocus(preset.focus);
            console.log(`[PostProcessingManager] Applied preset: ${presetName}`);
        } else {
            console.warn(`[PostProcessingManager] Unknown preset: ${presetName}`);
        }
    }

    /**
     * Get current settings
     */
    getSettings() {
        return { ...this.settings };
    }

    /**
     * Dispose resources
     */
    dispose() {
        if (this.composer) {
            this.composer.dispose();
        }
    }
}

export default PostProcessingManager;
