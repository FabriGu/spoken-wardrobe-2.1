/**
 * MeshAligner - Aligns clothing mesh to body mesh for weight transfer
 * 
 * The problem: Rodin generates clothing meshes as standalone objects centered at
 * origin with arbitrary scale. The body mesh has a specific position/scale.
 * For weight transfer to work, both meshes must be in the same coordinate space.
 * 
 * Solution: Bounding box alignment
 * 1. Get bounds of both meshes
 * 2. Scale clothing to match body height
 * 3. Translate clothing to match body center
 * 4. Return transform for positioning the skinned mesh
 */

import * as THREE from 'three';

export class MeshAligner {
    /**
     * Calculate alignment transform to match clothing to body
     * 
     * @param {THREE.Mesh} bodyMesh - The body mesh (reference)
     * @param {THREE.Mesh} clothingMesh - The clothing mesh (to be aligned)
     * @returns {Object} - { scale: number, translation: Vector3 }
     */
    static calculateAlignment(bodyMesh, clothingMesh) {
        // Get bounds in world space
        bodyMesh.updateMatrixWorld(true);
        clothingMesh.updateMatrixWorld(true);

        const bodyBox = new THREE.Box3().setFromObject(bodyMesh);
        const clothingBox = new THREE.Box3().setFromObject(clothingMesh);

        const bodySize = bodyBox.getSize(new THREE.Vector3());
        const clothingSize = clothingBox.getSize(new THREE.Vector3());
        const bodyCenter = bodyBox.getCenter(new THREE.Vector3());
        const clothingCenter = clothingBox.getCenter(new THREE.Vector3());

        console.log('[MeshAligner] Body bounds:', {
            size: bodySize.toArray(),
            center: bodyCenter.toArray()
        });
        console.log('[MeshAligner] Clothing bounds:', {
            size: clothingSize.toArray(),
            center: clothingCenter.toArray()
        });

        // Calculate scale factor to match body height
        const scale = bodySize.y / clothingSize.y;
        console.log('[MeshAligner] Scale factor:', scale);

        // Calculate translation:
        // We want: clothing_center * scale + translation = body_center
        // Therefore: translation = body_center - clothing_center * scale
        const scaledClothingCenter = clothingCenter.clone().multiplyScalar(scale);
        const translation = bodyCenter.clone().sub(scaledClothingCenter);

        console.log('[MeshAligner] Translation:', translation.toArray());

        return {
            scale,
            translation,
            bodyCenter,
            clothingCenter,
            bodySize,
            clothingSize
        };
    }

    /**
     * Apply alignment transform to clothing mesh
     * 
     * @param {THREE.Mesh} clothingMesh - The clothing mesh to transform
     * @param {Object} alignment - The alignment data from calculateAlignment
     */
    static applyAlignment(clothingMesh, alignment) {
        const { scale, translation } = alignment;

        // Apply scale
        clothingMesh.scale.setScalar(scale);
        
        // Apply translation
        clothingMesh.position.copy(translation);
        
        // Update world matrix
        clothingMesh.updateMatrixWorld(true);

        console.log('[MeshAligner] Applied alignment:', {
            scale: clothingMesh.scale.toArray(),
            position: clothingMesh.position.toArray()
        });
    }

    /**
     * Reset clothing mesh to original state
     * 
     * @param {THREE.Mesh} clothingMesh - The clothing mesh to reset
     */
    static reset(clothingMesh) {
        clothingMesh.scale.set(1, 1, 1);
        clothingMesh.position.set(0, 0, 0);
        clothingMesh.rotation.set(0, 0, 0);
        clothingMesh.updateMatrixWorld(true);
        console.log('[MeshAligner] Reset clothing mesh');
    }

    /**
     * Align clothing geometry (not the mesh) for weight transfer
     * 
     * This transforms the geometry itself so weight transfer can use
     * world-space coordinates directly.
     * 
     * @param {THREE.BufferGeometry} clothingGeo - Clothing geometry
     * @param {Object} alignment - The alignment data
     * @returns {THREE.BufferGeometry} - Transformed geometry
     */
    static alignGeometry(clothingGeo, alignment) {
        const { scale, translation } = alignment;
        const alignedGeo = clothingGeo.clone();

        // Create transform matrix: scale then translate
        const scaleMatrix = new THREE.Matrix4().makeScale(scale, scale, scale);
        const translateMatrix = new THREE.Matrix4().makeTranslation(
            translation.x, translation.y, translation.z
        );
        const transformMatrix = new THREE.Matrix4().multiplyMatrices(
            translateMatrix, scaleMatrix
        );

        // Apply to geometry
        alignedGeo.applyMatrix4(transformMatrix);

        console.log('[MeshAligner] Aligned geometry');
        return alignedGeo;
    }
}
