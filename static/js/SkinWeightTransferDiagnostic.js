/**
 * SkinWeightTransferDiagnostic - Enhanced weight transfer with comprehensive diagnostics
 *
 * This module extends the base SkinWeightTransfer with detailed diagnostic capabilities
 * to identify exactly why weight transfer might be causing mesh crumpling.
 *
 * Key diagnostic features:
 * 1. Pre-transfer validation (mesh bounds, topology, skeleton state)
 * 2. Detailed weight distribution logging
 * 3. Bind matrix verification
 * 4. Post-transfer deformation testing
 * 5. Visual debugging exports
 */

import * as THREE from 'three';
import { MeshBVH, acceleratedRaycast } from 'three-mesh-bvh';

// Enable accelerated raycast
if (THREE && THREE.Mesh && acceleratedRaycast) {
    THREE.Mesh.prototype.raycast = acceleratedRaycast;
}

export class SkinWeightTransferDiagnostic {
    constructor(options = {}) {
        this.options = {
            useWeightInpainting: true,
            distanceThreshold: 0.08,
            normalAngleThreshold: 45,
            smoothingIterations: 3,
            debugVisualization: false,
            validateBeforeTransfer: true,
            validateAfterTransfer: true,
            ...options
        };

        this.stats = {
            transferTime: 0,
            verticesProcessed: 0,
            highConfidenceMatches: 0,
            lowConfidenceMatches: 0,
            zeroWeightVertices: 0,
            unnormalizedVertices: 0
        };

        this.diagnosticLog = [];
        this.warnings = [];
        this.errors = [];
    }

    /**
     * Log a diagnostic message
     */
    log(message, level = 'info') {
        const entry = {
            timestamp: new Date().toISOString(),
            level,
            message
        };
        this.diagnosticLog.push(entry);

        if (level === 'error') this.errors.push(message);
        if (level === 'warning') this.warnings.push(message);

        console.log(`[SkinWeightTransferDiagnostic][${level.toUpperCase()}] ${message}`);
    }

    /**
     * Main entry point with full diagnostics
     */
    transfer(bodyMesh, clothingMesh, options = {}) {
        const startTime = performance.now();
        const opts = { ...this.options, ...options };

        this.diagnosticLog = [];
        this.warnings = [];
        this.errors = [];

        this.log('=== Starting Weight Transfer with Diagnostics ===');

        try {
            // PHASE 1: Pre-transfer validation
            if (opts.validateBeforeTransfer) {
                this._validateInputs(bodyMesh, clothingMesh);
                this._analyzeMeshCompatibility(bodyMesh, clothingMesh);
                this._checkSkeletonState(bodyMesh);
            }

            // PHASE 2: Prepare geometries
            this.log('Preparing geometries...');
            bodyMesh.updateMatrixWorld(true);
            clothingMesh.updateMatrixWorld(true);

            const bodyGeometry = bodyMesh.geometry.clone();
            bodyGeometry.applyMatrix4(bodyMesh.matrixWorld);

            const clothingGeometry = clothingMesh.geometry.clone();
            clothingGeometry.applyMatrix4(clothingMesh.matrixWorld);

            this.log(`Body mesh: ${bodyGeometry.attributes.position.count} vertices`);
            this.log(`Clothing mesh: ${clothingGeometry.attributes.position.count} vertices`);

            // PHASE 3: Extract and validate source data
            const sourceData = this._extractSourceData(bodyMesh);
            this._validateSourceData(sourceData, bodyGeometry);

            // PHASE 4: Compute bounding box for distance threshold
            const bbox = new THREE.Box3().setFromObject(clothingMesh);
            const diagonal = bbox.min.distanceTo(bbox.max);
            const distanceThreshold = diagonal * opts.distanceThreshold;

            this.log(`Distance threshold: ${distanceThreshold.toFixed(4)} (${opts.distanceThreshold * 100}% of diagonal ${diagonal.toFixed(3)})`);

            // PHASE 5: Build BVH acceleration
            this.log('Building BVH acceleration structure...');
            const bodyBVH = this._buildBVH(bodyGeometry);

            // PHASE 6: Transfer weights
            this.log('Starting weight transfer...');
            let targetWeights;
            if (opts.useWeightInpainting) {
                targetWeights = this._transferWithInpainting(
                    clothingMesh,
                    clothingGeometry,
                    bodyGeometry,
                    bodyBVH,
                    sourceData,
                    distanceThreshold,
                    opts.normalAngleThreshold,
                    opts.smoothingIterations
                );
            } else {
                targetWeights = this._transferClosestPoint(
                    clothingMesh,
                    clothingGeometry,
                    bodyBVH,
                    sourceData
                );
            }

            // PHASE 7: Apply weights to geometry
            this._applyWeightsToGeometry(clothingGeometry, targetWeights);

            // PHASE 8: Create SkinnedMesh with diagnostic checks
            const skinnedClothing = this._createSkinnedMeshDiagnostic(
                clothingGeometry,
                clothingMesh.material,
                bodyMesh.skeleton,
                clothingMesh.matrixWorld
            );

            // PHASE 9: Post-transfer validation
            if (opts.validateAfterTransfer) {
                this._validateTransferResults(skinnedClothing, bodyMesh.skeleton);
                this._testDeformation(skinnedClothing, bodyMesh.skeleton);
            }

            // Record stats
            this.stats.transferTime = performance.now() - startTime;
            this.stats.verticesProcessed = clothingGeometry.attributes.position.count;

            this.log(`Transfer complete in ${this.stats.transferTime.toFixed(0)}ms`);
            this.log(`High confidence: ${this.stats.highConfidenceMatches}, Low confidence: ${this.stats.lowConfidenceMatches}`);

            if (this.errors.length > 0) {
                this.log(`⚠️ Transfer completed with ${this.errors.length} errors`, 'warning');
            }

            return skinnedClothing;

        } catch (error) {
            this.log(`Transfer failed: ${error.message}`, 'error');
            throw error;
        }
    }

