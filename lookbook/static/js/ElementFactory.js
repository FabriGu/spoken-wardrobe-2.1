/**
 * ElementFactory.js
 *
 * Factory for creating different element types in anamorphic compositions.
 * Provides unified interface for creating meshes, images, text, and shaders.
 */

import { GLBMeshElement } from './elements/GLBMeshElement.js';
import { ImagePlaneElement } from './elements/ImagePlaneElement.js';
import { Text3DElement } from './elements/Text3DElement.js';
import { ShaderPlaneElement } from './elements/ShaderPlaneElement.js';

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
    }

    /**
     * Create an element from configuration.
     * @param {object} config - Element configuration with 'type' property
     * @returns {Promise<THREE.Object3D>} - The created 3D object
     */
    async create(config) {
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
