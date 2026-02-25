/**
 * ShaderLibrary.js
 *
 * Comprehensive shader collection for the Dreamwear Lookbook.
 * Each shader is designed to embody chaos, dreams, and digital artifacts.
 */

import * as THREE from 'three';

// ============================================================================
// NOISE FUNCTIONS (Shared utilities)
// ============================================================================

const NOISE_GLSL = `
// Simplex 3D Noise
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

// Random function (returns float)
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

// Random function (returns vec2)
vec2 random2(vec2 st) {
    return fract(sin(vec2(
        dot(st, vec2(127.1, 311.7)),
        dot(st, vec2(269.5, 183.3))
    )) * 43758.5453);
}

// Voronoi noise
vec2 voronoi(vec2 x) {
    vec2 n = floor(x);
    vec2 f = fract(x);

    vec2 mg, mr;
    float md = 8.0;

    for(int j = -1; j <= 1; j++) {
        for(int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = random2(n + g) * 0.5 + 0.5;
            vec2 r = g + o - f;
            float d = dot(r, r);

            if(d < md) {
                md = d;
                mr = r;
                mg = g;
            }
        }
    }

    return mr;
}
`;

// ============================================================================
// SHADER DEFINITIONS
// ============================================================================

export const SHADERS = {
    // ========================================================================
    // 1. DREAM BLUR - Ethereal, soft, breathing glow
    // ========================================================================
    dreamBlur: {
        name: 'Dream Blur',
        description: 'Ethereal multi-layer blur with breathing animation',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            color: { value: new THREE.Color(0xffffff) },
            blurIntensity: { value: 0.03 },
            breathSpeed: { value: 1.0 }
        },
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
            uniform float blurIntensity;
            uniform float breathSpeed;
            varying vec2 vUv;
            
            void main() {
                vec2 center = vUv - 0.5;
                float dist = length(center);
                
                // Breathing animation
                float breath = sin(time * breathSpeed) * 0.5 + 0.5;
                float pulse = 0.8 + breath * 0.4;
                
                // Multi-ring blur effect
                float rings = 0.0;
                for(float i = 1.0; i <= 5.0; i++) {
                    float ring = smoothstep(0.5 - i * blurIntensity, 0.5 - (i-1.0) * blurIntensity, dist);
                    ring *= 1.0 - smoothstep(0.5 - (i-1.0) * blurIntensity, 0.5 - (i-2.0) * blurIntensity, dist);
                    rings += ring * (1.0 - i * 0.15);
                }
                
                // Soft edge falloff
                float alpha = (1.0 - smoothstep(0.0, 0.5, dist)) * pulse * opacity;
                
                // Dreamy color variation
                vec3 finalColor = color * (1.0 + breath * 0.2);
                
                gl_FragColor = vec4(finalColor, alpha * rings);
            }
        `,
        presets: [
            { blurIntensity: 0.02, breathSpeed: 0.5, opacity: 0.4 },
            { blurIntensity: 0.05, breathSpeed: 1.5, opacity: 0.7 },
            { blurIntensity: 0.03, breathSpeed: 2.0, opacity: 0.5, color: 0xff69b4 }
        ]
    },

    // ========================================================================
    // 2. GLITCH DISPLACEMENT - Digital corruption
    // ========================================================================
    glitch: {
        name: 'Glitch',
        description: 'RGB split, block displacement, scan lines',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.8 },
            glitchIntensity: { value: 0.5 },
            speed: { value: 3.0 },
            seed: { value: 0 }
        },
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
            uniform float glitchIntensity;
            uniform float speed;
            uniform float seed;
            varying vec2 vUv;
            
            float random(vec2 st) {
                return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
            }
            
            void main() {
                vec2 uv = vUv;
                
                // Block glitch
                float blockSize = 20.0;
                vec2 blockUv = floor(uv * blockSize) / blockSize;
                float blockNoise = random(blockUv + floor(time * speed) + seed);
                
                // Random displacement
                float glitch = step(1.0 - glitchIntensity * 0.3, blockNoise);
                vec2 displacement = vec2(
                    random(blockUv + 1.0) - 0.5,
                    random(blockUv + 2.0) - 0.5
                ) * glitch * glitchIntensity * 0.1;
                
                uv += displacement;
                
                // RGB split based on glitch intensity
                float rgbSplit = glitch * glitchIntensity * 0.05;
                
                float r = 1.0 - smoothstep(0.0, 0.5, length((uv - 0.5) * (1.0 + rgbSplit)));
                float g = 1.0 - smoothstep(0.0, 0.5, length(uv - 0.5));
                float b = 1.0 - smoothstep(0.0, 0.5, length((uv - 0.5) * (1.0 - rgbSplit)));
                
                // Scan lines
                float scanLine = sin(uv.y * 200.0 + time * 10.0) * 0.1 + 0.9;
                
                // Digital noise
                float noise = random(uv + time) * glitch * 0.5;
                
                vec3 color = vec3(r, g, b) * scanLine + noise;
                float alpha = (r + g + b) / 3.0 * opacity;
                
                gl_FragColor = vec4(color, alpha);
            }
        `,
        presets: [
            { glitchIntensity: 0.3, speed: 2.0 },
            { glitchIntensity: 0.7, speed: 5.0 },
            { glitchIntensity: 0.5, speed: 1.0 }
        ]
    },

    // ========================================================================
    // 3. KINETIC LIQUID - Flowing, organic movement
    // ========================================================================
    kineticLiquid: {
        name: 'Kinetic Liquid',
        description: 'Fluid, wave-like distortion with organic flow',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            color: { value: new THREE.Color(0x00ffff) },
            flowSpeed: { value: 1.0 },
            waveIntensity: { value: 0.1 }
        },
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
            uniform float flowSpeed;
            uniform float waveIntensity;
            varying vec2 vUv;
            
            float random(vec2 st) {
                return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
            }
            
            void main() {
                vec2 uv = vUv;
                
                // Multi-layer wave distortion
                float wave1 = sin(uv.y * 10.0 + time * flowSpeed) * waveIntensity;
                float wave2 = sin(uv.x * 8.0 - time * flowSpeed * 0.7) * waveIntensity * 0.5;
                float wave3 = sin((uv.x + uv.y) * 15.0 + time * flowSpeed * 1.3) * waveIntensity * 0.3;
                
                uv.x += wave1 + wave2 + wave3;
                uv.y += wave2 - wave1 * 0.5;
                
                // Organic blob shape
                vec2 center = uv - 0.5;
                float angle = atan(center.y, center.x);
                float radius = length(center);
                
                // Distort radius with noise-like waves
                float distortion = sin(angle * 5.0 + time * flowSpeed) * 0.1;
                distortion += sin(angle * 3.0 - time * flowSpeed * 0.5) * 0.15;
                
                float shape = 1.0 - smoothstep(0.3 + distortion, 0.5 + distortion, radius);
                
                // Color variation based on position
                vec3 finalColor = color * (1.0 + sin(time * 0.5) * 0.2);
                finalColor += vec3(0.1) * sin(angle * 10.0 + time);
                
                // Edge shimmer
                float shimmer = sin(radius * 50.0 - time * 5.0) * 0.1 + 0.9;
                
                gl_FragColor = vec4(finalColor * shimmer, shape * opacity);
            }
        `,
        presets: [
            { flowSpeed: 0.8, waveIntensity: 0.05, color: 0x00ced1 },
            { flowSpeed: 2.0, waveIntensity: 0.15, color: 0xff1493 },
            { flowSpeed: 1.2, waveIntensity: 0.08, color: 0xffd700 }
        ]
    },

    // ========================================================================
    // 4. CHROMATIC ABERRATION - RGB split with distortion
    // ========================================================================
    chromatic: {
        name: 'Chromatic Aberration',
        description: 'Prismatic RGB separation with radial distortion',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.7 },
            aberration: { value: 0.1 },
            pulseSpeed: { value: 1.0 }
        },
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
            uniform float aberration;
            uniform float pulseSpeed;
            varying vec2 vUv;
            
            void main() {
                vec2 center = vUv - 0.5;
                float dist = length(center);
                float angle = atan(center.y, center.x);
                
                // Pulsing effect
                float pulse = sin(time * pulseSpeed) * 0.5 + 0.5;
                float pulse2 = sin(time * pulseSpeed * 1.3 + 2.0) * 0.5 + 0.5;
                
                // RGB channels with different radial offsets
                float r = 1.0 - smoothstep(0.0, 0.5, abs(dist - (0.25 + pulse * aberration * 0.5)));
                float g = 1.0 - smoothstep(0.0, 0.5, abs(dist - 0.25));
                float b = 1.0 - smoothstep(0.0, 0.5, abs(dist - (0.25 - pulse2 * aberration * 0.5)));
                
                // Angular color variation
                vec3 rgb = vec3(r, g, b);
                rgb *= 0.8 + 0.4 * sin(angle * 3.0 + time);
                
                // Outer glow
                float glow = 1.0 - smoothstep(0.3, 0.5, dist);
                
                gl_FragColor = vec4(rgb, glow * opacity);
            }
        `,
        presets: [
            { aberration: 0.15, pulseSpeed: 1.0 },
            { aberration: 0.25, pulseSpeed: 2.0 },
            { aberration: 0.08, pulseSpeed: 0.5 }
        ]
    },

    // ========================================================================
    // 5. NOISE FIELD - Perlin noise-based texture
    // ========================================================================
    noiseField: {
        name: 'Noise Field',
        description: 'Flowing Perlin noise with color mapping',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            color1: { value: new THREE.Color(0x000000) },
            color2: { value: new THREE.Color(0xffffff) },
            speed: { value: 0.5 },
            scale: { value: 3.0 }
        },
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: NOISE_GLSL + `
            uniform float time;
            uniform float opacity;
            uniform vec3 color1;
            uniform vec3 color2;
            uniform float speed;
            uniform float scale;
            varying vec2 vUv;
            
            void main() {
                // Animated noise
                float n1 = snoise(vec3(vUv * scale, time * speed));
                float n2 = snoise(vec3(vUv * scale * 2.0 + 100.0, time * speed * 1.3));
                float n3 = snoise(vec3(vUv * scale * 0.5 + 200.0, time * speed * 0.7));
                
                // Combine noise octaves
                float noise = n1 * 0.5 + n2 * 0.3 + n3 * 0.2;
                noise = noise * 0.5 + 0.5; // Normalize to 0-1
                
                // Color mapping
                vec3 color = mix(color1, color2, noise);
                
                // Add some turbulence
                float turbulence = abs(n2 - n1) * 2.0;
                color += turbulence * 0.1;
                
                // Soft edge
                float dist = length(vUv - 0.5);
                float alpha = (1.0 - smoothstep(0.3, 0.5, dist)) * opacity;
                
                gl_FragColor = vec4(color, alpha);
            }
        `,
        presets: [
            { scale: 2.0, speed: 0.3, color1: 0x000000, color2: 0x8b5cf6 },
            { scale: 5.0, speed: 1.0, color1: 0xff1493, color2: 0x00ff7f },
            { scale: 1.5, speed: 0.2, color1: 0x000000, color2: 0xffffff }
        ]
    },

    // ========================================================================
    // 6. SCAN LINE - Retro CRT / Digital interference
    // ========================================================================
    scanLine: {
        name: 'Scan Lines',
        description: 'Horizontal scan lines with vertical hold artifacts',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.5 },
            lineDensity: { value: 50.0 },
            interference: { value: 0.3 }
        },
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
            uniform float lineDensity;
            uniform float interference;
            varying vec2 vUv;
            
            float random(vec2 st) {
                return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
            }
            
            void main() {
                // Scan lines
                float scanLine = sin(vUv.y * lineDensity + time * 0.5) * 0.5 + 0.5;
                scanLine = pow(scanLine, 0.5); // Sharpen lines
                
                // Vertical hold jitter
                float jitter = sin(time * 10.0) * interference * 0.02;
                jitter *= step(0.9, random(vec2(0.0, floor(time * 5.0)))); // Random jumps
                
                float y = vUv.y + jitter;
                
                // Horizontal line artifact
                float artifact = step(0.95, random(vec2(floor(time * 3.0))));
                float artifactPos = random(vec2(floor(time * 2.0)));
                float artifactLine = 1.0 - smoothstep(0.0, 0.02, abs(y - artifactPos));
                
                // Color shift
                float r = scanLine * (1.0 + artifactLine * 0.5);
                float g = scanLine;
                float b = scanLine * (1.0 - artifactLine * 0.3);
                
                // Edge falloff
                float dist = length(vUv - 0.5);
                float alpha = (1.0 - smoothstep(0.3, 0.5, dist)) * opacity;
                
                gl_FragColor = vec4(r, g, b, alpha);
            }
        `,
        presets: [
            { lineDensity: 30.0, interference: 0.2 },
            { lineDensity: 80.0, interference: 0.5 },
            { lineDensity: 15.0, interference: 0.1 }
        ]
    },

    // ========================================================================
    // 7. VORONOI FRACTURE - Cellular patterns
    // ========================================================================
    voronoi: {
        name: 'Voronoi Fracture',
        description: 'Cracked cellular patterns with edge glow',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.7 },
            color: { value: new THREE.Color(0xff4500) },
            cellCount: { value: 5.0 },
            edgeGlow: { value: 0.3 }
        },
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
            uniform float cellCount;
            uniform float edgeGlow;
            varying vec2 vUv;
            
            vec2 hash2(vec2 p) {
                return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
            }
            
            vec2 voronoi(vec2 x) {
                vec2 n = floor(x);
                vec2 f = fract(x);
                
                float minDist = 8.0;
                vec2 minPoint;
                
                for(int j = -1; j <= 1; j++) {
                    for(int i = -1; i <= 1; i++) {
                        vec2 g = vec2(float(i), float(j));
                        vec2 o = hash2(n + g);
                        o = 0.5 + 0.5 * sin(time * 0.5 + 6.2831 * o);
                        vec2 r = g + o - f;
                        float d = dot(r, r);
                        
                        if(d < minDist) {
                            minDist = d;
                            minPoint = r;
                        }
                    }
                }
                return minPoint;
            }
            
            void main() {
                vec2 uv = vUv * cellCount;
                vec2 c = voronoi(uv);
                float dist = length(c);
                
                // Cell edges
                float edge = 1.0 - smoothstep(0.0, 0.1, dist);
                
                // Animated color variation per cell
                vec2 cellId = floor(uv) + hash2(floor(uv));
                float colorVar = sin(cellId.x * 10.0 + time) * 0.5 + 0.5;
                
                vec3 finalColor = color * (0.5 + colorVar * 0.5);
                finalColor += edgeGlow * edge;
                
                float alpha = (0.3 + edge * 0.7) * opacity;
                
                // Circular mask
                float circDist = length(vUv - 0.5);
                alpha *= 1.0 - smoothstep(0.4, 0.5, circDist);
                
                gl_FragColor = vec4(finalColor, alpha);
            }
        `,
        presets: [
            { cellCount: 3.0, edgeGlow: 0.5, color: 0xff4500 },
            { cellCount: 8.0, edgeGlow: 0.2, color: 0x9400d3 },
            { cellCount: 15.0, edgeGlow: 0.8, color: 0x00ff7f }
        ]
    },

    // ========================================================================
    // 8. PARTICLE CLOUD - Swarming particles
    // ========================================================================
    particleCloud: {
        name: 'Particle Cloud',
        description: 'Swarming, flocking particle field',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            color: { value: new THREE.Color(0xffffff) },
            particleCount: { value: 30.0 },
            swarmSpeed: { value: 2.0 }
        },
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
            uniform float particleCount;
            uniform float swarmSpeed;
            varying vec2 vUv;
            
            float particle(vec2 uv, vec2 pos, float size) {
                return 1.0 - smoothstep(0.0, size, length(uv - pos));
            }
            
            void main() {
                vec2 uv = vUv;
                float particles = 0.0;
                
                for(float i = 0.0; i < 50.0; i++) {
                    if(i >= particleCount) break;
                    
                    // Particle position with orbital motion
                    float angle = time * swarmSpeed * (0.5 + fract(i * 0.1)) + i * 6.28 / particleCount;
                    float radius = 0.1 + fract(i * 0.37) * 0.3;
                    
                    // Add some chaotic movement
                    radius += sin(time * 2.0 + i) * 0.05;
                    
                    vec2 pos = 0.5 + vec2(cos(angle), sin(angle)) * radius;
                    
                    // Particle size varies
                    float size = 0.02 + fract(i * 0.23) * 0.03;
                    
                    particles += particle(uv, pos, size);
                }
                
                // Soft particles
                particles = min(particles, 1.0);
                
                // Add glow around center
                float glow = 1.0 - smoothstep(0.0, 0.4, length(uv - 0.5));
                
                vec3 finalColor = color * (particles + glow * 0.3);
                
                gl_FragColor = vec4(finalColor, particles * opacity + glow * 0.1);
            }
        `,
        presets: [
            { particleCount: 20.0, swarmSpeed: 1.0, color: 0xffffff },
            { particleCount: 40.0, swarmSpeed: 3.0, color: 0xffd700 },
            { particleCount: 15.0, swarmSpeed: 0.5, color: 0x00ced1 }
        ]
    },

    // ========================================================================
    // 9. HOLOGRAPHIC - Iridescent interference
    // ========================================================================
    holographic: {
        name: 'Holographic',
        description: 'Rainbow iridescence with interference patterns',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            iridescence: { value: 1.0 },
            shiftSpeed: { value: 1.0 }
        },
        vertexShader: `
            varying vec2 vUv;
            varying vec3 vPosition;
            void main() {
                vUv = uv;
                vPosition = position;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float opacity;
            uniform float iridescence;
            uniform float shiftSpeed;
            varying vec2 vUv;
            
            // HSL to RGB conversion
            vec3 hsl2rgb(vec3 c) {
                vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
                return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
            }
            
            void main() {
                vec2 center = vUv - 0.5;
                float dist = length(center);
                float angle = atan(center.y, center.x);
                
                // Interference pattern
                float pattern = sin(dist * 50.0 - time * shiftSpeed) * 
                               cos(angle * 5.0 + time * shiftSpeed * 0.5);
                
                // Hue based on angle and distance
                float hue = (angle / 6.28) + dist * 2.0 + time * shiftSpeed * 0.1;
                hue = fract(hue);
                
                // Iridescent color
                vec3 iridColor = hsl2rgb(vec3(hue, 0.7, 0.6));
                
                // Add pattern to color
                iridColor += pattern * 0.2;
                
                // Radial gradient
                float alpha = (1.0 - smoothstep(0.2, 0.5, dist)) * opacity;
                
                // Sparkle effect
                float sparkle = pow(sin(dist * 100.0 + time * 10.0) * 0.5 + 0.5, 20.0) * 0.5;
                iridColor += sparkle;
                
                gl_FragColor = vec4(iridColor, alpha);
            }
        `,
        presets: [
            { iridescence: 1.0, shiftSpeed: 1.0 },
            { iridescence: 1.5, shiftSpeed: 2.5 },
            { iridescence: 0.7, shiftSpeed: 0.5 }
        ]
    },

    // ========================================================================
    // 10. DATA MOSH - Compression artifacts simulation
    // ========================================================================
    dataMosh: {
        name: 'Data Mosh',
        description: 'Compression blocks and pixel sorting',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.7 },
            blockSize: { value: 20.0 },
            corruption: { value: 0.3 }
        },
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
            uniform float blockSize;
            uniform float corruption;
            varying vec2 vUv;
            
            float random(vec2 st) {
                return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
            }
            
            void main() {
                vec2 uv = vUv;
                
                // Macro block corruption
                vec2 blockUv = floor(uv * blockSize) / blockSize;
                float blockRand = random(blockUv + floor(time));
                
                // Block displacement
                float isCorrupted = step(1.0 - corruption, blockRand);
                vec2 blockOffset = vec2(
                    random(blockUv + 1.0) - 0.5,
                    0.0
                ) * isCorrupted * 0.2;
                
                uv += blockOffset;
                
                // Pixel sorting simulation
                float sortThreshold = 0.5 + sin(time * 0.5) * 0.3;
                float brightness = length(uv - 0.5);
                float sorted = step(sortThreshold, brightness);
                
                // Stretch sorted pixels
                uv.x = mix(uv.x, floor(uv.x * 20.0) / 20.0, sorted * isCorrupted);
                
                // Color based on position + corruption
                vec3 color = vec3(0.0);
                color.r = smoothstep(0.0, 0.5, uv.x);
                color.g = smoothstep(0.0, 0.5, uv.y);
                color.b = isCorrupted;
                
                // Compression artifacts color
                color += vec3(0.2, 0.0, 0.2) * isCorrupted;
                
                // Circular mask
                float dist = length(vUv - 0.5);
                float alpha = (1.0 - smoothstep(0.3, 0.5, dist)) * opacity;
                
                gl_FragColor = vec4(color, alpha);
            }
        `,
        presets: [
            { blockSize: 15.0, corruption: 0.2 },
            { blockSize: 8.0, corruption: 0.5 },
            { blockSize: 30.0, corruption: 0.1 }
        ]
    },

    // ========================================================================
    // 11. RIPPLE DISTORTION - Water-like interference
    // ========================================================================
    ripple: {
        name: 'Ripple',
        description: 'Concentric water ripples expanding outward',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.5 },
            color: { value: new THREE.Color(0x00ffff) },
            rippleCount: { value: 5.0 },
            speed: { value: 2.0 }
        },
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
            uniform float rippleCount;
            uniform float speed;
            varying vec2 vUv;
            
            void main() {
                vec2 center = vUv - 0.5;
                float dist = length(center);
                float angle = atan(center.y, center.x);
                
                float ripples = 0.0;
                
                // Multiple expanding ripples
                for(float i = 0.0; i < 10.0; i++) {
                    if(i >= rippleCount) break;
                    
                    float offset = i / rippleCount;
                    float rippleTime = fract(time * speed * 0.1 + offset);
                    float rippleDist = rippleTime * 0.7;
                    
                    float ripple = 1.0 - smoothstep(0.0, 0.05, abs(dist - rippleDist));
                    ripple *= 1.0 - rippleTime; // Fade as it expands
                    
                    ripples += ripple;
                }
                
                // Interference pattern
                float interference = sin(dist * 50.0 - time * speed) * 0.5 + 0.5;
                interference *= ripples;
                
                // Color intensity based on ripples
                vec3 finalColor = color * (0.2 + ripples * 0.8);
                finalColor += interference * 0.3;
                
                // Soft edge
                float alpha = ripples * opacity * (1.0 - smoothstep(0.4, 0.5, dist));
                
                gl_FragColor = vec4(finalColor, alpha);
            }
        `,
        presets: [
            { rippleCount: 3.0, speed: 1.5, color: 0x00ffff },
            { rippleCount: 8.0, speed: 3.0, color: 0xff69b4 },
            { rippleCount: 5.0, speed: 0.8, color: 0xffd700 }
        ]
    },

    // ========================================================================
    // 12. MANDALA / KALEIDOSCOPE - Symmetric patterns
    // ========================================================================
    // ========================================================================
    // 12. GLOW - Simple radial glow (legacy compatibility)
    // ========================================================================
    glow: {
        name: 'Glow',
        description: 'Radial pulsing glow effect',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.5 },
            color: { value: new THREE.Color(0xffffff) },
            color2: { value: new THREE.Color(0x000000) }
        },
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
        `,
        presets: [
            { color: 0xffffff, color2: 0x000000, opacity: 0.5 },
            { color: 0xff69b4, color2: 0x000000, opacity: 0.6 },
            { color: 0x00ffff, color2: 0x000033, opacity: 0.4 }
        ]
    },

    // ========================================================================
    // 13. DIAGONAL - Striped diagonal lines (legacy compatibility)
    // ========================================================================
    diagonal: {
        name: 'Diagonal',
        description: 'Diagonal lines and strips',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.7 },
            color: { value: new THREE.Color(0xffffff) },
            angle: { value: 0.785 }, // 45 degrees
            lineWidth: { value: 0.1 }
        },
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
            uniform float angle;
            uniform float lineWidth;
            varying vec2 vUv;
            
            void main() {
                // Rotate UV
                float c = cos(angle);
                float s = sin(angle);
                vec2 rotUv = vec2(
                    vUv.x * c - vUv.y * s,
                    vUv.x * s + vUv.y * c
                );
                
                // Animated diagonal lines
                float line = step(0.5, fract(rotUv.x * 10.0 + time * 0.5));
                
                // Secondary set of lines
                float line2 = step(0.5, fract(rotUv.x * 20.0 - time * 0.3)) * 0.5;
                
                float pattern = max(line, line2);
                
                // Edge fade
                float dist = length(vUv - 0.5);
                float alpha = (1.0 - smoothstep(0.3, 0.5, dist)) * opacity;
                
                gl_FragColor = vec4(color, pattern * alpha);
            }
        `,
        presets: [
            { angle: 0.785, lineWidth: 0.1, color: 0xffffff },
            { angle: -0.785, lineWidth: 0.15, color: 0xff1493 },
            { angle: 1.047, lineWidth: 0.08, color: 0x00ff7f }
        ]
    },

    mandala: {
        name: 'Mandala',
        description: 'Rotating symmetric patterns with geometric complexity',
        uniforms: {
            time: { value: 0 },
            opacity: { value: 0.6 },
            color: { value: new THREE.Color(0xff69b4) },
            segments: { value: 6.0 },
            complexity: { value: 3.0 }
        },
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
            uniform float segments;
            uniform float complexity;
            varying vec2 vUv;
            
            void main() {
                vec2 uv = vUv - 0.5;
                
                // Polar coordinates
                float r = length(uv);
                float angle = atan(uv.y, uv.x);
                
                // Symmetry
                float symAngle = mod(angle + time * 0.2, 6.28 / segments);
                symAngle = abs(symAngle - 3.14 / segments);
                
                // Pattern based on polar coords
                float pattern = sin(r * 30.0 + time) * 
                               cos(symAngle * complexity * 5.0) * 
                               sin(r * 20.0 - time * 2.0);
                
                pattern = pattern * 0.5 + 0.5;
                
                // Rings
                float rings = sin(r * 50.0) * 0.5 + 0.5;
                
                // Combine
                float shape = pattern * rings;
                shape = smoothstep(0.3, 0.7, shape);
                
                vec3 finalColor = color * (0.3 + shape * 0.7);
                
                // Rotate color
                finalColor += 0.2 * sin(angle * segments + time);
                
                // Soft edge
                float alpha = (1.0 - smoothstep(0.4, 0.5, r)) * opacity;
                
                gl_FragColor = vec4(finalColor, alpha * shape);
            }
        `,
        presets: [
            { segments: 6.0, complexity: 2.0, color: 0xff69b4 },
            { segments: 8.0, complexity: 4.0, color: 0x8b5cf6 },
            { segments: 12.0, complexity: 1.0, color: 0x00ff7f }
        ]
    }
};