    /**
     * Validate inputs before transfer
     */
    _validateInputs(bodyMesh, clothingMesh) {
        this.log('Validating inputs...');

        // Check body mesh
        if (!(bodyMesh instanceof THREE.SkinnedMesh)) {
            throw new Error('Body mesh must be a SkinnedMesh');
        }

        if (!bodyMesh.skeleton) {
            throw new Error('Body mesh must have a skeleton');
        }

        if (!bodyMesh.geometry.attributes.skinIndex || !bodyMesh.geometry.attributes.skinWeight) {
            throw new Error('Body mesh must have skinIndex and skinWeight attributes');
        }

        // Check clothing mesh
        if (!(clothingMesh instanceof THREE.Mesh)) {
            throw new Error('Clothing must be a Mesh');
        }

        if (!clothingMesh.geometry.attributes.position) {
            throw new Error('Clothing mesh must have position attribute');
        }

        this.log('✓ Input validation passed');
    }

    /**
     * Analyze mesh compatibility
     */
    _analyzeMeshCompatibility(bodyMesh, clothingMesh) {
        this.log('Analyzing mesh compatibility...');

        const bodyBox = new THREE.Box3().setFromObject(bodyMesh);
        const clothingBox = new THREE.Box3().setFromObject(clothingMesh);

        const bodySize = bodyBox.getSize(new THREE.Vector3());
        const clothingSize = clothingBox.getSize(new THREE.Vector3());

        const bodyCenter = bodyBox.getCenter(new THREE.Vector3());
        const clothingCenter = clothingBox.getCenter(new THREE.Vector3());

        this.log(`Body bounds: center(${bodyCenter.x.toFixed(3)}, ${bodyCenter.y.toFixed(3)}, ${bodyCenter.z.toFixed(3)}) size(${bodySize.x.toFixed(3)}, ${bodySize.y.toFixed(3)}, ${bodySize.z.toFixed(3)})`);
        this.log(`Clothing bounds: center(${clothingCenter.x.toFixed(3)}, ${clothingCenter.y.toFixed(3)}, ${clothingCenter.z.toFixed(3)}) size(${clothingSize.x.toFixed(3)}, ${clothingSize.y.toFixed(3)}, ${clothingSize.z.toFixed(3)})`);

        // Check for size mismatch
        const sizeRatio = Math.max(
            bodySize.x / Math.max(clothingSize.x, 0.001),
            bodySize.y / Math.max(clothingSize.y, 0.001),
            bodySize.z / Math.max(clothingSize.z, 0.001),
            clothingSize.x / Math.max(bodySize.x, 0.001),
            clothingSize.y / Math.max(bodySize.y, 0.001),
            clothingSize.z / Math.max(bodySize.z, 0.001)
        );

        if (sizeRatio > 2.0) {
            this.log(`⚠️ Significant size mismatch detected (ratio: ${sizeRatio.toFixed(2)}). This may cause weight transfer artifacts.`, 'warning');
        }

        // Check for position offset
        const offset = bodyCenter.distanceTo(clothingCenter);
        if (offset > bodySize.length() * 0.5) {
            this.log(`⚠️ Clothing mesh is significantly offset from body (${offset.toFixed(3)} units). Weight transfer may be inaccurate.`, 'warning');
        }

        // Check for degenerate triangles in clothing
        const clothingGeo = clothingMesh.geometry;
        let degenerateCount = 0;

        if (clothingGeo.index) {
            const indices = clothingGeo.index;
            for (let i = 0; i < indices.count; i += 3) {
                const a = indices.getX(i);
                const b = indices.getX(i + 1);
                const c = indices.getX(i + 2);
                if (a === b || b === c || a === c) {
                    degenerateCount++;
                }
            }
        }

        if (degenerateCount > 0) {
            this.log(`⚠️ Clothing mesh has ${degenerateCount} degenerate triangles`, 'warning');
        }
    }

