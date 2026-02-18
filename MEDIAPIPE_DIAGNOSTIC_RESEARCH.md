# MediaPipe Diagnostic Tool - Research & Implementation Plan

## Date: 2026-02-17

## Overview

This document outlines research findings and implementation strategies for creating a MediaPipe-based diagnostic tool that addresses:
1. **Spine rigid transform** (no warping for root bone movements)
2. **MediaPipe pose tracking** integration with orientation-only mode
3. **Weight quality improvements** (research only - defer implementation)

---

## Issue #1: Spine Rigid Transform (PRIORITY)

### Problem Description

Currently, when the spine bone rotates, the clothing mesh deforms (warps) as if it were a limb. This causes unnatural distortion. Instead:
- **Desired:** Spine rotation should move the entire clothing mesh as a rigid body
- **Current:** Spine rotation causes skeletal skinning deformation
- **Root cause:** All bones (including spine) are treated equally in the skinning system

### Research Findings

From Three.js skeletal animation research:
- Three.js SkinnedMesh applies bone transforms equally to all bones
- The vertex shader computes: `finalPosition = Σ(boneMatrix[i] * bindMatrix[i]^-1 * position * weight[i])`
- There's no built-in concept of "root motion" or "rigid transform bones"

**Sources:**
- [Skeletal Animation & Skinning - DeepWiki](https://deepwiki.com/mrdoob/three.js/5.2-skeletal-animation-and-skinning)
- [Rigging and skeletal animation in Three.js](https://roman01la-blog.tumblr.com/post/60461559240/rigging-and-skeletal-animation-in-threejs)

### Proposed Solutions

#### Solution A: Dual Transform System (RECOMMENDED)

Separate spine movement into two layers:
1. **Global Transform** (mesh-level): Handle spine position/rotation as rigid transform
2. **Local Skinning** (vertex-level): Only apply skeletal deformation for limbs

**Implementation:**
```javascript
// 1. Extract spine bone world transform
const spineWorldMatrix = skeleton.bones[0].matrixWorld.clone();

// 2. Apply to clothing mesh as rigid transform
clothingMesh.matrix.copy(spineWorldMatrix);
clothingMesh.matrixAutoUpdate = false;

// 3. Modify skeleton to use spine-relative transforms for skinning
// Set spine bone to identity in skeleton (it's already applied at mesh level)
skeleton.bones[0].matrix.identity();
skeleton.bones[0].updateMatrixWorld(true);

// 4. Child bones (arms, legs) now animate relative to identity spine
// This causes warping only for limbs, not the torso
```

**Pros:**
- Clean separation of concerns
- Spine movement doesn't cause mesh warping
- Limbs still animate correctly relative to body

**Cons:**
- Need to track spine bone index (currently bone 0)
- Need to update spine transform separately from skeletal animation

#### Solution B: Weight Zeroing

Set all spine bone weights to zero in the skinning data, and manually position the mesh.

**Pros:**
- Simple to implement

**Cons:**
- Torso wouldn't deform at all (can't bend forward)
- Loses granularity

#### Solution C: Hybrid Approach

Detect magnitude of spine rotation:
- Small rotations (< 15°) → Rigid transform
- Large rotations (> 15°) → Skeletal warping (torso bend)

**Pros:**
- Handles both cases

**Cons:**
- Complex threshold tuning
- Potential discontinuities at transition

### Recommended Implementation: Solution A

1. **Track spine bone** (bone index 0 - "spine")
2. **Before rendering:**
   - Extract spine world matrix
   - Apply to clothing mesh as rigid transform
   - Reset spine bone to identity in skeleton
   - Update child bones (relative to identity spine)
3. **Render:** Skinning shader applies deformation only to limbs

---

## Issue #2: MediaPipe Pose Integration

### Research Findings

MediaPipe Pose provides:
- **33 3D body landmarks** with depth information
- **Real-time performance** (30+ FPS on webcam)
- **Three complexity levels:** Lite (fast), Full (balanced), Heavy (accurate)
- **Web implementation:** Available via `@mediapipe/tasks-vision` NPM package
- **Orientation-only mode:** Track landmark positions in 2D/3D, map to bone rotations

**Sources:**
- [Real-Time Body Tracking in Browser with MediaPipe](https://medium.com/@creativeaininja/real-time-body-tracking-in-your-browser-what-mediapipe-actually-does-and-how-to-use-it-b31aa96a5071)
- [MediaPipe Pose Landmarker Web Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js)
- [High Fidelity Pose Tracking with BlazePose and TensorFlow.js](https://blog.tensorflow.org/2021/05/high-fidelity-pose-tracking-with-mediapipe-blazepose-and-tfjs.html)

### Key Landmarks for Body Tracking

MediaPipe provides 33 landmarks, key ones for skeletal mapping:
- **Spine/Torso:** 11 (left shoulder), 12 (right shoulder), 23 (left hip), 24 (right hip)
- **Arms:** 11, 13, 15 (left: shoulder, elbow, wrist), 12, 14, 16 (right)
- **Legs:** 23, 25, 27 (left: hip, knee, ankle), 24, 26, 28 (right)
- **Head:** 0 (nose), 7 (left ear), 8 (right ear)

### Implementation Strategy

#### Option 1: Orientation-Only (RECOMMENDED for now)

**Approach:**
1. **Initialize:** Load MediaPipe Pose model (Full complexity)
2. **Capture:** Get webcam feed using `getUserMedia()`
3. **Detect:** Run MediaPipe pose detection on each frame
4. **Map Landmarks to Bones:**
   - Calculate bone vectors from landmark pairs
   - Compute rotation quaternions from vectors
   - Apply rotations to skeleton bones
5. **Render:** Clothing mesh follows bone rotations (centered on screen)

**Bone Mapping:**
```javascript
const boneMapping = {
    'spine': {
        landmarks: [11, 12, 23, 24],  // shoulders + hips
        computeRotation: (landmarks) => {
            // Calculate torso orientation from shoulder-hip alignment
            const shoulderVec = landmarks[12].sub(landmarks[11]);
            const hipVec = landmarks[24].sub(landmarks[23]);
            // ... compute quaternion
        }
    },
    'left_upper_arm': {
        landmarks: [11, 13],  // shoulder to elbow
        parent: 'spine'
    },
    'left_lower_arm': {
        landmarks: [13, 15],  // elbow to wrist
        parent: 'left_upper_arm'
    },
    // ... similar for other bones
};
```

**Pros:**
- Stable (no position jitter)
- Works with any webcam (no depth sensor needed)
- Feels like "avatar control"

**Cons:**
- No translation (mesh stays centered)
- Requires mapping 33 landmarks → 9 bones

#### Option 2: Full 3D Tracking

Track position + orientation using MediaPipe's depth estimates.

**Pros:**
- More immersive (mesh moves with user)

**Cons:**
- Depth estimation less accurate than OAK-D Pro
- More jitter/noise
- Harder to tune

**Decision:** Start with Option 1 (orientation-only), can add Option 2 later

### MediaPipe Integration Steps

1. **Add MediaPipe library:**
   ```html
   <script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js"></script>
   <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>
   <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>
   ```

2. **Initialize pose detector:**
   ```javascript
   const pose = new Pose({
       locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
   });

   pose.setOptions({
       modelComplexity: 1,  // 0=Lite, 1=Full, 2=Heavy
       smoothLandmarks: true,
       minDetectionConfidence: 0.5,
       minTrackingConfidence: 0.5
   });
   ```

3. **Setup webcam:**
   ```javascript
   const videoElement = document.createElement('video');
   const camera = new Camera(videoElement, {
       onFrame: async () => {
           await pose.send({image: videoElement});
       },
       width: 1280,
       height: 720
   });
   camera.start();
   ```

4. **Process results:**
   ```javascript
   pose.onResults((results) => {
       if (results.poseLandmarks) {
           updateSkeletonFromLandmarks(results.poseLandmarks);
       }
   });
   ```

5. **Map to skeleton bones:**
   ```javascript
   function updateSkeletonFromLandmarks(landmarks) {
       // For each bone in skeleton
       for (const [boneName, boneData] of Object.entries(boneMapping)) {
           const bone = skeleton.bones.find(b => b.name === boneName);

           // Get landmark positions
           const startPos = landmarks[boneData.landmarks[0]];
           const endPos = landmarks[boneData.landmarks[1]];

           // Calculate bone vector
           const boneVec = new THREE.Vector3(
               endPos.x - startPos.x,
               -(endPos.y - startPos.y),  // Flip Y (MediaPipe Y is down)
               endPos.z - startPos.z
           );

           // Compute rotation to align bone with vector
           const rotation = computeRotationFromVector(boneVec, bone.userData.restDirection);

           // Apply rotation
           bone.quaternion.copy(rotation);
       }

       skeleton.update();
   }
   ```

---

## Issue #3: Weight Quality Improvements (RESEARCH ONLY)

### Problem Description

Clothing mesh vertices don't always follow body correctly:
- **Arm ends** (hands/wrists) left behind when arms rotate
- **Chest vertices** incorrectly assigned to arm bones (move with arms instead of torso)
- **Suggests:** Weight transfer assigned wrong bones at boundary regions

### Research Findings

#### Geodesic Distance Weighting

**Current approach:** Euclidean distance (straight-line) from clothing vertex to body surface
**Better approach:** Geodesic distance (surface distance) along body mesh

**Paper:** [Geodesic Voxel Binding for Production Character Meshes (SCA 2013)](https://dl.acm.org/doi/10.1145/2485895.2485919)

**Key insight:** Geodesic distance respects mesh topology, preventing "bleeding" across body parts.

**Example:**
- Clothing vertex on left chest near shoulder
- **Euclidean:** Might find closest point on right arm (if arm is raised)
- **Geodesic:** Finds closest point on left chest/torso (surface distance)

**Implementation:**
- Build geodesic distance field from body mesh
- Use Fast Marching Method or Heat Method
- Libraries: `geodesic` npm package, or custom heat diffusion

#### Laplacian Smoothing

**Current approach:** No smoothing - weights are transferred as-is
**Better approach:** Smooth weights spatially on clothing mesh

**Paper:** [Laplacian mesh smoothing with bilateral weights](https://www.tandfonline.com/doi/full/10.1080/21642583.2025.2568665)

**Key insight:** Vertex weights should vary smoothly across mesh, avoiding hard transitions.

**Algorithm:**
1. For each vertex, compute average of neighbor weights
2. Blend with original weight: `w_new = α * w_original + (1-α) * w_neighbors`
3. Iterate 3-5 times
4. Normalize so weights sum to 1.0

**Pseudocode:**
```javascript
function smoothWeights(geometry, skinIndices, skinWeights, iterations = 3) {
    const positions = geometry.attributes.position;
    const numVerts = positions.count;

    // Build adjacency list
    const neighbors = buildAdjacencyList(geometry);

    for (let iter = 0; iter < iterations; iter++) {
        const newWeights = skinWeights.array.slice();

        for (let i = 0; i < numVerts; i++) {
            for (let k = 0; k < 4; k++) {
                const idx = i * 4 + k;
                const boneIdx = skinIndices.array[idx];
                const weight = skinWeights.array[idx];

                // Average with neighbors
                let sum = weight;
                let count = 1;

                for (const neighborIdx of neighbors[i]) {
                    for (let j = 0; j < 4; j++) {
                        const nIdx = neighborIdx * 4 + j;
                        if (skinIndices.array[nIdx] === boneIdx) {
                            sum += skinWeights.array[nIdx];
                            count++;
                        }
                    }
                }

                newWeights[idx] = sum / count;
            }

            // Normalize
            const total = newWeights[i*4] + newWeights[i*4+1] + newWeights[i*4+2] + newWeights[i*4+3];
            for (let k = 0; k < 4; k++) {
                newWeights[i * 4 + k] /= total;
            }
        }

        skinWeights.array.set(newWeights);
    }
}
```

#### Heat Diffusion Method

**Paper:** [Robust Skin Weights Transfer via Weight Inpainting (University of Toronto)](https://www.dgp.toronto.edu/~rinat/projects/RobustSkinWeightsTransfer/preprint.pdf)

**Key insight:** Treat weight transfer as a "heat diffusion" problem - weights propagate from known regions to unknown regions.

**Approach:**
1. Transfer weights to "high confidence" vertices (close to body)
2. Mark "low confidence" vertices (far from body or in gaps)
3. Solve heat equation to diffuse weights from high → low confidence
4. Uses cotangent Laplacian for better results

**Benefits:**
- Fills in missing weights smoothly
- Handles difficult topology (holes, thin parts)
- Produces more natural deformations

#### Normal-Based Filtering

**Current approach:** Assign weights based only on distance
**Better approach:** Also consider surface normal alignment

**Idea:**
- Clothing vertex with normal pointing UP should not match body vertex with normal pointing DOWN
- Filter out matches where `dot(normal_clothing, normal_body) < threshold` (e.g., 0.3)

**Implementation:**
```javascript
// In BVH closest point loop
const clothingNormal = normals.getX(i), normals.getY(i), normals.getZ(i));
const bodyNormal = getBodyNormalAtPoint(target.point, target.faceIndex, bodyGeometry);

const alignment = clothingNormal.dot(bodyNormal);

if (alignment < 0.3) {
    // Normals point in opposite directions - bad match
    // Try next closest point or expand search radius
    continue;
}
```

### Recommended Implementation Priority (for later)

1. **Laplacian smoothing** (easiest, quick win)
   - Smooth existing weights spatially
   - ~50 lines of code
   - Immediate improvement

2. **Normal-based filtering** (medium complexity)
   - Reject bad matches during weight transfer
   - ~100 lines of code
   - Reduces arm/chest blending issues

3. **Geodesic distance** (complex, best results)
   - Replace Euclidean distance with geodesic
   - Requires external library or custom implementation
   - Most accurate, handles complex topology

4. **Heat diffusion** (advanced, research-level)
   - Full weight inpainting system
   - Significant implementation effort
   - Best for production-quality results

### Sources

- [Geodesic Voxel Binding (ACM SCA 2013)](https://dl.acm.org/doi/10.1145/2485895.2485919)
- [Robust Skin Weights Transfer via Weight Inpainting](https://www.dgp.toronto.edu/~rinat/projects/RobustSkinWeightsTransfer/preprint.pdf)
- [Automatic Skinning and Weight Retargeting](https://www3.cs.stonybrook.edu/~qin/research/2017-tvc-automatic-skinning-weight-retargeting.pdf)
- [Laplacian Mesh Smoothing with Bilateral Weights](https://www.tandfonline.com/doi/full/10.1080/21642583.2025.2568665)

---

## Implementation Plan

### Phase 1: Spine Rigid Transform (Current)
1. ✅ Research solutions
2. 🔄 Implement Solution A (dual transform system)
3. Test with bone rotation buttons in diagnostic tool
4. Verify spine rotation doesn't warp mesh

### Phase 2: MediaPipe Integration (Next)
1. ✅ Research MediaPipe Pose
2. Add MediaPipe libraries to HTML
3. Initialize pose detector with webcam
4. Map 33 landmarks → 9 skeleton bones
5. Implement orientation-only tracking (centered mesh)
6. Test real-time performance

### Phase 3: Weight Quality (Deferred)
1. ✅ Research smoothing techniques
2. Document recommended approaches
3. Defer implementation until MediaPipe is working
4. Revisit when ready for production quality

---

## Success Criteria

### Spine Rigid Transform
- ✅ Spine rotation moves entire mesh without warping
- ✅ Limb rotations still cause skeletal deformation
- ✅ Smooth transition between spine and limb movements

### MediaPipe Tracking
- ✅ 30+ FPS real-time tracking with webcam
- ✅ Bone rotations accurately follow user movements
- ✅ Mesh stays centered on screen (orientation-only mode)
- ✅ No significant jitter or lag

### Weight Quality (Future)
- Smooth weight transitions at bone boundaries
- Chest vertices stay with torso (not arms)
- Arm ends follow arm rotations correctly
- < 5% vertices with problematic weights

---

## Next Steps

1. Implement spine rigid transform in `mediapipe_diagnostic.html`
2. Test with existing bone rotation buttons
3. Add MediaPipe library integration
4. Map landmarks to bone rotations
5. Test with live webcam feed
6. Document results and iterate
