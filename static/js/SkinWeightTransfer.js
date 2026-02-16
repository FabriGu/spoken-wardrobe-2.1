/**
 * SkinWeightTransfer - Transfer skinning weights from rigged body to clothing
 *
 * This module implements the "closest point" weight transfer algorithm with
 * optional Epic Games two-stage refinement for production-quality results.
 *
 * Algorithm:
 * 1. For each clothing vertex, find closest point on body mesh surface
 * 2. Calculate barycentric coordinates within the containing triangle
 * 3. Interpolate skin weights from triangle vertices
 * 4. Apply weights to clothing geometry
 * 5. Convert to SkinnedMesh sharing body's skeleton
 *
 * Performance: O(n * log(m)) where n = clothing vertices, m = body triangles
 * Expected: ~300-500ms for 5K-8K vertex meshes with BVH acceleration
 *
 * References:
 * - Autodesk Maya "Copy Skin Weights" (closest point method)
 * - Epic Games SIGGRAPH Asia 2023: "Robust Skin Weights Transfer via Weight Inpainting"
 */

import * as THREE from 'three';
import { MeshBVH, acceleratedRaycast } from 'three-mesh-bvh';

// Enable accelerated raycast for all meshes (with defensive check)
if (THREE && THREE.Mesh && acceleratedRaycast) {
    THREE.Mesh.prototype.raycast = acceleratedRaycast;
    console.log('[SkinWeightTransfer] BVH accelerated raycast enabled');
} else {
    console.warn('[SkinWeightTransfer] Could not enable BVH acceleration - THREE.Mesh not available');
}

export class SkinWeightTransfer {
    constructor(options = {}) {
        this.options = {
            useWeightInpainting: true,      // Enable Epic Games two-stage method
            distanceThreshold: 0.08,        // As fraction of bounding box diagonal
            normalAngleThreshold: 45,       // Degrees
            smoothingIterations: 3,         // Iterations for weight inpainting
            debugVisualization: false,      // Log debug info
            ...options
        };

        this.stats = {
            transferTime: 0,
            verticesProcessed: 0,
            highConfidenceMatches: 0,
            lowConfidenceMatches: 0
        };
    }

    /**
     * Main entry point - transfer weights from rigged body to clothing
     *
     * @param {THREE.SkinnedMesh} bodyMesh - Source mesh with skinning data
     * @param {THREE.Mesh} clothingMesh - Target mesh to rig (converted to SkinnedMesh)
     * @param {Object} options - Override default options
     * @returns {THREE.SkinnedMesh} - Rigged clothing mesh sharing body's skeleton
     */
    transfer(bodyMesh, clothingMesh, options = {}) {
        const startTime = performance.now();
        const opts = { ...this.options, ...options };

        console.log('[SkinWeightTransfer] Starting weight transfer...');

        // 1. Validate inputs
        this._validateInputs(bodyMesh, clothingMesh);

        // 2. Ensure body mesh geometry is in world space for accurate matching
        bodyMesh.updateMatrixWorld(true);
        clothingMesh.updateMatrixWorld(true);

        // 3. Build BVH acceleration structure for fast closest point queries
        const bodyGeometry = bodyMesh.geometry.clone();
        bodyGeometry.applyMatrix4(bodyMesh.matrixWorld);
        const bodyBVH = this._buildBVH(bodyGeometry);

        // 4. Extract source skinning data
        const sourceData = this._extractSourceData(bodyMesh);

        // 5. Compute bounding box diagonal for distance threshold
        const bbox = new THREE.Box3().setFromObject(clothingMesh);
        const diagonal = bbox.min.distanceTo(bbox.max);
        const distanceThreshold = diagonal * opts.distanceThreshold;

        console.log(`[SkinWeightTransfer] Distance threshold: ${distanceThreshold.toFixed(4)} (${opts.distanceThreshold * 100}% of ${diagonal.toFixed(3)})`);

        // 6. Transfer weights
        let targetWeights;
        if (opts.useWeightInpainting) {
            targetWeights = this._transferWithInpainting(
                clothingMesh,
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
                bodyGeometry,
                bodyBVH,
                sourceData
            );
        }

        // 7. Apply weights to clothing geometry
        this._applyWeightsToGeometry(clothingMesh.geometry, targetWeights);

        // 8. Convert to SkinnedMesh and bind to body's skeleton
        // IMPORTANT: Do NOT clone skeleton - we need clothing to share the same
        // skeleton instance that SkeletalAnimator will update
        const skinnedClothing = this._createSkinnedMesh(
            clothingMesh,
            bodyMesh.skeleton  // Share skeleton reference (not clone!)
        );

        // 9. Record performance stats
        this.stats.transferTime = performance.now() - startTime;
        this.stats.verticesProcessed = clothingMesh.geometry.attributes.position.count;

        console.log(`[SkinWeightTransfer] Transfer complete in ${this.stats.transferTime.toFixed(0)}ms`);
        console.log(`[SkinWeightTransfer] Vertices: ${this.stats.verticesProcessed}, High confidence: ${this.stats.highConfidenceMatches}, Low confidence: ${this.stats.lowConfidenceMatches}`);

        return skinnedClothing;
    }

