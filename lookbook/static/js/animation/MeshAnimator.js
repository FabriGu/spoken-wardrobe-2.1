/**
 * MeshAnimator.js
 *
 * Animation system for GLB meshes - makes clothing breathe, float, and distort.
 * Adds life to static 3D models through vertex displacement and transformations.
 */

import * as THREE from 'three';

// Simplex noise implementation for organic movement
const SIMPLEX_NOISE = `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    
    i = mod289(i);
    vec4 p = permute(permute(permute(
        i.z + vec4(0.0, i1.z, i2.z, 1.0))
        + i.y + vec4(0.0, i1.y, i2.y, 1.0))
        + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    
    vec4 x = x_ *ns.x + ns.yyyy;
    vec4 y = y_ *ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x;
    p1 *= norm.y;
    p2 *= norm.z;
    p3 *= norm.w;
    
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
`;

export class MeshAnimator {
    constructor(mesh, options = {}) {
        this.mesh = mesh;
        this.options = {
            // Floating animation
            floatEnabled: options.floatEnabled !== false,
            floatSpeed: options.floatSpeed || 0.8,
            floatAmplitude: options.floatAmplitude || 0.1,
            
            // Breathing animation
            breatheEnabled: options.breatheEnabled !== false,
            breatheSpeed: options.breatheSpeed || 1.2,
            breatheAmplitude: options.breatheAmplitude || 0.02,
            
            // Rotation drift
            rotationEnabled: options.rotationEnabled || false,
            rotationSpeed: options.rotationSpeed || 0.2,
            rotationAxis: options.rotationAxis || new THREE.Vector3(0, 1, 0),
            
            // Glitch effect
            glitchEnabled: options.glitchEnabled || false,
            glitchFrequency: options.glitchFrequency || 0.1,
            glitchIntensity: options.glitchIntensity || 0.05,
            
            // Dissolve effect
            dissolveEnabled: options.dissolveEnabled || false,
            dissolveSpeed: options.dissolveSpeed || 0.3,
            
            ...options
        };
        
        this.time = 0;
        this.originalPosition = mesh.position.clone();
        this.originalRotation = mesh.rotation.clone();
        this.originalScale = mesh.scale.clone();
        
        // Store references to materials
        this.materials = [];
        this.mesh.traverse((child) => {
            if (child.isMesh && child.material) {
                this.materials.push(child.material);
            }
        });
        
        // Setup effects
        if (this.options.dissolveEnabled) {
            this.setupDissolve();
        }
        
        if (this.options.glitchEnabled) {
            this.setupGlitch();
        }
    }

    /**
     * Update animation
     */
    update(deltaTime) {
        this.time += deltaTime;
        
        if (this.options.floatEnabled) {
            this.animateFloat();
        }
        
        if (this.options.breatheEnabled) {
            this.animateBreathe();
        }
        
        if (this.options.rotationEnabled) {
            this.animateRotation();
        }
        
        if (this.options.glitchEnabled) {
            this.animateGlitch();
        }
        
        if (this.options.dissolveEnabled) {
            this.animateDissolve();
        }
    }

    /**
     * Floating animation - gentle up/down motion
     */
    animateFloat() {
        const { floatSpeed, floatAmplitude } = this.options;
        
        // Sine wave floating
        const yOffset = Math.sin(this.time * floatSpeed) * floatAmplitude;
        
        // Add slight horizontal drift for organic feel
        const xOffset = Math.cos(this.time * floatSpeed * 0.7) * floatAmplitude * 0.3;
        const zOffset = Math.sin(this.time * floatSpeed * 0.5) * floatAmplitude * 0.2;
        
        this.mesh.position.set(
            this.originalPosition.x + xOffset,
            this.originalPosition.y + yOffset,
            this.originalPosition.z + zOffset
        );
    }

    /**
     * Breathing animation - subtle scale pulsing
     */
    animateBreathe() {
        const { breatheSpeed, breatheAmplitude } = this.options;
        
        // Breathing cycle
        const breath = Math.sin(this.time * breatheSpeed) * breatheAmplitude + 1.0;
        
        // Scale uniformly for breathing effect
        this.mesh.scale.copy(this.originalScale).multiplyScalar(breath);
    }

    /**
     * Rotation drift - slow continuous rotation
     */
    animateRotation() {
        const { rotationSpeed, rotationAxis } = this.options;
        
        // Apply rotation on top of original
        this.mesh.rotation.copy(this.originalRotation);
        
        // Add drift rotation
        const angle = this.time * rotationSpeed;
        this.mesh.rotateOnAxis(rotationAxis, angle);
        
        // Add secondary wobble
        this.mesh.rotateX(Math.sin(this.time * rotationSpeed * 0.5) * 0.05);
        this.mesh.rotateZ(Math.cos(this.time * rotationSpeed * 0.3) * 0.05);
    }

