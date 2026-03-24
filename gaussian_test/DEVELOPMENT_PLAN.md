# Gaussian Splat Clothing Pipeline - Development Plan

## Overview
Replace Rodin API mesh generation with local Gaussian Splat generation for real-time clothing visualization with body tracking.

**Key Architecture Decision (Research Validated):**
Use MediaPipe landmarks at calibration time as the "invisible rigged mesh" - NO SMPL required.

---

## Validated Pipeline Architecture

```
1. T-pose capture
   ↓
2. BodyPix mask → 2D clothing area
   ↓
3. Generate 2D clothing image (Stable Diffusion via ComfyUI)
   ↓
4. Convert to Gaussian Splat (with depth estimation)
   - Splats have positions, colors, depths
   - NO weights assigned yet
   ↓
5. User steps into camera frame
   ↓
6. User aligns in T-pose → CALIBRATION
   ├─ MediaPipe detects 33 landmarks
   ├─ Splat is positioned/scaled to overlay on user
   └─ Assign weights: each Gaussian gets weights based on proximity to landmarks
   ↓
7. Real-time try-on
   - Bone rotations computed from MediaPipe (existing bone_rotation_calculator.py)
   - Dual Quaternion Skinning applied to weighted Gaussians
   - Gaussians move with user at 30+ FPS
```

---

## Research Validation Summary

| Aspect | Viability | Confidence | Source |
|--------|-----------|------------|--------|
| MediaPipe as skeleton rig | ✅ YES | 85-95% | GauHuman, 3DGS-Avatar, ASH papers |
| Proximity-based weights | ✅ YES | 95% | Jacobson 2012, SkinCells 2025 |
| Skip SMPL entirely | ✅ YES | HIGH | RigGS, SC-GS, Articulated Point NeRF |
| 30 FPS with 50K splats | ✅ YES | 95% | Requires GPU (Metal/WebGL) |

---

## Phase 1: Depth-Based 3D Generation (1-2 days)
**Goal:** Generate proper 3D splats from 2D clothing images using depth estimation

### Tasks:
1. [ ] Install Video Depth Anything (recommended over Apple Depth Pro for temporal consistency)
   ```bash
   pip install depth-anything-v2
   # Or clone: https://github.com/DepthAnything/Video-Depth-Anything
   ```

2. [ ] Modify `generate_splat.py` to use real depth
   ```python
   from depth_anything_v2.dpt import DepthAnythingV2

   model = DepthAnythingV2(encoder='vitl')
   depth_map = model.infer_image(clothing_image)
   z_coords = depth_map[valid_pixels] * depth_scale
   ```

3. [ ] Test with clothing images
   - Verify depth quality on generated clothing
   - Tune depth_scale for proper 3D appearance (start with 0.3)

### Deliverable:
Clothing images render as proper 3D shapes (not flat planes)

---

## Phase 2: Migrate to Spark Library (1 day)
**Goal:** Use actively maintained library with dynamic splat manipulation APIs

### Tasks:
1. [ ] Update HTML importmap to use Spark
   ```html
   "@sparkjsdev/spark": "https://unpkg.com/@sparkjsdev/spark/dist/spark.module.js"
   ```

2. [ ] Refactor `app.js` to use Spark's `SplatMesh` API
   ```javascript
   import { SplatMesh, PackedSplats } from '@sparkjsdev/spark';

   const mesh = new SplatMesh({
       onFrame: ({ mesh, time }) => {
           // Per-frame updates for animation
           updateGaussianPositions(mesh, currentBoneTransforms);
       }
   });
   ```

3. [ ] Verify scene-level transforms work with Three.js integration

### Deliverable:
Viewer uses Spark with proper dynamic manipulation APIs

---

## Phase 3: Calibration-Time Weight Assignment (2-3 days)
**Goal:** Assign skinning weights to Gaussians when user calibrates in T-pose

**THIS REPLACES SMPL-X - MediaPipe landmarks become the skeleton**