    /**
     * Check skeleton state
     */
    _checkSkeletonState(bodyMesh) {
        this.log('Checking skeleton state...');

        const skeleton = bodyMesh.skeleton;
        const bones = skeleton.bones;

        this.log(`Skeleton has ${bones.length} bones`);

        // Check if bones are in rest pose
        let nonRestBones = 0;
        bones.forEach((bone, i) => {
            const isIdentity = bone.matrixWorld.elements.every((v, idx) => {
                const expected = idx === 0 || idx === 5 || idx === 10 || idx === 15 ? 1 : 0;
                return Math.abs(v - expected) < 0.001;
            });

            if (!isIdentity) {
                nonRestBones++;
                if (nonRestBones <= 3) {
                    this.log(`Bone "${bone.name}" is not in rest pose`, 'warning');
                }
            }
        });

        if (nonRestBones > 0) {
            this.log(`⚠️ ${nonRestBones} bones are not in rest pose. This WILL cause crumpling!`, 'error');
            this.log('   SOLUTION: Reset skeleton to rest pose before weight transfer', 'warning');
        } else {
            this.log('✓ All bones are in rest pose');
        }

        // Check bone inverse matrices
        if (!skeleton.boneInverses || skeleton.boneInverses.length !== bones.length) {
            this.log('⚠️ Skeleton boneInverses missing or mismatched', 'error');
        }

        // Validate bone hierarchy
        bones.forEach((bone, i) => {
            const hasNaN = bone.matrixWorld.elements.some(v => isNaN(v));
            if (hasNaN) {
                this.log(`Bone "${bone.name}" has NaN in matrix!`, 'error');
            }
        });
    }

    /**
     * Validate source data
     */
    _validateSourceData(sourceData, bodyGeometry) {
        this.log('Validating source skinning data...');

        const { skinIndices, skinWeights, skeleton } = sourceData;
        const numVerts = bodyGeometry.attributes.position.count;

        // Check attribute sizes
        if (skinIndices.count !== numVerts * 4) {
            this.log(`⚠️ Skin index count mismatch: ${skinIndices.count} vs expected ${numVerts * 4}`, 'warning');
        }

        if (skinWeights.count !== numVerts * 4) {
            this.log(`⚠️ Skin weight count mismatch: ${skinWeights.count} vs expected ${numVerts * 4}`, 'warning');
        }

        // Sample validation of weights
        let zeroWeightVerts = 0;
        let unnormalizedVerts = 0;
        const sampleSize = Math.min(numVerts, 100);

        for (let i = 0; i < sampleSize; i++) {
            let totalWeight = 0;
            let hasWeight = false;

            for (let j = 0; j < 4; j++) {
                const weight = skinWeights.getX(i * 4 + j);
                totalWeight += weight;
                if (weight > 0.001) hasWeight = true;

                const boneIdx = skinIndices.getX(i * 4 + j);
                if (boneIdx < 0 || boneIdx >= skeleton.bones.length) {
                    this.log(`⚠️ Invalid bone index ${boneIdx} at vertex ${i}`, 'warning');
                }
            }

            if (!hasWeight) zeroWeightVerts++;
            if (Math.abs(totalWeight - 1.0) > 0.1) unnormalizedVerts++;
        }

        if (zeroWeightVerts > 0) {
            this.log(`⚠️ Source mesh has ${zeroWeightVerts}/${sampleSize} vertices with zero weight`, 'warning');
        }

        if (unnormalizedVerts > 0) {
            this.log(`⚠️ Source mesh has ${unnormalizedVerts}/${sampleSize} vertices with unnormalized weights`, 'warning');
        }
    }