// ============================================================================
// SHADER LIBRARY MANAGER
// ============================================================================

export class ShaderLibrary {
    constructor() {
        this.shaders = SHADERS;
        this.shaderNames = Object.keys(SHADERS);
    }

    /**
     * Get a shader by name
     */
    get(name) {
        return this.shaders[name];
    }

    /**
     * Get a random shader with a random preset
     */
    getRandom() {
        const name = this.shaderNames[Math.floor(Math.random() * this.shaderNames.length)];
        const shader = this.shaders[name];
        const preset = shader.presets[Math.floor(Math.random() * shader.presets.length)];
        
        return {
            name,
            shader,
            preset: this.applyPreset(shader, preset)
        };
    }

    /**
     * Get shaders matching a mood/keyword
     */
    getForMood(mood) {
        const moodMap = {
            'chaotic': ['glitch', 'dataMosh', 'voronoi'],
            'dreamy': ['dreamBlur', 'kineticLiquid', 'holographic'],
            'digital': ['scanLine', 'glitch', 'dataMosh'],
            'organic': ['kineticLiquid', 'particleCloud', 'ripple'],
            'geometric': ['voronoi', 'mandala', 'holographic'],
            'noisy': ['noiseField', 'glitch', 'scanLine'],
            'calm': ['dreamBlur', 'ripple', 'holographic'],
            'aggressive': ['glitch', 'dataMosh', 'scanLine']
        };

        const candidates = moodMap[mood.toLowerCase()] || this.shaderNames;
        const name = candidates[Math.floor(Math.random() * candidates.length)];
        const shader = this.shaders[name];
        const preset = shader.presets[Math.floor(Math.random() * shader.presets.length)];
        
        return {
            name,
            shader,
            preset: this.applyPreset(shader, preset)
        };
    }