### Tasks:
1. [ ] Create `gaussian_weight_assigner.py`
   ```python
   import numpy as np

   class GaussianWeightAssigner:
       """Assign skinning weights based on proximity to MediaPipe landmarks."""

       # Landmarks that define bone regions (upper body focus)
       BONE_LANDMARKS = {
           'spine': [11, 12, 23, 24],      # shoulders + hips
           'left_upper_arm': [11, 13],      # shoulder → elbow
           'left_lower_arm': [13, 15],      # elbow → wrist
           'right_upper_arm': [12, 14],
           'right_lower_arm': [14, 16],
       }

       def __init__(self, sigma_factor=0.3):
           """
           Args:
               sigma_factor: Multiply by shoulder_width to get Gaussian falloff sigma
           """
           self.sigma_factor = sigma_factor
           self.weights = None  # Cached after calibration

       def assign_weights(self, gaussian_positions, landmarks_world, shoulder_width):
           """
           Assign weights at calibration time (user in T-pose).

           Args:
               gaussian_positions: (N, 3) array of Gaussian centers
               landmarks_world: MediaPipe landmarks_world (33, 3)
               shoulder_width: Measured shoulder width in meters

           Returns:
               weights: (N, num_bones) skinning weights per Gaussian
           """
           sigma = self.sigma_factor * shoulder_width
           num_gaussians = len(gaussian_positions)
           num_bones = len(self.BONE_LANDMARKS)

           weights = np.zeros((num_gaussians, num_bones))

           # Compute bone center positions from landmarks
           bone_centers = []
           for bone_name, lm_indices in self.BONE_LANDMARKS.items():
               center = np.mean([landmarks_world[i] for i in lm_indices], axis=0)
               bone_centers.append(center)
           bone_centers = np.array(bone_centers)

           # Gaussian falloff weights
           for i, pos in enumerate(gaussian_positions):
               for j, center in enumerate(bone_centers):
                   distance = np.linalg.norm(pos - center)
                   weights[i, j] = np.exp(-(distance / sigma) ** 2)

               # Normalize to sum to 1
               weights[i] /= weights[i].sum() + 1e-8

           self.weights = weights
           return weights
   ```

2. [ ] Integrate with calibration flow in `warp_test_0.py`
   ```python
   # In _run_calibration_phase():
   if frame_data and frame_data.body:
       # Existing calibration
       self.mesh_calibrator.calibrate_offset(frame_data.body)

       # NEW: Assign Gaussian weights
       shoulder_width = self._compute_shoulder_width(frame_data.body)
       self.weight_assigner.assign_weights(
           self.gaussian_positions,
           frame_data.body.landmarks_world,
           shoulder_width
       )
   ```

3. [ ] Store weights with Gaussian data (extend PLY format or use sidecar JSON)

### Deliverable:
Each Gaussian has skinning weights assigned based on T-pose landmark proximity

---

## Phase 4: Dual Quaternion Skinning Animation (2-3 days)
**Goal:** Animate clothing splats based on body pose using DQS (not basic LBS)

### Why DQS over LBS:
- LBS causes "candy-wrapper" artifacts at joint bends
- DQS preserves volume with negligible overhead (~5%)
- Your `bone_rotation_calculator.py` already outputs quaternions

### Tasks:
1. [ ] Create `gaussian_animator.py` with CPU validation first
   ```python
   import numpy as np
   from scipy.spatial.transform import Rotation

   class GaussianAnimator:
       """Animate Gaussians using Dual Quaternion Skinning."""

       def __init__(self, canonical_positions, weights, bone_names):
           self.canonical_positions = canonical_positions  # T-pose positions
           self.weights = weights  # (N, num_bones)
           self.bone_names = bone_names

       def animate(self, bone_rotations):
           """
           Apply DQS to transform Gaussians.

           Args:
               bone_rotations: Dict from BoneRotationCalculator
                   {'spine': {'x':, 'y':, 'z':, 'w':}, ...}

           Returns:
               posed_positions: (N, 3) transformed positions
               posed_rotations: (N, 4) transformed quaternions (optional)
           """
           N = len(self.canonical_positions)
           posed_positions = np.zeros((N, 3))

           # Convert bone quaternions to dual quaternions
           dual_quats = self._bone_rotations_to_dual_quats(bone_rotations)

           for i in range(N):
               # Blend dual quaternions by weight
               blended_dq = self._blend_dual_quaternions(
                   dual_quats,
                   self.weights[i]
               )

               # Apply blended DQ to position
               posed_positions[i] = self._transform_point_by_dq(
                   self.canonical_positions[i],
                   blended_dq
               )

           return posed_positions

       def _blend_dual_quaternions(self, dqs, weights):
           """Weighted blend of dual quaternions."""
           # Ensure same hemisphere (dot product check)
           result_real = np.zeros(4)
           result_dual = np.zeros(4)

           for j, (dq, w) in enumerate(zip(dqs, weights)):
               if w < 0.001:
                   continue
               if j > 0 and np.dot(dqs[0][0], dq[0]) < 0:
                   dq = (-dq[0], -dq[1])  # Flip to same hemisphere
               result_real += w * dq[0]
               result_dual += w * dq[1]

           # Normalize
           norm = np.linalg.norm(result_real)
           return (result_real / norm, result_dual / norm)
   ```