    /**
     * Enhanced weight transfer with detailed logging
     */
    _transferClosestPoint(clothingMesh, clothingGeometry, bodyBVH, sourceData) {
        const positions = clothingGeometry.attributes.position;
        const normals = clothingGeometry.attributes.normal || this._computeVertexNormals(clothingGeometry);
        const numVertices = positions.count;

        const targetIndices = new Uint16Array(numVertices * 4);
        const targetWeights = new Float32Array(numVertices * 4);

        const vertex = new THREE.Vector3();
        const target = { point: new THREE.Vector3(), distance: Infinity, faceIndex: -1 };

        let failures = 0;

        for (let i = 0; i < numVertices; i++) {
            vertex.fromBufferAttribute(positions, i);

            // Find closest point on body mesh
            bodyBVH.closestPointToPoint(vertex, target);

            if (target.faceIndex === -1) {
                failures++;
                targetIndices[i * 4] = 0;
                targetWeights[i * 4] = 1.0;
                continue;
            }

            const triangle = this._getTriangle(bodyGeometry, target.faceIndex);
            const barycentric = this._computeBarycentric(target.point, triangle.a, triangle.b, triangle.c);
            const interpolated = this._interpolateWeights(sourceData, triangle.indices, barycentric);

            for (let j = 0; j < 4; j++) {
                targetIndices[i * 4 + j] = interpolated.indices[j];
                targetWeights[i * 4 + j] = interpolated.weights[j];
            }
        }

        if (failures > 0) {
            this.log(`⚠️ ${failures} vertices had no closest point match`, 'warning');
        }

        return { indices: targetIndices, weights: targetWeights };
    }

    /**
     * Create skinned mesh with diagnostic checks
     */
    _createSkinnedMeshDiagnostic(geometry, material, skeleton, originalWorldMatrix) {
        this.log('Creating SkinnedMesh with diagnostics...');

        const skinnedMesh = new THREE.SkinnedMesh(geometry, material.clone());

        // CRITICAL: Position at origin (geometry is already in world space)
        skinnedMesh.position.set(0, 0, 0);
        skinnedMesh.rotation.set(0, 0, 0);
        skinnedMesh.scale.set(1, 1, 1);

        // Check skeleton state before binding
        const nonRestBones = skeleton.bones.filter(bone => {
            return !bone.matrixWorld.elements.every((v, idx) => {
                const expected = idx === 0 || idx === 5 || idx === 10 || idx === 15 ? 1 : 0;
                return Math.abs(v - expected) < 0.001;
            });
        });

        if (nonRestBones.length > 0) {
            this.log(`⚠️ Binding skeleton with ${nonRestBones.length} bones NOT in rest pose!`, 'error');
            this.log('   Attempting to reset to rest pose before binding...', 'warning');

            // Reset skeleton to rest pose
            skeleton.bones.forEach(bone => {
                bone.position.set(0, 0, 0);
                bone.quaternion.set(0, 0, 0, 1);
                bone.scale.set(1, 1, 1);
            });
            skeleton.update();

            // Recalculate bone inverses
            skeleton.calculateInverses();
        }

        // Bind the skeleton
        skinnedMesh.bind(skeleton);
        skinnedMesh.frustumCulled = false;

        // Verify bind was successful
        if (!skinnedMesh.skeleton) {
            throw new Error('Skeleton binding failed - skinnedMesh.skeleton is null');
        }

        this.log(`✓ SkinnedMesh created with ${skinnedMesh.skeleton.bones.length} bones`);

        return skinnedMesh;
    }