    /**
     * Basic closest point weight transfer (standard industry method)
     */
    _transferClosestPoint(clothingMesh, bodyGeometry, bodyBVH, sourceData) {
        const clothingGeometry = clothingMesh.geometry;
        const positions = clothingGeometry.attributes.position;
        const normals = clothingGeometry.attributes.normal ||
            this._computeVertexNormals(clothingGeometry);

        const numVertices = positions.count;

        // Initialize target weight arrays
        const targetIndices = new Uint16Array(numVertices * 4);
        const targetWeights = new Float32Array(numVertices * 4);

        // Temporary vectors
        const vertex = new THREE.Vector3();
        const vertexWorld = new THREE.Vector3();
        const target = { point: new THREE.Vector3(), distance: Infinity, faceIndex: -1 };

        // Process each clothing vertex
        for (let i = 0; i < numVertices; i++) {
            // Get vertex position in world space
            vertex.fromBufferAttribute(positions, i);
            vertexWorld.copy(vertex).applyMatrix4(clothingMesh.matrixWorld);

            // Find closest point on body mesh
            bodyBVH.closestPointToPoint(vertexWorld, target);

            if (target.faceIndex === -1) {
                console.warn(`[SkinWeightTransfer] No closest point found for vertex ${i}`);
                // Default to identity weights on first bone
                targetIndices[i * 4] = 0;
                targetWeights[i * 4] = 1.0;
                continue;
            }

            // Get the triangle containing the closest point
            const triangle = this._getTriangle(bodyGeometry, target.faceIndex);

            // Calculate barycentric coordinates
            const barycentric = this._computeBarycentric(
                target.point,
                triangle.a,
                triangle.b,
                triangle.c
            );

            // Interpolate skin weights
            const interpolated = this._interpolateWeights(
                sourceData,
                triangle.indices,
                barycentric
            );

            // Store in target arrays (4 bones per vertex)
            for (let j = 0; j < 4; j++) {
                targetIndices[i * 4 + j] = interpolated.indices[j];
                targetWeights[i * 4 + j] = interpolated.weights[j];
            }
        }

        this.stats.highConfidenceMatches = numVertices;
        return { indices: targetIndices, weights: targetWeights };
    }