    /**
     * Glitch animation - sudden displacements
     */
    animateGlitch() {
        const { glitchFrequency, glitchIntensity } = this.options;
        
        // Random glitch trigger
        const glitchThreshold = 1.0 - glitchFrequency;
        const noise = Math.random();
        
        if (noise > glitchThreshold) {
            // Apply glitch displacement
            const glitchX = (Math.random() - 0.5) * glitchIntensity * 2;
            const glitchY = (Math.random() - 0.5) * glitchIntensity * 2;
            const glitchZ = (Math.random() - 0.5) * glitchIntensity;
            
            this.mesh.position.x += glitchX;
            this.mesh.position.y += glitchY;
            this.mesh.position.z += glitchZ;
            
            // RGB split effect on materials
            this.materials.forEach(mat => {
                if (mat.emissive) {
                    const r = Math.random();
                    mat.emissive.setRGB(r > 0.5 ? 1 : 0, r > 0.3 && r < 0.7 ? 1 : 0, r < 0.5 ? 1 : 0);
                }
            });
        } else {
            // Reset emissive
            this.materials.forEach(mat => {
                if (mat.emissive && mat.userData.originalEmissive) {
                    mat.emissive.copy(mat.userData.originalEmissive);
                }
            });
        }
    }

    /**
     * Dissolve animation - transparency pattern reveal
     */
    animateDissolve() {
        const { dissolveSpeed } = this.options;
        
        // Oscillating dissolve
        const dissolve = (Math.sin(this.time * dissolveSpeed) + 1) * 0.5;
        
        this.materials.forEach(mat => {
            if (mat.transparent !== undefined) {
                mat.transparent = true;
                // Base opacity with dissolve modulation
                const baseOpacity = mat.userData.baseOpacity || 1.0;
                mat.opacity = baseOpacity * (0.5 + dissolve * 0.5);
                mat.needsUpdate = true;
            }
        });
    }

    /**
     * Setup dissolve materials
     */
    setupDissolve() {
        this.materials.forEach(mat => {
            mat.userData.baseOpacity = mat.opacity || 1.0;
            mat.transparent = true;
        });
    }

    /**
     * Setup glitch materials
     */
    setupGlitch() {
        this.materials.forEach(mat => {
            if (mat.emissive) {
                mat.userData.originalEmissive = mat.emissive.clone();
            }
        });
    }

    /**
     * Reset to original state
     */
    reset() {
        this.mesh.position.copy(this.originalPosition);
        this.mesh.rotation.copy(this.originalRotation);
        this.mesh.scale.copy(this.originalScale);
    }

    /**
     * Set animation intensity (0-1)
     */
    setIntensity(intensity) {
        this.options.floatAmplitude *= intensity;
        this.options.breatheAmplitude *= intensity;
        this.options.glitchIntensity *= intensity;
    }

    /**
     * Create animator for a mesh (static factory method)
     */
    static create(mesh, preset = 'dreamy') {
        const presets = {
            'dreamy': {
                floatEnabled: true,
                floatSpeed: 0.5,
                floatAmplitude: 0.15,
                breatheEnabled: true,
                breatheSpeed: 0.8,
                rotationEnabled: true,
                rotationSpeed: 0.1
            },
            'chaotic': {
                floatEnabled: true,
                floatSpeed: 2.0,
                floatAmplitude: 0.2,
                glitchEnabled: true,
                glitchFrequency: 0.15,
                glitchIntensity: 0.1,
                rotationEnabled: true,
                rotationSpeed: 0.5
            },
            'ethereal': {
                floatEnabled: true,
                floatSpeed: 0.3,
                floatAmplitude: 0.25,
                breatheEnabled: true,
                breatheSpeed: 0.5,
                dissolveEnabled: true
            },
            'aggressive': {
                floatEnabled: true,
                floatSpeed: 3.0,
                floatAmplitude: 0.1,
                glitchEnabled: true,
                glitchFrequency: 0.3,
                glitchIntensity: 0.15,
                rotationEnabled: true,
                rotationSpeed: 1.0
            },
            'meditative': {
                floatEnabled: true,
                floatSpeed: 0.2,
                floatAmplitude: 0.05,
                breatheEnabled: true,
                breatheSpeed: 0.4,
                breatheAmplitude: 0.01,
                rotationEnabled: true,
                rotationSpeed: 0.05
            }
        };
        
        const options = presets[preset] || presets['dreamy'];
        return new MeshAnimator(mesh, options);
    }
}

export default MeshAnimator;
