# Gaussian Splat Clothing Pipeline - Development Plan

## Overview
Replace Rodin API mesh generation with local Gaussian Splat generation for real-time clothing visualization with body tracking.

---

## Phase 1: Depth-Based 3D Generation (1-2 days)
**Goal:** Generate proper 3D splats from 2D clothing images using depth estimation

### Tasks:
1. [ ] Integrate Apple Depth Pro or Depth Anything V2
   - Install: `pip install git+https://github.com/apple/ml-depth-pro.git`
   - Or: Clone Depth-Anything-V2 repo

2. [ ] Modify `generate_splat.py` to use real depth
   ```python
   # Replace flat Z projection with:
   depth_map = depth_model.infer(image)
   z_coords = depth_map[valid_pixels] * depth_scale
   ```

3. [ ] Test with clothing images
   - Verify depth quality on generated clothing
   - Tune depth scale for proper 3D appearance

### Deliverable:
Clothing images render as proper 3D shapes (not flat planes)

---

## Phase 2: Migrate to Spark Library (1 day)
**Goal:** Use actively maintained library with dynamic splat APIs

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
       }
   });
   ```

3. [ ] Verify scene-level transforms work with Three.js integration

### Deliverable:
Viewer uses Spark with proper dynamic manipulation APIs

---

## Phase 3: SMPL-X Body Model Integration (2-3 days)
**Goal:** Fit body model to BlazePose landmarks for skinning

### Tasks:
1. [ ] Install SMPL-X dependencies
   ```bash
   pip install smplx
   # Download SMPL-X model files (requires registration)
   ```

2. [ ] Create BlazePose → SMPL-X fitting module
   - Map 33 BlazePose landmarks to SMPL-X joints
   - Use EasyMocap or similar for fitting

3. [ ] Initialize Gaussians from SMPL-X vertices
   - Sample ~50K-200K points from mesh surface
   - Assign per-Gaussian skinning weights from barycentric coordinates

4. [ ] Export skinning weights with PLY
   - Add custom attributes for bone weights/indices

### Deliverable:
Clothing splats attached to SMPL-X body model

---

## Phase 4: Linear Blend Skinning Animation (2-3 days)
**Goal:** Animate clothing splats based on body pose

### Tasks:
1. [ ] Implement CPU-based LBS first (for validation)
   ```python
   for gaussian in gaussians:
       final_pos = sum(weight * bone_transform @ position
                      for weight, bone_transform in zip(weights, transforms))
   ```

2. [ ] Move to GPU shader for performance
   ```glsl
   // Vertex shader
   vec4 skinnedPos = vec4(0.0);
   for (int i = 0; i < 4; i++) {
       skinnedPos += boneWeights[i] * (boneMatrices[int(boneIndices[i])] * position);
   }
   ```

3. [ ] Handle quaternion rotation properly
   - Blend rotations using SLERP or dual quaternions
   - Apply to Gaussian rotation attribute

4. [ ] Test with BlazePose real-time input
   - Connect to existing WebSocket body tracking
   - Verify 30+ FPS performance

### Deliverable:
Clothing moves with body in real-time

---

## Phase 5: Pipeline Integration (1-2 days)
**Goal:** Replace Rodin API in main pipeline

### Tasks:
1. [ ] Create unified generation endpoint
   ```python
   # speech_to_clothing_with_rodin_api.py
   if use_gaussian_splats:
       result = gaussian_generator.generate(clothing_image)
   else:
       result = rodin_api.generate(clothing_image)  # Fallback
   ```

2. [ ] Update WebSocket protocol for splat data
   - Send splat positions/colors instead of GLB base64
   - Or serve .splat file URL

3. [ ] Modify Three.js viewer to load splats
   - Use Spark's `addSplatScene()` or similar

4. [ ] Test full pipeline: Speech → 2D → 3D Splat → Body Tracking

### Deliverable:
Complete local pipeline without external 3D API

---

## Phase 6: Advanced Features (Optional, 1-2 weeks)

### 6a. Physics-Based Cloth Simulation
- Integrate concepts from PGC (Physics-Based Gaussian Cloth)
- Add cloth dynamics using XPBD or similar
- Enable realistic draping and movement

### 6b. Multi-View Consistency (GS-VTON approach)
- Use reference-driven inpainting for multiple views
- Train LoRA for consistent garment appearance
- Improve 3D reconstruction quality

### 6c. Layered Clothing (LayGA approach)
- Separate body and clothing Gaussian layers
- Enable clothing transfer between avatars
- Support multiple garment combinations

---

## Key GitHub Repositories

### Must-Have:
- [apple/ml-depth-pro](https://github.com/apple/ml-depth-pro) - Depth estimation
- [sparkjsdev/spark](https://github.com/sparkjsdev/spark) - 3DGS viewer
- [vchoutas/smplx](https://github.com/vchoutas/smplx) - Body model

### Reference Implementation:
- [yukangcao/GS-VTON](https://github.com/yukangcao/GS-VTON) - Virtual try-on
- [eth-ait/Gaussian-Garments](https://github.com/eth-ait/Gaussian-Garments) - Garment reconstruction
- [mikeqzy/3dgs-avatar-release](https://github.com/mikeqzy/3dgs-avatar-release) - Avatar animation
- [kv2000/ASH](https://github.com/kv2000/ASH) - Advanced skinning

### Curated Lists:
- [MrNeRF/awesome-3D-gaussian-splatting](https://github.com/MrNeRF/awesome-3D-gaussian-splatting)

---

## Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| 3D Generation | 60-90s (Rodin) | <5s (local) |
| Rendering FPS | 30 (GLB) | 60+ (3DGS) |
| Animation Latency | N/A | <16ms |
| Memory (GPU) | ~200MB | ~500MB |

---

## Decision Points

### Q1: Spark vs Custom WebGL Implementation?
**Recommendation:** Start with Spark, consider custom only if performance insufficient.

### Q2: CPU vs GPU Skinning?
**Recommendation:** Start CPU for correctness, migrate to GPU for production.

### Q3: LBS vs Dual Quaternion Skinning?
**Recommendation:** Start LBS, upgrade to DQS only if candy-wrapper artifacts appear.

### Q4: Keep Rodin API as Fallback?
**Recommendation:** Yes, for reliability during development and for high-quality static renders.

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | 1-2 days | None |
| Phase 2 | 1 day | Phase 1 |
| Phase 3 | 2-3 days | Phase 2 |
| Phase 4 | 2-3 days | Phase 3 |
| Phase 5 | 1-2 days | Phase 4 |
| **Total** | **7-11 days** | |

---

## Questions to Resolve

1. **Do we need physics simulation?** (Adds complexity but enables realistic cloth behavior)
2. **Single garment or layered outfits?** (Layered requires more sophisticated separation)
3. **Target device?** (Mobile requires aggressive optimization, ~60K splats max)
4. **Offline generation acceptable?** (Real-time generation is much harder)

---

## Next Immediate Step

**Phase 1, Task 1:** Install depth estimation and test on clothing images.

```bash
# Quick test
cd gaussian_test
pip install git+https://github.com/apple/ml-depth-pro.git
python -c "from depth_pro import DepthPro; print('Depth Pro ready')"
```