    /**
     * Advanced two-stage method with weight inpainting (Epic Games)
     */
    _transferWithInpainting(
        clothingMesh,
        bodyGeometry,
        bodyBVH,
        sourceData,
        distanceThreshold,
        normalThreshold,
        smoothingIterations
    ) {
        const clothingGeometry = clothingMesh.geometry;
        const positions = clothingGeometry.attributes.position;
        const normals = clothingGeometry.attributes.normal ||
            this._computeVertexNormals(clothingGeometry);
        const numVertices = positions.count;

        // Stage 1: Identify high-confidence matches
        const matchingSets = this._identifyMatchingSets(
            clothingMesh,
            bodyGeometry,
            bodyBVH,
            sourceData,
            distanceThreshold,
            normalThreshold
        );

        this.stats.highConfidenceMatches = matchingSets.matched.size;
        this.stats.lowConfidenceMatches = matchingSets.unmatched.size;

        // Initialize with closest-point weights for all vertices
        const baseWeights = this._transferClosestPoint(
            clothingMesh,
            bodyGeometry,
            bodyBVH,
            sourceData
        );

        // Stage 2: Smooth weights for low-confidence vertices
        if (matchingSets.unmatched.size > 0) {
            const adjacency = this._buildVertexAdjacency(clothingGeometry);
            this._smoothUnmatchedWeights(
                baseWeights,
                matchingSets,
                adjacency,
                smoothingIterations
            );
        }

        return baseWeights;
    }

    /**
     * Identify vertices with reliable vs unreliable matches
     */
    _identifyMatchingSets(
        clothingMesh,
        bodyGeometry,
        bodyBVH,
        sourceData,
        distanceThreshold,
        normalThreshold
    ) {
        const positions = clothingMesh.geometry.attributes.position;
        const normals = clothingMesh.geometry.attributes.normal;
        const numVertices = positions.count;

        const matched = new Set();
        const unmatched = new Set();
        const matchData = new Map();  // Store closest point data for matched vertices

        const vertex = new THREE.Vector3();
        const normal = new THREE.Vector3();
        const target = { point: new THREE.Vector3(), distance: Infinity, faceIndex: -1 };

        const normalThresholdCos = Math.cos(normalThreshold * Math.PI / 180);

        for (let i = 0; i < numVertices; i++) {
            vertex.fromBufferAttribute(positions, i);
            vertex.applyMatrix4(clothingMesh.matrixWorld);

            if (normals) {
                normal.fromBufferAttribute(normals, i);
                normal.transformDirection(clothingMesh.matrixWorld);
            }

            // Find closest point
            bodyBVH.closestPointToPoint(vertex, target);
            const distance = vertex.distanceTo(target.point);

            // Get surface normal at closest point
            let normalAlignment = 1.0;
            if (normals && target.faceIndex >= 0) {
                const bodyNormal = this._getTriangleNormal(bodyGeometry, target.faceIndex);
                normalAlignment = normal.dot(bodyNormal);
            }

            // Check confidence criteria
            const isHighConfidence =
                distance < distanceThreshold &&
                normalAlignment > normalThresholdCos;

            if (isHighConfidence) {
                matched.add(i);
                matchData.set(i, { point: target.point.clone(), faceIndex: target.faceIndex });
            } else {
                unmatched.add(i);
            }
        }

        console.log(`[SkinWeightTransfer] Matched: ${matched.size}, Unmatched: ${unmatched.size}`);
        return { matched, unmatched, matchData };
    }

