/**
 * SkeletalAnimator - Update skeleton bones from BlazePose rotation data
 *
 * This module handles real-time skeletal animation by mapping BlazePose
 * bone rotations (computed in Python) to Three.js skeleton bones.
 *
 * The 9 bones map BlazePose landmarks to the pre-rigged body mesh:
 *   - spine
 *   - left_upper_arm, left_lower_arm
 *   - right_upper_arm, right_lower_arm
 *   - left_upper_leg, left_lower_leg
 *   - right_upper_leg, right_lower_leg
 *
 * Usage:
 *   const animator = new SkeletalAnimator(skeleton);
 *   // In animation loop:
 *   animator.updateBones(boneRotations);
 */

import * as THREE from 'three';

export class SkeletalAnimator {
    constructor(skeleton, options = {}) {
        this.skeleton = skeleton;
        this.options = {
            smoothingFactor: 0.3,        // 0 = instant, 1 = no change
            lerpSpeed: 0.15,             // Interpolation speed per frame
            debug: false,                // Log debug info
            ...options
        };

        // Build bone name → bone mapping
        this.boneMap = this._buildBoneMap(skeleton);

        // Store previous rotations for smoothing
        this.prevRotations = {};

        // Rest pose rotations (captured at initialization)
        this.restPose = this._captureRestPose(skeleton);

        // Animation stats
        this.stats = {
            framesProcessed: 0,
            lastUpdateTime: 0
        };

        console.log(`[SkeletalAnimator] Initialized with ${skeleton.bones.length} bones`);
        console.log(`[SkeletalAnimator] Bone names: ${skeleton.bones.map(b => b.name).join(', ')}`);
    }

    /**
     * Build mapping from bone names to bone objects
     */
    _buildBoneMap(skeleton) {
        const map = new Map();

        for (const bone of skeleton.bones) {
            // Normalize bone name for matching
            const normalizedName = this._normalizeBoneName(bone.name);
            map.set(normalizedName, bone);

            // Also store original name mapping
            map.set(bone.name, bone);
        }

        // Log found bones for debugging
        const expectedBones = [
            'spine',
            'left_upper_arm', 'left_lower_arm',
            'right_upper_arm', 'right_lower_arm',
            'left_upper_leg', 'left_lower_leg',
            'right_upper_leg', 'right_lower_leg'
        ];

        for (const boneName of expectedBones) {
            const found = map.has(boneName) || map.has(this._normalizeBoneName(boneName));
            if (!found) {
                console.warn(`[SkeletalAnimator] Expected bone '${boneName}' not found in skeleton`);
            }
        }

        return map;
    }

    /**
     * Normalize bone name for fuzzy matching
     * Handles variations like "Spine" vs "spine", "left_upper_arm" vs "LeftUpperArm"
     */
    _normalizeBoneName(name) {
        return name.toLowerCase()
            .replace(/[\s-]/g, '_')           // Replace spaces/hyphens with underscore
            .replace(/([A-Z])/g, '_$1')       // CamelCase to snake_case
            .replace(/__+/g, '_')             // Remove double underscores
            .replace(/^_|_$/g, '');           // Trim underscores
    }

    /**
     * Capture rest pose rotations
     */
    _captureRestPose(skeleton) {
        const restPose = {};

        for (const bone of skeleton.bones) {
            restPose[bone.name] = bone.quaternion.clone();
        }

        return restPose;
    }

