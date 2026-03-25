# Gaussian vs Polygon Warping Analysis - Session 250326

## Session Summary

This document captures the comprehensive analysis comparing the **polygon mesh warping** (working, web-based) and **Gaussian splat warping** (Python-based, issues) approaches in the Spoken Wardrobe project.

---

## What We Did This Session

### 1. Codebase Exploration
- Identified all files related to **polygon mesh warping** (17+ files)
- Identified all files related to **Gaussian splat warping** (15+ files)
- Mapped the complete data flow for both approaches

### 2. Deep Code Analysis
Read and analyzed the following critical files:

**Polygon Pipeline:**
- `static/js/SkinWeightTransfer.js` - BVH-accelerated weight transfer
- `static/js/SkeletalAnimator.js` - Real-time bone updates with SLERP
- `src/ui/bone_rotation_calculator.py` - 9-bone quaternion computation

**Gaussian Pipeline:**
- `gaussian_test/gaussian_animator.py` - DQS animation (CPU/GPU)
- `gaussian_test/gaussian_weight_assigner.py` - Distance-based weight assignment
- `gaussian_test/gaussian_tryon_pipeline.py` - Main orchestrator
- `gaussian_test/live_tryon_demo.py` - Live demo with MediaPipe

### 3. Identified Critical Issues
Found 4 major issues causing Gaussian version to underperform:
1. **Weight Assignment Method** - Uses distance to bone segments instead of body mesh surface
2. **Bone Definitions Mismatch** - 12 bones vs polygon's 9, different landmark pairs
3. **Missing Coordinate Transform** - No BlazePose Y-DOWN → Three.js Y-UP conversion
4. **No Temporal Smoothing** - Missing SLERP causes jitter

### 4. Web Portability Research
Analyzed feasibility of porting Gaussian to web:
- Current `@mkkellogg/gaussian-splats-3d` library doesn't support dynamic position updates
- Recommended approach: Treat Gaussians as InstancedMesh points, reuse polygon infrastructure

---

## Current State

### Polygon Mesh Warping ✅ WORKING
- Fully functional in browser
- GPU-accelerated via Three.js skeleton
- 30 FPS pose data, 60 FPS rendering
- Professional weight transfer via BVH + barycentric interpolation

### Gaussian Splat Warping ⚠️ ISSUES
- Works in Python (live_tryon_demo.py) but with artifacts
- Issues: floating clothing, incorrect joint bending, jitter
- Not yet ported to web
- Uses different algorithms than proven polygon approach

---

## Proposed Implementation Plan

### Phase 1: Fix Gaussian Python Pipeline (7-11 hours) ⭐ CRITICAL

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | Align bone definitions to polygon's 9 bones | Not Started |
| 1.2 | Add Y-flip coordinate transform | Not Started |
| 1.3 | Improve weight assignment (use body mesh or tune sigmas) | Not Started |
| 1.4 | Add SLERP temporal smoothing | Not Started |

### Phase 2: Web Portability (9-12 hours)

| Task | Description | Status |
|------|-------------|--------|
| 2.1 | Create GaussianMesh adapter (splats → InstancedMesh) | Not Started |
| 2.2 | Reuse SkeletalAnimator + SkinWeightTransfer pattern | Not Started |
| 2.3 | Integrate with existing UI | Not Started |

### Phase 3: Optimization (Optional, 8-10 hours)

| Task | Description | Status |
|------|-------------|--------|
| 3.1 | GPU DQS animation in WebGL compute shader | Not Started |

---

## Key Files Reference

### Polygon (Working - Learn From These)
```
static/js/SkinWeightTransfer.js      # BVH + barycentric weight transfer
static/js/SkeletalAnimator.js        # Bone updates with SLERP
static/js/MeshAligner.js             # Coordinate space alignment
src/ui/bone_rotation_calculator.py   # 9-bone quaternion computation
src/ui/mesh_calibrator.py            # Body calibration
```

