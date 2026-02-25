/**
 * ElementFactory.js
 *
 * Factory for creating different element types in anamorphic compositions.
 * Provides unified interface for creating meshes, images, text, and shaders.
 */

import * as THREE from 'three';
import { GLBMeshElement } from './elements/GLBMeshElement.js';
import { ImagePlaneElement } from './elements/ImagePlaneElement.js';
import { Text3DElement } from './elements/Text3DElement.js';
import { ShaderPlaneElement } from './elements/ShaderPlaneElement.js';
import { CurveTextFlow } from './effects/CurveTextFlow.js';
import { PointCloudDissolver } from './effects/PointCloudDissolver.js';

export class ElementFactory {
    constructor() {
        // Element type registry
        this.types = {
            'glb_mesh': GLBMeshElement,
            'image_plane': ImagePlaneElement,
            'text_3d': Text3DElement,
            'shader_plane': ShaderPlaneElement,
            // Aliases
            'mesh': GLBMeshElement,
            'image': ImagePlaneElement,
            'text': Text3DElement,
            'shader': ShaderPlaneElement
        };

        // Effect classes (handled specially)
        this.effects = {
            'curve_text': CurveTextFlow,
            'point_cloud': PointCloudDissolver
        };
    }

    /**
     * Create an element from configuration.
     * @param {object} config - Element configuration with 'type' property
     * @returns {Promise<THREE.Object3D>} - The created 3D object
     */
    async create(config) {
        // Check for effect types first
        if (this.effects[config.type]) {
            return await this.createEffect(config);
        }

        const ElementClass = this.types[config.type];

        if (!ElementClass) {
            console.warn(`[ElementFactory] Unknown element type: ${config.type}`);
            return null;
        }

        try {
            const element = new ElementClass(config);

            // Some elements (like ShaderPlaneElement) have synchronous load
            if (element.load.constructor.name === 'AsyncFunction') {
                return await element.load();
            } else {
                return element.load();
            }
        } catch (error) {
            console.error(`[ElementFactory] Failed to create ${config.type}:`, error);
            return null;
        }
    }

    /**
     * Create an effect element (CurveTextFlow, PointCloudDissolver).
     * @param {object} config - Effect configuration
     * @returns {Promise<THREE.Object3D>} - The effect group/object
     */
    async createEffect(config) {
        const EffectClass = this.effects[config.type];

        if (!EffectClass) {
            console.warn(`[ElementFactory] Unknown effect type: ${config.type}`);
            return null;
        }

        try {
            if (config.type === 'curve_text') {
                // CurveTextFlow: orbiting text from words
                const effect = new CurveTextFlow({
                    fontSize: config.fontSize || 0.12,
                    orbitSpeed: config.orbitSpeed || 0.08,
                    numCurves: config.numCurves || 3,
                    curveRadius: config.curveRadius || 1.2,
                    curveHeight: config.curveHeight || 0.8,
                    textColor: config.textColor || 0xffffff,
                    useSprites: config.useSprites !== false,
                    staggerDelay: config.staggerDelay || 0.2
                });

                const words = config.words || [];
                const center = config.center ?
                    new THREE.Vector3(config.center.x || 0, config.center.y || 0, config.center.z || 0) :
                    new THREE.Vector3(0, 0, 0);

                const group = await effect.init(words, center);
                group.userData.effectType = 'curve_text';
                group.userData.effect = effect;

                return group;

            } else if (config.type === 'point_cloud') {
                // PointCloudDissolver: mesh to particles effect
                // This is applied TO a mesh, so we store the config for later
                const effect = new PointCloudDissolver({
                    particleSize: config.particleSize || 0.015,
                    particleColor: config.particleColor || 0xffffff,
                    scatterRadius: config.scatterRadius || 1.5,
                    turbulence: config.turbulence || 0.3,
                    dissolveDuration: config.dissolveDuration || 2.5,
                    reformDuration: config.reformDuration || 3.0,
                    useAdditiveBlending: config.additive !== false
                });

                // Store for later application to mesh
                const placeholder = new THREE.Group();
                placeholder.userData.effectType = 'point_cloud';
                placeholder.userData.effect = effect;
                placeholder.userData.effectConfig = config;

                return placeholder;
            }

        } catch (error) {
            console.error(`[ElementFactory] Failed to create effect ${config.type}:`, error);
            return null;
        }

        return null;
    }

    /**
     * Create multiple elements from an array of configs.
     * @param {Array} configs - Array of element configurations
     * @returns {Promise<Array>} - Array of created objects
     */
    async createAll(configs) {
        const elements = [];

        for (const config of configs) {
            const element = await this.create(config);
            if (element) {
                elements.push(element);
            }
        }

        return elements;
    }

    /**
     * Register a custom element type.
     * @param {string} name - Type name
     * @param {class} ElementClass - Element class with load() method
     */
    register(name, ElementClass) {
        this.types[name] = ElementClass;
    }
}