    /**
     * Update bones from BlazePose rotation data
     *
     * @param {Object} boneRotations - Dict mapping bone_name to {x, y, z, w} quaternion
     */
    updateBones(boneRotations) {
        if (!boneRotations) return;

        const startTime = performance.now();

        for (const [boneName, rotation] of Object.entries(boneRotations)) {
            const bone = this._findBone(boneName);

            if (!bone) {
                if (this.options.debug) {
                    console.warn(`[SkeletalAnimator] Bone '${boneName}' not found`);
                }
                continue;
            }

            // Create quaternion from rotation data
            const targetQuat = new THREE.Quaternion(
                rotation.x,
                rotation.y,
                rotation.z,
                rotation.w
            );

            // Ensure valid quaternion
            if (isNaN(targetQuat.x) || isNaN(targetQuat.y) ||
                isNaN(targetQuat.z) || isNaN(targetQuat.w)) {
                console.warn(`[SkeletalAnimator] Invalid rotation for '${boneName}'`);
                continue;
            }

            // Normalize quaternion
            targetQuat.normalize();

            // Apply rest pose offset (bone rotation = rest_rotation * pose_rotation)
            const restQuat = this.restPose[bone.name] || new THREE.Quaternion();
            const finalQuat = new THREE.Quaternion();
            finalQuat.multiplyQuaternions(restQuat, targetQuat);

            // Apply smoothing using SLERP
            if (this.options.smoothingFactor > 0 && this.prevRotations[boneName]) {
                bone.quaternion.slerp(finalQuat, this.options.lerpSpeed);
            } else {
                bone.quaternion.copy(finalQuat);
            }

            // Store for next frame smoothing
            this.prevRotations[boneName] = bone.quaternion.clone();
        }

        // Update bone matrices
        this.skeleton.update();

        this.stats.framesProcessed++;
        this.stats.lastUpdateTime = performance.now() - startTime;

        if (this.options.debug && this.stats.framesProcessed % 60 === 0) {
            console.log(`[SkeletalAnimator] Update took ${this.stats.lastUpdateTime.toFixed(2)}ms`);
        }
    }

    /**
     * Find bone by name with fuzzy matching
     */
    _findBone(name) {
        // Try direct lookup
        if (this.boneMap.has(name)) {
            return this.boneMap.get(name);
        }

        // Try normalized lookup
        const normalized = this._normalizeBoneName(name);
        if (this.boneMap.has(normalized)) {
            return this.boneMap.get(normalized);
        }

        // Try common variations
        const variations = [
            name.replace(/_/g, ''),           // left_upper_arm -> leftupperarm
            name.replace(/_/g, ' '),          // left_upper_arm -> left upper arm
            name.split('_').map(s =>          // left_upper_arm -> LeftUpperArm
                s.charAt(0).toUpperCase() + s.slice(1)
            ).join(''),
        ];

        for (const variant of variations) {
            if (this.boneMap.has(variant)) {
                return this.boneMap.get(variant);
            }
            if (this.boneMap.has(variant.toLowerCase())) {
                return this.boneMap.get(variant.toLowerCase());
            }
        }

        return null;
    }

    /**
     * Reset all bones to rest pose
     */
    reset() {
        for (const bone of this.skeleton.bones) {
            if (this.restPose[bone.name]) {
                bone.quaternion.copy(this.restPose[bone.name]);
            }
        }
        this.skeleton.update();
        this.prevRotations = {};
        console.log('[SkeletalAnimator] Reset to rest pose');
    }

    /**
     * Set smoothing factor (0 = instant, 1 = no change)
     */
    setSmoothing(factor) {
        this.options.smoothingFactor = Math.max(0, Math.min(1, factor));
        this.options.lerpSpeed = 1 - this.options.smoothingFactor;
    }

    /**
     * Get animation statistics
     */
    getStats() {
        return {
            ...this.stats,
            bonesTracked: this.boneMap.size,
            smoothingFactor: this.options.smoothingFactor
        };
    }

    /**
     * Log bone hierarchy for debugging
     */
    logBoneHierarchy() {
        const logBone = (bone, indent = 0) => {
            console.log(' '.repeat(indent) + bone.name);
            for (const child of bone.children) {
                if (child.isBone) {
                    logBone(child, indent + 2);
                }
            }
        };

        console.log('[SkeletalAnimator] Bone Hierarchy:');
        for (const bone of this.skeleton.bones) {
            if (!bone.parent?.isBone) {
                logBone(bone);
            }
        }
    }
}