    /**
     * Smooth weights for unmatched vertices using Laplacian diffusion
     */
    _smoothUnmatchedWeights(baseWeights, matchingSets, adjacency, iterations) {
        const { matched, unmatched } = matchingSets;
        const numVertices = baseWeights.weights.length / 4;

        // Create working copy
        const workingWeights = new Float32Array(baseWeights.weights);
        const workingIndices = new Uint16Array(baseWeights.indices);

        for (let iter = 0; iter < iterations; iter++) {
            for (const vertexIdx of unmatched) {
                const neighbors = adjacency[vertexIdx];
                if (!neighbors || neighbors.length === 0) continue;

                // Count bone influences from neighbors
                const boneWeights = new Map();

                for (const neighborIdx of neighbors) {
                    for (let j = 0; j < 4; j++) {
                        const boneIdx = workingIndices[neighborIdx * 4 + j];
                        const weight = workingWeights[neighborIdx * 4 + j];
                        if (weight > 0.001) {
                            boneWeights.set(boneIdx, (boneWeights.get(boneIdx) || 0) + weight);
                        }
                    }
                }

                // Sort by weight and take top 4
                const sorted = Array.from(boneWeights.entries())
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 4);

                // Normalize
                const totalWeight = sorted.reduce((sum, [_, w]) => sum + w, 0);

                for (let j = 0; j < 4; j++) {
                    if (j < sorted.length && totalWeight > 0) {
                        workingIndices[vertexIdx * 4 + j] = sorted[j][0];
                        workingWeights[vertexIdx * 4 + j] = sorted[j][1] / totalWeight;
                    } else {
                        workingIndices[vertexIdx * 4 + j] = 0;
                        workingWeights[vertexIdx * 4 + j] = 0;
                    }
                }
            }
        }