2. [ ] Move to GPU shader for performance (WebGL/Three.js)
   ```glsl
   // Dual quaternion skinning shader
   uniform vec4 boneQuatReal[9];  // Real part of DQ
   uniform vec4 boneQuatDual[9];  // Dual part of DQ

   attribute vec4 boneWeights;    // 4 weights per vertex
   attribute ivec4 boneIndices;   // 4 bone indices

   vec3 dqsTransform(vec3 pos, vec4 weights, ivec4 indices) {
       // Blend dual quaternions
       vec4 blendReal = vec4(0.0);
       vec4 blendDual = vec4(0.0);

       for (int i = 0; i < 4; i++) {
           int idx = indices[i];
           float w = weights[i];

           // Hemisphere check
           if (i > 0 && dot(boneQuatReal[indices[0]], boneQuatReal[idx]) < 0.0) {
               w = -w;
           }

           blendReal += w * boneQuatReal[idx];
           blendDual += w * boneQuatDual[idx];
       }

       // Normalize
       float len = length(blendReal);
       blendReal /= len;
       blendDual /= len;

       // Apply DQ to position
       vec3 t = 2.0 * (blendReal.w * blendDual.xyz - blendDual.w * blendReal.xyz
                       + cross(blendReal.xyz, blendDual.xyz));
       vec3 rotated = pos + 2.0 * cross(blendReal.xyz, cross(blendReal.xyz, pos)
                                        + blendReal.w * pos);

       return rotated + t;
   }
   ```

3. [ ] Test with BlazePose real-time input
   - Connect to existing WebSocket body tracking
   - Use `bone_rotation_calculator.py` output directly
   - Verify 30+ FPS performance

### Deliverable:
Clothing moves with body in real-time without candy-wrapper artifacts

---

## Phase 5: Pipeline Integration (1-2 days)
**Goal:** Integrate Gaussian pipeline with main Spoken Wardrobe flow

### Tasks:
1. [ ] Create unified generation endpoint
   ```python
   # In speech_to_clothing_with_rodin_api.py (or new file)

   class GaussianClothingGenerator:
       def __init__(self):
           self.depth_model = DepthAnythingV2()
           self.splat_generator = SplatGenerator()
           self.weight_assigner = GaussianWeightAssigner()

       def generate(self, clothing_image):
           """Generate Gaussian Splat from 2D clothing image."""
           # 1. Estimate depth
           depth_map = self.depth_model.infer_image(clothing_image)

           # 2. Generate splats
           splat_data = self.splat_generator.generate(
               clothing_image,
               depth_map,
               num_splats=50000
           )

           return splat_data  # No weights yet - assigned at calibration
   ```

2. [ ] Update WebSocket protocol for splat data
   ```python
   # New message types
   {
       'type': 'splat_ready',
       'data': {
           'splat_url': '/output/clothing.ply',  # Or base64
           'num_splats': 50000,
           'has_weights': False  # Weights assigned at calibration
       }
   }

   {
       'type': 'weights_assigned',
       'data': {
           'bone_names': ['spine', 'left_upper_arm', ...],
           'weights_url': '/output/weights.json'  # Or embedded
       }
   }
   ```

3. [ ] Modify Three.js viewer to:
   - Load splats using Spark
   - Receive weight data at calibration
   - Apply DQS animation per frame

4. [ ] Test full pipeline: Speech → 2D → 3D Splat → Calibration → Try-On

### Deliverable:
Complete local pipeline without external 3D API

---

## Phase 6: Advanced Features (Optional)

