/**
 * RestPoseSkeleton - Creates a proper rest-pose skeleton for weight transfer
 * 
 * The body mesh GLB (lowpoly_rigged_full_v1.glb) was exported with bones already
 * posed (not in rest pose). This causes weight transfer to fail because:
 * 
 * 1. Clothing vertices are matched to posed body vertices
 * 2. The skeleton's bind matrices expect rest pose
 * 3. Result: crumpled mesh
 * 
 * This module creates a NEW skeleton with proper rest-pose bind matrices.
 */

import * as THREE from 'three';

export class RestPoseSkeleton {
    /**
     * Create a new skeleton in rest pose from the body mesh's bone hierarchy
     * 
     * @param {THREE.SkinnedMesh} bodyMesh - The body mesh with posed skeleton
     * @returns {THREE.Skeleton} - A new skeleton with rest-pose bind matrices
     */
    static createFromBodyMesh(bodyMesh) {
        if (!bodyMesh || !bodyMesh.skeleton) {
            console.error('[RestPoseSkeleton] No skeleton found');
            return null;
        }

        const originalBones = bodyMesh.skeleton.bones;
        const originalBoneInverses = bodyMesh.skeleton.boneInverses;

        console.log('[RestPoseSkeleton] Creating rest-pose skeleton from', originalBones.length, 'bones');

        // Build bone hierarchy map
        const boneHierarchy = this._buildHierarchy(originalBones);

        // Create new bones at world positions from original
        // This captures the current pose as the rest pose
        const newBones = [];
        const worldMatrices = [];

        originalBones.forEach((origBone, i) => {
            const newBone = new THREE.Bone();
            newBone.name = origBone.name;
            
            // Get world matrix of original bone
            const worldMatrix = origBone.matrixWorld.clone();
            worldMatrices.push(worldMatrix);
            
            // Store world position for later
            const worldPos = new THREE.Vector3();
            const worldQuat = new THREE.Quaternion();
            const worldScale = new THREE.Vector3();
            worldMatrix.decompose(worldPos, worldQuat, worldScale);
            
            newBone.userData.worldPosition = worldPos;
            newBone.userData.worldQuaternion = worldQuat;
            newBone.userData.worldScale = worldScale;
            
            newBones.push(newBone);
        });

        // Rebuild hierarchy
        originalBones.forEach((origBone, i) => {
            const parentIndex = originalBones.indexOf(origBone.parent);
            if (parentIndex >= 0) {
                newBones[parentIndex].add(newBones[i]);
            }
        });

        // Now set local transforms so that world matrices match
        // For root bones, local = world
        // For child bones, local = parentWorld^-1 * world
        newBones.forEach((bone, i) => {
            if (bone.parent && bone.parent.isBone) {
                // Child bone
                const parentWorld = bone.parent.matrixWorld;
                const localMatrix = new THREE.Matrix4()
                    .multiplyMatrices(parentWorld.clone().invert(), worldMatrices[i]);
                
                const pos = new THREE.Vector3();
                const quat = new THREE.Quaternion();
                const scale = new THREE.Vector3();
                localMatrix.decompose(pos, quat, scale);
                
                bone.position.copy(pos);
                bone.quaternion.copy(quat);
                bone.scale.copy(scale);
            } else {
                // Root bone
                const pos = bone.userData.worldPosition;
                const quat = bone.userData.worldQuaternion;
                const scale = bone.userData.worldScale;
                
                bone.position.copy(pos);
                bone.quaternion.copy(quat);
                bone.scale.copy(scale);
            }
            bone.updateMatrix();
        });

        // Update world matrices
        newBones.forEach(bone => {
            bone.updateMatrixWorld(true);
        });

        // Create skeleton - this computes bind matrices from current pose
        const newSkeleton = new THREE.Skeleton(newBones);
        
        // The bind matrices are now computed from the current (posed) positions
        // This means the current pose IS the rest pose

        console.log('[RestPoseSkeleton] Created skeleton with rest pose = current pose');
        
        return newSkeleton;
    }

    /**
     * Alternative approach: Keep original skeleton but compute new bind matrices
     * from the current bone positions
     */
    static fixBindMatrices(bodyMesh) {
        if (!bodyMesh || !bodyMesh.skeleton) {
            return;
        }

        console.log('[RestPoseSkeleton] Fixing bind matrices...');

        const skeleton = bodyMesh.skeleton;
        
        // Update all world matrices
        bodyMesh.updateMatrixWorld(true);
        skeleton.update();

        // Recalculate bind matrices from current pose
        // This makes the current pose the "rest pose"
        skeleton.calculateInverses();

        console.log('[RestPoseSkeleton] Bind matrices recalculated');
    }

    /**
     * Build hierarchy map from flat bone array
     */
    static _buildHierarchy(bones) {
        const hierarchy = [];
        bones.forEach((bone, i) => {
            const parentIndex = bones.indexOf(bone.parent);
            hierarchy.push({
                index: i,
                name: bone.name,
                parentIndex: parentIndex
            });
        });
        return hierarchy;
    }

    /**
     * Verify skeleton is valid
     */
    static verifySkeleton(skeleton) {
        if (!skeleton) return false;

        const issues = [];

        // Check bone count matches inverse matrices
        if (skeleton.bones.length !== skeleton.boneInverses.length) {
            issues.push(`Bone count (${skeleton.bones.length}) != inverse count (${skeleton.boneInverses.length})`);
        }

        // Check for NaN in bind matrices
        skeleton.boneInverses.forEach((mat, i) => {
            if (mat.elements.some(v => isNaN(v) || !isFinite(v))) {
                issues.push(`Bone ${i} has NaN in inverse matrix`);
            }
        });

        if (issues.length > 0) {
            console.error('[RestPoseSkeleton] Verification failed:', issues);
            return false;
        }

        console.log('[RestPoseSkeleton] ✓ Skeleton verification passed');
        return true;
    }
}
