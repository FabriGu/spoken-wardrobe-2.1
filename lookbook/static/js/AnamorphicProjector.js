/**
 * AnamorphicProjector.js
 *
 * The core algorithm for anamorphic compositions.
 * Positions 3D objects so they project to specific 2D screen positions
 * from ONE specific camera viewpoint.
 *
 * When the camera moves, the illusion breaks and objects scatter into 3D space.
 * From the "perfect" viewpoint, they align into a coherent 2D collage.
 */

import * as THREE from 'three';

export class AnamorphicProjector {
    constructor(camera) {
        this.camera = camera;

        // Store the "perfect" anamorphic viewpoint
        this.anamorphicPosition = camera.position.clone();
        this.anamorphicTarget = new THREE.Vector3(0, 0, 0);

        // Raycaster for projection calculations
        this.raycaster = new THREE.Raycaster();
    }

    /**
     * Set the camera position that defines the "perfect" anamorphic view.
     * @param {THREE.Vector3} position - Camera position
     * @param {THREE.Vector3} target - Camera look-at target
     */
    setAnamorphicView(position, target = new THREE.Vector3(0, 0, 0)) {
        this.anamorphicPosition = position.clone();
        this.anamorphicTarget = target.clone();
    }

    /**
     * Project a 2D screen position to a 3D world position at a given depth.
     *
     * This is the key insight: we cast a ray from the camera through the
     * target screen position, then place the object along that ray at
     * the specified depth. From the camera's viewpoint, the object will
     * appear at the target 2D position regardless of its actual depth.
     *
     * @param {object} target2D - { x: 0-1, y: 0-1 } normalized screen position
     * @param {number} depth - Distance from camera along the viewing ray
     * @returns {THREE.Vector3} - World position for the object
     */
    projectToDepth(target2D, depth) {
        // Convert normalized coords (0-1) to NDC (-1 to 1)
        // Note: Y is flipped because screen Y goes down, NDC Y goes up
        const ndcX = (target2D.x * 2) - 1;
        const ndcY = -((target2D.y * 2) - 1);

        // Create ray from camera through this screen point
        this.raycaster.setFromCamera(
            new THREE.Vector2(ndcX, ndcY),
            this.camera
        );

        // Get point along ray at specified depth
        const direction = this.raycaster.ray.direction.clone().normalize();
        const position = this.camera.position.clone()
            .add(direction.multiplyScalar(depth));

        return position;
    }

    /**
     * Position an element so its center appears at target2D from the camera view.
     * Randomly varies depth within the given range for visual variety.
     *
     * @param {THREE.Object3D} element - The 3D object to position
     * @param {object} target2D - { x: 0-1, y: 0-1 } normalized screen position
     * @param {object} depthRange - { min, max } depth range in world units
     * @param {number} targetScale - Desired apparent size (0-1 fraction of screen)
     * @returns {object} - { position, depth, scale } applied values
     */
    positionElement(element, target2D, depthRange = { min: 3, max: 15 }, targetScale = 0.2) {
        // Random depth within range for visual interest
        const depth = THREE.MathUtils.randFloat(depthRange.min, depthRange.max);

        // Calculate world position along viewing ray
        const worldPos = this.projectToDepth(target2D, depth);
        element.position.copy(worldPos);

        // Scale inversely with depth to maintain consistent apparent size
        // Objects further away need to be larger to appear the same size
        const scaleFactor = this.calculateScale(depth, targetScale);
        element.scale.setScalar(scaleFactor);

        // Store depth info for potential use (sorting, etc.)
        element.userData.anamorphicDepth = depth;
        element.userData.anamorphicTarget = { ...target2D };

        return { position: worldPos, depth, scale: scaleFactor };
    }