### Gaussian (Fix These)
```
gaussian_test/gaussian_animator.py         # DQS animation - needs coord transform
gaussian_test/gaussian_weight_assigner.py  # Weight assignment - needs improvement
gaussian_test/gaussian_tryon_pipeline.py   # Orchestrator
gaussian_test/live_tryon_demo.py           # Live demo for testing
```

---

## Critical Code Differences

### Weight Assignment

**Polygon (CORRECT):**
```javascript
// Uses body mesh surface + barycentric interpolation
bodyBVH.closestPointToPoint(clothingVertex, target);
const barycentric = computeBarycentric(target.point, tri.a, tri.b, tri.c);
weights = interpolate(bodyMesh.skinWeights, triIndices, barycentric);
```

**Gaussian (NEEDS FIX):**
```python
# Uses distance to bone segment - ignores body surface
distances = point_to_segment_distance(splat_positions, p0, p1)
weights = exp(-(distances / sigma)²)
```

### Coordinate Transform

**Polygon (CORRECT):**
```python
def _transform_to_threejs(self, quat):
    return {
        'x': float(-quat['x']),  # Negate X
        'y': float(quat['y']),
        'z': float(-quat['z']),  # Negate Z
        'w': float(quat['w'])
    }
```

**Gaussian (MISSING):** No equivalent transform exists.

### Temporal Smoothing

**Polygon (CORRECT):**
```javascript
bone.quaternion.slerp(finalQuat, this.options.lerpSpeed);
```

**Gaussian (MISSING):** No SLERP smoothing.

---

## Open Questions (Need User Input)

1. **Weight Assignment Strategy:**
   - **Option A:** Use pre-rigged body mesh (like polygon) - best quality
   - **Option B:** Tune sigma values empirically - faster implementation

2. **Priority:**
   - Phase 1 only (fix Python)?
   - Phases 1+2 (Python + web port)?

3. **Testing:**
   - Which specific clothing item/test case to use for validation?

---

## Prompt to Continue Next Session

```
Continue working on the Gaussian splat warping fixes for Spoken Wardrobe.

## Context
- We completed analysis comparing polygon mesh warping (working) vs Gaussian splat warping (issues)
- Full analysis documented in: docs/250326_gaussian_vs_polygon_analysis.md
- Identified 4 critical issues in Gaussian version

## Critical Issues to Fix
1. Weight assignment uses bone distance instead of body mesh surface
2. Bone definitions: Gaussian has 12 bones, polygon has 9 (different landmark pairs)
3. Missing coordinate transform (BlazePose Y-DOWN → rendering Y-UP)
4. No temporal smoothing (SLERP)

## Files to Modify
- gaussian_test/gaussian_weight_assigner.py - Fix weight assignment
- gaussian_test/gaussian_animator.py - Add coord transform + smoothing
- gaussian_test/gaussian_tryon_pipeline.py - Align bone definitions

## Reference Files (Working Polygon Implementation)
- static/js/SkinWeightTransfer.js - BVH weight transfer
- static/js/SkeletalAnimator.js - SLERP smoothing
- src/ui/bone_rotation_calculator.py - 9-bone definitions + Y-flip

## Proposed Plan
Phase 1: Fix Python Gaussian (7-11 hours)
Phase 2: Port to Web (9-12 hours)
Phase 3: GPU Optimization (optional, 8-10 hours)

## Questions to Resolve First
1. Weight assignment: Use body mesh (Option A) or tune sigmas (Option B)?
2. Priority: Phase 1 only or Phases 1+2?
3. Test case: Which clothing item for validation?

Please start by reviewing the analysis document and implementing Phase 1 fixes.
```

---

## Session Metadata

- **Date:** 2025-03-26
- **Branch:** `gaussian-exploration`
- **Last Commit:** `05bbfab` - "gaussian splatting close to working overlay body mapped"
- **Analysis Complete:** ✅
- **Implementation Started:** ❌

---

## Next Steps

1. User approves plan and answers questions
2. Begin Phase 1 implementation
3. Test with live_tryon_demo.py
4. Iterate until Gaussian matches polygon quality
5. Consider Phase 2 (web port) if Phase 1 successful
