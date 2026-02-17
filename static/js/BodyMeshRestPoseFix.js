/**
 * BodyMeshRestPoseFix - Fixes body meshes exported with posed bones
 * 
 * The lowpoly_rigged_full_v1.glb has bones that are NOT in rest pose.
 * This module extracts the bind pose from the skeleton and resets bones to rest.
 */

import * as THREE from 'three';

export class BodyMeshRestPoseFix {
    /**
     * Reset a skinned mesh's skeleton to rest pose
     * 
     * The issue: The GLB was exported with bones already posed (A-pose or similar).
     * When we bind clothing to this skeleton, the inverse bind matrices are wrong.
     * 
     * Solution: Reset bones to identity, recalculate bind matrices.
     */
    static resetToRestPose(skinnedMesh) {
        if (!skinnedMesh || !skinnedMesh.skeleton) {
            console.warn('[BodyMeshRestPoseFix] No skeleton to reset');
            return;
        }

        const skeleton = skinnedMesh.skeleton;
        const bones = skeleton.bones;

        console.log('[BodyMeshRestPoseFix] Resetting skeleton to rest pose...');
        console.log(`[BodyMeshRestPoseFix] Before: ${bones.filter(b => !this.isBoneAtRest(b)).length} non-rest bones`);

        // Store current world matrices for reference
        const originalWorldMatrices = bones.map(bone => bone.matrixWorld.clone());

        // Reset each bone to identity in local space
        bones.forEach((bone, i) => {
            // Store original for debugging
            bone.userData.originalPosition = bone.position.clone();
            bone.userData.originalQuaternion = bone.quaternion.clone();
            bone.userData.originalScale = bone.scale.clone();

            // Reset to identity
            bone.position.set(0, 0, 0);
            bone.quaternion.set(0, 0, 0, 1);
            bone.scale.set(1, 1, 1);
            
            // Update local matrix
            bone.updateMatrix();
        });

        // Update world matrices from root
        skinnedMesh.updateMatrixWorld(true);
        skeleton.update();

        // Recalculate inverse bind matrices
        // This is CRITICAL - it recomputes the bind pose
        skeleton.calculateInverses();

        console.log(`[BodyMeshRestPoseFix] After: ${bones.filter(b => !this.isBoneAtRest(b)).length} non-rest bones`);
        console.log('[BodyMeshRestPoseFix] Skeleton reset complete');

        return originalWorldMatrices;
    }

    /**
     * Check if a bone is at rest pose (identity matrix)
     */
    static isBoneAtRest(bone) {
        const isIdentity = bone.matrixWorld.elements.every((v, idx) => {
            const expected = idx === 0 || idx === 5 || idx === 10 || idx === 15 ? 1 : 0;
            return Math.abs(v - expected) < 0.001;
        });
        return isIdentity;
    }

    /**
     * Alternative: Apply the inverse of current pose to get to rest
     * 
     * Use this if resetting to identity breaks the mesh
     */
    static applyInversePose(skinnedMesh) {
        if (!skinnedMesh || !skinnedMesh.skeleton) {
            return;
        }

        const skeleton = skinnedMesh.skeleton;
        
        console.log('[BodyMeshRestPoseFix] Applying inverse pose...');

        // For each bone, apply the inverse of its current world transform
        skeleton.bones.forEach((bone, i) => {
            const worldMatrix = bone.matrixWorld.clone();
            const inverseWorld = worldMatrix.clone().invert();
            
            // Decompose inverse world to local transform
            const pos = new THREE.Vector3();
            const quat = new THREE.Quaternion();
            const scale = new THREE.Vector3();
            inverseWorld.decompose(pos, quat, scale);
            
            bone.position.copy(pos);
            bone.quaternion.copy(quat);
            bone.scale.copy(scale);
            bone.updateMatrix();
        });

        skinnedMesh.updateMatrixWorld(true);
        skeleton.update();
        skeleton.calculateInverses();

        console.log('[BodyMeshRestPoseFix] Inverse pose applied');
    }

    /**
     * Create a completely new skeleton with proper rest pose
     * 
     * This is the nuclear option - creates a fresh skeleton
     */
    static createRestPoseSkeleton(skinnedMesh) {
        if (!skinnedMesh || !skinnedMesh.skeleton) {
            return null;
        }

        const originalBones = skinnedMesh.skeleton.bones;
        
        // Create new bone hierarchy
        const newBones = originalBones.map(origBone => {
            const newBone = new THREE.Bone();
            newBone.name = origBone.name;
            newBone.position.copy(origBone.position); // Keep positions for hierarchy
            return newBone;
        });

        // Rebuild hierarchy
        originalBones.forEach((origBone, i) => {
            const newBone = newBones[i];
            origBone.children.forEach(child => {
                const childIndex = originalBones.indexOf(child);
                if (childIndex >= 0) {
                    newBone.add(newBones[childIndex]);
                }
            });
        });

        // Create new skeleton
        const newSkeleton = new THREE.Skeleton(newBones);
        
        // Update bind matrices (will be identity-based)
        newSkeleton.calculateInverses();

        console.log('[BodyMeshRestPoseFix] Created new rest-pose skeleton');
        
        return newSkeleton;
    }

    /**
     * Verify skeleton is in rest pose
     */
    static verifyRestPose(skinnedMesh) {
        if (!skinnedMesh || !skinnedMesh.skeleton) {
            return false;
        }

        const nonRestBones = skinnedMesh.skeleton.bones.filter(bone => !this.isBoneAtRest(bone));
        
        if (nonRestBones.length > 0) {
            console.warn(`[BodyMeshRestPoseFix] ${nonRestBones.length} bones NOT in rest pose:`);
            nonRestBones.forEach(b => console.warn(`  - ${b.name}`));
            return false;
        }

        console.log('[BodyMeshRestPoseFix] ✓ All bones in rest pose');
        return true;
    }
}