    /**
     * Calculate the scale needed for an object to appear at a target apparent size.
     *
     * Uses perspective math: apparent size = actual size / depth
     * So: actual size = apparent size * depth
     *
     * @param {number} depth - Distance from camera
     * @param {number} targetApparentSize - Desired fraction of view height (0-1)
     * @returns {number} - Scale factor to apply to the object
     */
    calculateScale(depth, targetApparentSize) {
        // Calculate visible height at this depth using FOV
        const fov = THREE.MathUtils.degToRad(this.camera.fov);
        const visibleHeight = 2 * Math.tan(fov / 2) * depth;

        // Target size in world units
        return targetApparentSize * visibleHeight;
    }

    /**
     * Apply rotation to an element while maintaining its anamorphic position.
     * Rotations are applied around the camera-facing axis.
     *
     * @param {THREE.Object3D} element - The 3D object to rotate
     * @param {number} angleDegrees - Rotation angle in degrees
     */
    applyRotation(element, angleDegrees) {
        // Calculate direction from camera to element
        const toElement = element.position.clone().sub(this.camera.position).normalize();

        // Create rotation around this axis (billboard-style rotation)
        const rotationAxis = toElement;
        const angle = THREE.MathUtils.degToRad(angleDegrees);

        // Apply rotation
        element.rotateOnWorldAxis(rotationAxis, angle);
    }

    /**
     * Make an element face the camera (billboard mode).
     * Useful for image planes that should always face the viewer.
     *
     * @param {THREE.Object3D} element - The 3D object to billboard
     */
    makeBillboard(element) {
        element.lookAt(this.camera.position);
    }

    /**
     * Generate chaotic positions for multiple elements.
     * Creates a visually interesting layout while avoiding overlap.
     *
     * @param {number} count - Number of positions to generate
     * @param {object} options - Layout options
     * @returns {Array} - Array of { target2D, depthRange, rotation } configs
     */
    generateChaoticLayout(count, options = {}) {
        const {
            avoidCenter = 0.2,      // Keep center area clear for main element
            marginX = 0.1,          // Edge margin
            marginY = 0.1,
            depthMin = 4,
            depthMax = 20,
            rotationAngles = [0, 45, 90, 135, 180, -45, -90, -135]
        } = options;

        const positions = [];
        const usedRegions = [];

        for (let i = 0; i < count; i++) {
            let attempts = 0;
            let pos;

            // Try to find non-overlapping position
            do {
                pos = {
                    x: marginX + Math.random() * (1 - 2 * marginX),
                    y: marginY + Math.random() * (1 - 2 * marginY)
                };
                attempts++;
            } while (
                attempts < 50 &&
                (this._isInCenter(pos, avoidCenter) || this._overlapsExisting(pos, usedRegions))
            );

            usedRegions.push(pos);

            // Vary depth based on distance from center (further = deeper)
            const distFromCenter = Math.sqrt(
                Math.pow(pos.x - 0.5, 2) + Math.pow(pos.y - 0.5, 2)
            );
            const depthBias = distFromCenter * 0.5; // Outer elements pushed back
            const depth = {
                min: depthMin + depthBias * 5,
                max: depthMax + depthBias * 5
            };

            // Random rotation from allowed angles
            const rotation = rotationAngles[Math.floor(Math.random() * rotationAngles.length)];

            positions.push({
                target2D: pos,
                depthRange: depth,
                rotation
            });
        }

        return positions;
    }

    /**
     * Check if position is in the center exclusion zone.
     */
    _isInCenter(pos, avoidRadius) {
        const dx = pos.x - 0.5;
        const dy = pos.y - 0.5;
        return Math.sqrt(dx * dx + dy * dy) < avoidRadius;
    }

    /**
     * Check if position overlaps with existing positions.
     */
    _overlapsExisting(pos, existing, threshold = 0.15) {
        for (const other of existing) {
            const dx = pos.x - other.x;
            const dy = pos.y - other.y;
            if (Math.sqrt(dx * dx + dy * dy) < threshold) {
                return true;
            }
        }
        return false;
    }

    /**
     * Get the "perfect" anamorphic camera position.
     */
    getAnamorphicPosition() {
        return this.anamorphicPosition.clone();
    }

    /**
     * Get the anamorphic look-at target.
     */
    getAnamorphicTarget() {
        return this.anamorphicTarget.clone();
    }
}