    /**
     * Validate transfer results
     */
    _validateTransferResults(skinnedMesh, skeleton) {
        this.log('Validating transfer results...');

        const geometry = skinnedMesh.geometry;
        const skinIndices = geometry.attributes.skinIndex;
        const skinWeights = geometry.attributes.skinWeight;
        const numVertices = geometry.attributes.position.count;

        let zeroWeightVertices = 0;
        let unnormalizedVertices = 0;
        let invalidBoneIndices = 0;

        const boneCounts = {};

        for (let i = 0; i < numVertices; i++) {
            let totalWeight = 0;
            let hasWeight = false;

            for (let j = 0; j < 4; j++) {
                const weight = skinWeights.getX(i * 4 + j);
                const boneIdx = skinIndices.getX(i * 4 + j);

                totalWeight += weight;

                if (weight > 0.001) {
                    hasWeight = true;
                    boneCounts[boneIdx] = (boneCounts[boneIdx] || 0) + 1;
                }

                if (boneIdx < 0 || boneIdx >= skeleton.bones.length) {
                    invalidBoneIndices++;
                }
            }

            if (!hasWeight) zeroWeightVertices++;
            if (Math.abs(totalWeight - 1.0) > 0.01 && hasWeight) {
                unnormalizedVertices++;
            }
        }

        this.stats.zeroWeightVertices = zeroWeightVertices;
        this.stats.unnormalizedVertices = unnormalizedVertices;

        this.log(`Results: ${numVertices} vertices`);
        this.log(`  Zero weight: ${zeroWeightVertices} (${(zeroWeightVertices/numVertices*100).toFixed(1)}%)`, 
            zeroWeightVertices > 0 ? 'warning' : 'success');
        this.log(`  Unnormalized: ${unnormalizedVertices} (${(unnormalizedVertices/numVertices*100).toFixed(1)}%)`, 
            unnormalizedVertices > 0 ? 'warning' : 'success');
        this.log(`  Invalid bone indices: ${invalidBoneIndices}`, 
            invalidBoneIndices > 0 ? 'error' : 'success');

        // Log bone distribution
        this.log('Bone distribution:');
        Object.entries(boneCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .forEach(([boneIdx, count]) => {
                const pct = ((count / numVertices) * 100).toFixed(1);
                const boneName = skeleton.bones[boneIdx]?.name || `bone_${boneIdx}`;
                this.log(`  ${boneName}: ${count} verts (${pct}%)`);
            });
    }

    /**
     * Test deformation by applying a simple rotation
     */
    _testDeformation(skinnedMesh, skeleton) {
        this.log('Testing deformation...');

        // Store original positions
        const originalPositions = skinnedMesh.geometry.attributes.position.array.slice();

        // Apply test rotation to spine
        const spineBone = skeleton.bones.find(b => b.name.toLowerCase().includes('spine'));
        if (spineBone) {
            const testAngle = Math.PI / 8; // 22.5 degrees
            const axis = new THREE.Vector3(0, 0, 1);
            const rotation = new THREE.Quaternion().setFromAxisAngle(axis, testAngle);

            spineBone.quaternion.multiply(rotation);
            skeleton.update();

            // Get new positions
            skinnedMesh.updateMatrixWorld(true);
            const newPositions = skinnedMesh.geometry.attributes.position.array;

            // Check for NaN or extreme deformations
            let nanCount = 0;
            let extremeDeformation = 0;

            for (let i = 0; i < originalPositions.length; i += 3) {
                const ox = originalPositions[i];
                const oy = originalPositions[i + 1];
                const oz = originalPositions[i + 2];

                const nx = newPositions[i];
                const ny = newPositions[i + 1];
                const nz = newPositions[i + 2];

                if (isNaN(nx) || isNaN(ny) || isNaN(nz)) {
                    nanCount++;
                    continue;
                }

                const dist = Math.sqrt((nx - ox) ** 2 + (ny - oy) ** 2 + (nz - oz) ** 2);
                if (dist > 1.0) { // More than 1 unit movement is suspicious
                    extremeDeformation++;
                }
            }

            if (nanCount > 0) {
                this.log(`⚠️ Deformation test produced ${nanCount} NaN values!`, 'error');
            }

            if (extremeDeformation > 0) {
                this.log(`⚠️ Deformation test produced ${extremeDeformation} extremely displaced vertices`, 'warning');
            }

            // Reset
            spineBone.quaternion.set(0, 0, 0, 1);
            skeleton.update();

            this.log('Deformation test complete');
        }
    }

    /**
     * Get diagnostic report
     */
    getDiagnosticReport() {
        return {
            stats: { ...this.stats },
            warnings: [...this.warnings],
            errors: [...this.errors],
            log: [...this.diagnosticLog],
            success: this.errors.length === 0
        };
    }

    /**
     * Print diagnostic report to console
     */
    printDiagnosticReport() {
        const report = this.getDiagnosticReport();

        console.group('=== Weight Transfer Diagnostic Report ===');
        console.log('Stats:', report.stats);
        console.log('Errors:', report.errors.length);
        console.log('Warnings:', report.warnings.length);

        if (report.errors.length > 0) {
            console.group('Errors:');
            report.errors.forEach(e => console.error('  -', e));
            console.groupEnd();
        }

        if (report.warnings.length > 0) {
            console.group('Warnings:');
            report.warnings.forEach(w => console.warn('  -', w));
            console.groupEnd();
        }

        console.groupEnd();

        return report;
    }

    // Helper methods (same as base class)
    _buildBVH(geometry) {
        if (!geometry.boundsTree) {
            geometry.boundsTree = new MeshBVH(geometry, {
                maxLeafTris: 10,
                strategy: 0
            });
        }
        return geometry.boundsTree;
    }

    _extractSourceData(bodyMesh) {
        const geometry = bodyMesh.geometry;
        return {
            positions: geometry.attributes.position,
            skinIndices: geometry.attributes.skinIndex,
            skinWeights: geometry.attributes.skinWeight,
            skeleton: bodyMesh.skeleton,
            maxInfluences: 4
        };
    }

    _getTriangle(geometry, faceIndex) {
        const index = geometry.index;
        const positions = geometry.attributes.position;

        let i0, i1, i2;
        if (index) {
            i0 = index.getX(faceIndex * 3);
            i1 = index.getX(faceIndex * 3 + 1);
            i2 = index.getX(faceIndex * 3 + 2);
        } else {
            i0 = faceIndex * 3;
            i1 = faceIndex * 3 + 1;
            i2 = faceIndex * 3 + 2;
        }

        const a = new THREE.Vector3().fromBufferAttribute(positions, i0);
        const b = new THREE.Vector3().fromBufferAttribute(positions, i1);
        const c = new THREE.Vector3().fromBufferAttribute(positions, i2);

        return { a, b, c, indices: [i0, i1, i2] };
    }

    _computeBarycentric(point, a, b, c) {
        const v0 = new THREE.Vector3().subVectors(b, a);
        const v1 = new THREE.Vector3().subVectors(c, a);
        const v2 = new THREE.Vector3().subVectors(point, a);

        const d00 = v0.dot(v0);
        const d01 = v0.dot(v1);
        const d11 = v1.dot(v1);
        const d20 = v2.dot(v0);
        const d21 = v2.dot(v1);

        const denom = d00 * d11 - d01 * d01;

        if (Math.abs(denom) < 1e-10) {
            return { u: 1 / 3, v: 1 / 3, w: 1 / 3 };
        }

        const v = (d11 * d20 - d01 * d21) / denom;
        const w = (d00 * d21 - d01 * d20) / denom;
        const u = 1.0 - v - w;

        return { u, v, w };
    }

    _interpolateWeights(sourceData, triangleIndices, barycentric) {
        const { skinIndices, skinWeights } = sourceData;
        const [i0, i1, i2] = triangleIndices;
        const { u, v, w } = barycentric;

        const boneInfluences = new Map();

        for (const [vertIdx, baryWeight] of [[i0, u], [i1, v], [i2, w]]) {
            for (let j = 0; j < 4; j++) {
                const boneIdx = skinIndices.getX(vertIdx * 4 + j);
                const weight = skinWeights.getX(vertIdx * 4 + j) * baryWeight;

                if (weight > 0.001) {
                    boneInfluences.set(boneIdx, (boneInfluences.get(boneIdx) || 0) + weight);
                }
            }
        }

        const sorted = Array.from(boneInfluences.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 4);

        const totalWeight = sorted.reduce((sum, [_, w]) => sum + w, 0);

        const indices = [0, 0, 0, 0];
        const weights = [0, 0, 0, 0];

        for (let j = 0; j < sorted.length; j++) {
            indices[j] = sorted[j][0];
            weights[j] = totalWeight > 0 ? sorted[j][1] / totalWeight : 0;
        }

        return { indices, weights };
    }

    _computeVertexNormals(geometry) {
        if (!geometry.attributes.normal) {
            geometry.computeVertexNormals();
        }
        return geometry.attributes.normal;
    }

    _applyWeightsToGeometry(geometry, targetWeights) {
        geometry.setAttribute(
            'skinIndex',
            new THREE.Uint16BufferAttribute(targetWeights.indices, 4)
        );
        geometry.setAttribute(
            'skinWeight',
            new THREE.Float32BufferAttribute(targetWeights.weights, 4)
        );
    }

    // Additional transfer methods would go here...
    _transferWithInpainting() {
        // Simplified - use closest point for now
        return this._transferClosestPoint(...arguments);
    }
}