    /**
     * Get multiple unique shaders
     */
    getMultiple(count, avoid = []) {
        const selected = [];
        const available = this.shaderNames.filter(n => !avoid.includes(n));
        
        while (selected.length < count && available.length > 0) {
            const idx = Math.floor(Math.random() * available.length);
            const name = available.splice(idx, 1)[0];
            const shader = this.shaders[name];
            const preset = shader.presets[Math.floor(Math.random() * shader.presets.length)];
            
            selected.push({
                name,
                shader,
                preset: this.applyPreset(shader, preset)
            });
        }
        
        return selected;
    }

    /**
     * Apply preset values to shader uniforms
     */
    applyPreset(shader, preset) {
        const uniforms = {};
        
        // Copy default uniforms
        for (const [key, value] of Object.entries(shader.uniforms)) {
            if (value.value instanceof THREE.Color) {
                uniforms[key] = { value: value.value.clone() };
            } else {
                uniforms[key] = { value: value.value };
            }
        }
        
        // Apply preset overrides
        for (const [key, value] of Object.entries(preset)) {
            if (key === 'color' || key === 'color1' || key === 'color2') {
                uniforms[key] = { value: new THREE.Color(value) };
            } else if (uniforms[key]) {
                uniforms[key].value = value;
            }
        }
        
        return uniforms;
    }

    /**
     * Get all shader names for reference
     */
    getNames() {
        return this.shaderNames;
    }

    /**
     * Get shader descriptions
     */
    getDescriptions() {
        const descriptions = {};
        for (const [name, shader] of Object.entries(this.shaders)) {
            descriptions[name] = {
                name: shader.name,
                description: shader.description,
                presetCount: shader.presets.length
            };
        }
        return descriptions;
    }
}

// Export singleton instance
export const shaderLibrary = new ShaderLibrary();

export default shaderLibrary;