        // Copy back
        baseWeights.indices.set(workingIndices);
        baseWeights.weights.set(workingWeights);
    }

    /**
     * Build adjacency list for mesh topology
     */
    _buildVertexAdjacency(geometry) {
        const index = geometry.index;
        const numVertices = geometry.attributes.position.count;
        const adjacency = Array.from({ length: numVertices }, () => new Set());

        if (index) {
            for (let i = 0; i < index.count; i += 3) {
                const a = index.getX(i);
                const b = index.getX(i + 1);
                const c = index.getX(i + 2);

                adjacency[a].add(b); adjacency[a].add(c);
                adjacency[b].add(a); adjacency[b].add(c);
                adjacency[c].add(a); adjacency[c].add(b);
            }
        } else {
            const numFaces = numVertices / 3;
            for (let i = 0; i < numFaces; i++) {
                const a = i * 3;
                const b = i * 3 + 1;
                const c = i * 3 + 2;

                adjacency[a].add(b); adjacency[a].add(c);
                adjacency[b].add(a); adjacency[b].add(c);
                adjacency[c].add(a); adjacency[c].add(b);
            }
        }

        return adjacency.map(set => Array.from(set));
    }

    /**
     * Build BVH acceleration structure
     */
    _buildBVH(geometry) {
        if (!geometry.boundsTree) {
            geometry.boundsTree = new MeshBVH(geometry, {
                maxLeafTris: 10,
                strategy: 0  // SAH
            });
        }
        return geometry.boundsTree;
    }

    /**
     * Extract skinning data from source mesh
     */
    _extractSourceData(bodyMesh) {
        const geometry = bodyMesh.geometry;

        // Handle case where skinIndex/skinWeight use different attribute names
        let skinIndices = geometry.attributes.skinIndex;
        let skinWeights = geometry.attributes.skinWeight;

        if (!skinIndices || !skinWeights) {
            throw new Error('Body mesh must have skinIndex and skinWeight attributes');
        }

        return {
            positions: geometry.attributes.position,
            skinIndices: skinIndices,
            skinWeights: skinWeights,
            skeleton: bodyMesh.skeleton,
            maxInfluences: 4
        };
    }

    /**
     * Get triangle vertices and indices for a face
     */
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

    /**
     * Compute barycentric coordinates
     */
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

    /**
     * Interpolate skinning weights using barycentric coordinates
     */
    _interpolateWeights(sourceData, triangleIndices, barycentric) {
        const { skinIndices, skinWeights } = sourceData;
        const [i0, i1, i2] = triangleIndices;
        const { u, v, w } = barycentric;

        // Collect all bone influences from triangle vertices
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

        // Sort by weight and take top 4
        const sorted = Array.from(boneInfluences.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 4);

        // Normalize
        const totalWeight = sorted.reduce((sum, [_, w]) => sum + w, 0);

        const indices = [0, 0, 0, 0];
        const weights = [0, 0, 0, 0];

        for (let j = 0; j < sorted.length; j++) {
            indices[j] = sorted[j][0];
            weights[j] = totalWeight > 0 ? sorted[j][1] / totalWeight : 0;
        }

        return { indices, weights };
    }

    /**
     * Apply computed weights to geometry
     */
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

    /**
     * Convert regular mesh to SkinnedMesh and bind to skeleton
     */
    _createSkinnedMesh(clothingMesh, skeleton) {
        // Create SkinnedMesh with the rigged geometry
        const skinnedClothing = new THREE.SkinnedMesh(
            clothingMesh.geometry,
            clothingMesh.material
        );

        // Copy transform
        skinnedClothing.position.copy(clothingMesh.position);
        skinnedClothing.rotation.copy(clothingMesh.rotation);
        skinnedClothing.scale.copy(clothingMesh.scale);

        // Copy name and other properties
        skinnedClothing.name = clothingMesh.name || 'rigged_clothing';

        // IMPORTANT: Do NOT add skeleton.bones[0] as child - that would remove it
        // from the body mesh hierarchy! Instead, just bind the skeleton.
        // The skeleton bones remain in the body mesh scene graph, and the
        // clothing mesh will reference them via the skeleton binding.

        // BIND - this calculates inverse bind matrices from current bone transforms
        // The skeleton's boneInverses will be computed from each bone's matrixWorld
        skinnedClothing.bind(skeleton);

        // Enable frustum culling fix for skinned meshes
        skinnedClothing.frustumCulled = false;

        console.log(`[SkinWeightTransfer] Created SkinnedMesh with ${skeleton.bones.length} bones`);
        console.log(`[SkinWeightTransfer] Skeleton bone matrices valid:`,
            skeleton.bones.every(b => b.matrixWorld.elements.some(e => e !== 0)));

        return skinnedClothing;
    }

    /**
     * Get triangle normal
     */
    _getTriangleNormal(geometry, faceIndex) {
        const triangle = this._getTriangle(geometry, faceIndex);
        const normal = new THREE.Vector3();

        const edge1 = new THREE.Vector3().subVectors(triangle.b, triangle.a);
        const edge2 = new THREE.Vector3().subVectors(triangle.c, triangle.a);

        normal.crossVectors(edge1, edge2).normalize();
        return normal;
    }

    /**
     * Compute vertex normals if not present
     */
    _computeVertexNormals(geometry) {
        if (!geometry.attributes.normal) {
            geometry.computeVertexNormals();
        }
        return geometry.attributes.normal;
    }

    /**
     * Validate inputs
     */
    _validateInputs(bodyMesh, clothingMesh) {
        if (!(bodyMesh instanceof THREE.SkinnedMesh)) {
            throw new Error('Body mesh must be a SkinnedMesh with skeleton');
        }

        if (!bodyMesh.skeleton) {
            throw new Error('Body mesh must have a skeleton bound');
        }

        if (!(clothingMesh instanceof THREE.Mesh)) {
            throw new Error('Clothing must be a Mesh');
        }

        console.log(`[SkinWeightTransfer] Body: ${bodyMesh.geometry.attributes.position.count} vertices, ${bodyMesh.skeleton.bones.length} bones`);
        console.log(`[SkinWeightTransfer] Clothing: ${clothingMesh.geometry.attributes.position.count} vertices`);
    }

    /**
     * Get performance statistics
     */
    getStats() {
        return {
            ...this.stats,
            verticesPerSecond: Math.round(
                this.stats.verticesProcessed / (this.stats.transferTime / 1000)
            )
        };
    }

    /**
     * Create a debug material that visualizes skin weights by bone.
     * Each bone gets a unique color, and vertices show their dominant bone influence.
     *
     * @param {THREE.SkinnedMesh} skinnedMesh - The skinned mesh to visualize
     * @returns {THREE.MeshBasicMaterial} - Material with vertex colors showing weights
     */
    createWeightVisualizationMaterial(skinnedMesh) {
        const geometry = skinnedMesh.geometry;
        const skinIndices = geometry.attributes.skinIndex;
        const skinWeights = geometry.attributes.skinWeight;
        const numVertices = geometry.attributes.position.count;

        // Generate distinct colors for each bone
        const boneColors = [
            new THREE.Color(0xff0000), // Red - bone 0 (root/hips)
            new THREE.Color(0x00ff00), // Green - bone 1 (spine)
            new THREE.Color(0x0000ff), // Blue - bone 2
            new THREE.Color(0xffff00), // Yellow - bone 3
            new THREE.Color(0xff00ff), // Magenta - bone 4
            new THREE.Color(0x00ffff), // Cyan - bone 5
            new THREE.Color(0xff8000), // Orange - bone 6
            new THREE.Color(0x8000ff), // Purple - bone 7
            new THREE.Color(0x00ff80), // Teal - bone 8
            new THREE.Color(0xffffff), // White - fallback
        ];

        // Create vertex colors array
        const colors = new Float32Array(numVertices * 3);

        for (let i = 0; i < numVertices; i++) {
            // Find dominant bone (highest weight)
            let maxWeight = 0;
            let dominantBone = 0;

            for (let j = 0; j < 4; j++) {
                const weight = skinWeights.getX(i * 4 + j);
                if (weight > maxWeight) {
                    maxWeight = weight;
                    dominantBone = skinIndices.getX(i * 4 + j);
                }
            }

            // Get color for dominant bone
            const color = boneColors[dominantBone % boneColors.length];

            // Blend with gray based on weight strength (weaker = more gray)
            const blendedColor = new THREE.Color().lerpColors(
                new THREE.Color(0x808080),
                color,
                maxWeight
            );

            colors[i * 3] = blendedColor.r;
            colors[i * 3 + 1] = blendedColor.g;
            colors[i * 3 + 2] = blendedColor.b;
        }

        // Add vertex colors to geometry
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

        // Return material that uses vertex colors
        return new THREE.MeshBasicMaterial({
            vertexColors: true,
            side: THREE.DoubleSide
        });
    }

    /**
     * Log detailed weight information for debugging
     */
    logWeightDebugInfo(skinnedMesh, skeleton) {
        const geometry = skinnedMesh.geometry;
        const skinIndices = geometry.attributes.skinIndex;
        const skinWeights = geometry.attributes.skinWeight;
        const numVertices = geometry.attributes.position.count;

        console.log('[SkinWeightTransfer DEBUG] Weight distribution:');

        // Count vertices per dominant bone
        const boneCounts = {};
        let totalWeight = 0;
        let zeroWeightVertices = 0;

        for (let i = 0; i < numVertices; i++) {
            let vertexTotalWeight = 0;
            let maxWeight = 0;
            let dominantBone = 0;

            for (let j = 0; j < 4; j++) {
                const weight = skinWeights.getX(i * 4 + j);
                const boneIdx = skinIndices.getX(i * 4 + j);
                vertexTotalWeight += weight;

                if (weight > maxWeight) {
                    maxWeight = weight;
                    dominantBone = boneIdx;
                }
            }

            if (vertexTotalWeight < 0.001) {
                zeroWeightVertices++;
            }

            totalWeight += vertexTotalWeight;
            boneCounts[dominantBone] = (boneCounts[dominantBone] || 0) + 1;
        }

        console.log(`  Total vertices: ${numVertices}`);
        console.log(`  Average weight sum per vertex: ${(totalWeight / numVertices).toFixed(4)}`);
        console.log(`  Vertices with ~0 weight: ${zeroWeightVertices}`);
        console.log(`  Bone distribution:`);

        for (const [boneIdx, count] of Object.entries(boneCounts)) {
            const boneName = skeleton.bones[boneIdx]?.name || `bone_${boneIdx}`;
            const pct = ((count / numVertices) * 100).toFixed(1);
            console.log(`    ${boneName}: ${count} vertices (${pct}%)`);
        }
    }
}