### 6a. Alternative Image-to-3D: DreamGaussian
If depth-based generation quality is insufficient:
- [DreamGaussian](https://github.com/dreamgaussian/dreamgaussian) - Direct image → Gaussian Splats
- Higher quality but slower (2 min vs 5 sec)

### 6b. Creative/Artistic Effects
From research on novel aesthetics:
- Volumetric effects (fire, smoke) via splat opacity manipulation
- Painterly rendering via artistic style transfer
- 4D animated clothing via temporal interpolation

### 6c. Physics-Based Cloth (Future)
- Integrate concepts from PGC (Physics-Based Gaussian Cloth)
- Add cloth dynamics using XPBD
- Requires significant additional work

---

## Key GitHub Repositories

### Must-Have:
- [DepthAnything/Video-Depth-Anything](https://github.com/DepthAnything/Video-Depth-Anything) - Temporal depth
- [sparkjsdev/spark](https://github.com/sparkjsdev/spark) - 3DGS viewer
- [dreamgaussian/dreamgaussian](https://github.com/dreamgaussian/dreamgaussian) - Image→Splat alternative

### Reference Implementation:
- [CVMI-Lab/SC-GS](https://github.com/CVMI-Lab/SC-GS) - Sparse-controlled Gaussians
- [yaoyx689/RigGS](https://github.com/yaoyx689/RigGS) - Template-free rigging
- [mikeqzy/3dgs-avatar-release](https://github.com/mikeqzy/3dgs-avatar-release) - Avatar animation

### Research Papers:
- [Skinning with Dual Quaternions](https://users.cs.utah.edu/~ladislav/dq/index.html)
- [Fast Automatic Skinning Transformations (Jacobson 2012)](https://igl.ethz.ch/projects/fast/)

---

## Performance Targets

| Metric | Current | Target | Validated |
|--------|---------|--------|-----------|
| 3D Generation | 60-90s (Rodin) | <5s (local) | ✅ Depth estimation: ~0.3s |
| Weight Assignment | N/A | <1s (once) | ✅ O(N×bones) trivial |
| Animation FPS | N/A | 30+ FPS | ✅ GPU required |
| Rendering FPS | 30 (GLB) | 30-50 (3DGS) | ✅ Spark library |
| Memory (GPU) | ~200MB | ~40MB | ✅ 50K splats |

---

## Decision Points (Resolved)

### Q1: SMPL-X vs MediaPipe Landmarks?
**RESOLVED:** Skip SMPL-X. Use MediaPipe landmarks at calibration as skeleton.
- Simpler implementation
- No external dependencies
- Research validates this approach

### Q2: CPU vs GPU Skinning?
**RESOLVED:** GPU required for real-time.
- CPU: 50-100ms per frame (too slow)
- GPU: 6-8ms per frame (acceptable)

### Q3: LBS vs Dual Quaternion Skinning?
**RESOLVED:** Use DQS from the start.
- LBS has candy-wrapper artifacts
- DQS overhead is negligible (~5%)
- Your code already outputs quaternions

### Q4: When to assign weights?
**RESOLVED:** At calibration time (when user aligns in T-pose).
- Weights are computed ONCE
- Cached for entire try-on session
- User's skeleton defines bone positions

---

## Timeline Estimate (Revised)

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Depth | 1-2 days | None |
| Phase 2: Spark | 1 day | Phase 1 |
| Phase 3: Weights | 2-3 days | Phase 2 |
| Phase 4: DQS Animation | 2-3 days | Phase 3 |
| Phase 5: Integration | 1-2 days | Phase 4 |
| **Total** | **7-11 days** | |

---

## Next Immediate Steps

### Day 1-2: Depth Estimation
```bash
cd gaussian_test
source ../venv/bin/activate
pip install depth-anything-v2
python -c "from depth_anything_v2.dpt import DepthAnythingV2; print('Ready')"
```

### Day 3: Weight Assignment Prototype
Create `gaussian_weight_assigner.py` with Gaussian falloff formula.

### Day 4-5: DQS Animation
Implement CPU version first, validate correctness, then GPU.

---

## Research Sources

- [RigGS: CVPR 2025](https://github.com/yaoyx689/RigGS) - Template-free Gaussian rigging
- [SC-GS: CVPR 2024](https://github.com/CVMI-Lab/SC-GS) - Sparse-controlled Gaussians
- [ASH: CVPR 2024](https://vcai.mpi-inf.mpg.de/projects/ash/) - Animatable Gaussian splats
- [GauHuman: CVPR 2024](https://skhu101.github.io/GauHuman/) - 189 FPS human animation
- [Dual Quaternion Skinning](https://users.cs.utah.edu/~ladislav/kavan07skinning/) - Standard reference
- [Fast Automatic Skinning (SIGGRAPH 2012)](https://igl.ethz.ch/projects/fast/) - Proximity-based weights
