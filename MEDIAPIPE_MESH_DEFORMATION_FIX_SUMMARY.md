# MediaPipe to Body Mesh Deformation Fix - Summary

## Problem Statement
The body mesh deformation was inverted relative to MediaPipe tracking data:
- When user tilted forward → mesh tilted backward
- When user raised arms up → mesh arms moved down
- Mesh was NOT upside down (Z-axis rotation was correct)

## Root Cause Analysis

### The Key Insight
The **keypoint visualization** and **skeleton deformation** were using **different coordinate transforms**:

**Keypoint visualization** (`_updateKeypointVisualization`, lines 746-749):
```javascript
const scenePos = (lm) => new THREE.Vector3(
    -lm.x * scale + offsetX,   // -X
    -lm.y * scale + offsetY,   // -Y  
    -lm.z * scale + offsetZ    // -Z  <-- Z is negated!
);
```

**Original skeleton vec() function** (before fix):
```javascript
const vec = (idx) => new THREE.Vector3(
    -landmarks[idx].x,   // -X
    -landmarks[idx].y,   // -Y
    landmarks[idx].z     // +Z  <-- Z was NOT negated! BUG!
);
```

### Why This Caused Inversion

When user tilts forward (toward camera):
1. MediaPipe reports shoulders at **+Z** (closer to camera than hips)
2. Keypoints visualize at **-Z** (in scene, toward viewer)
3. Skeleton computed spineDir with **+Z** (no negation)
4. Result: mesh tilts **opposite** to keypoint visualization

### Coordinate System Details

| System | X+ | Y+ | Z+ |
|--------|----|----|----|
| MediaPipe | person's left | DOWN | toward camera |
| Three.js (scene) | viewer's right | UP | toward viewer |

The transform `(-x, -y, -z)` maps MediaPipe to scene space:
- X: person's left (+X) → viewer's left (-X) ✓ mirror
- Y: down (+Y) → up (-Y) ✓ flip
- Z: toward camera (+Z) → toward viewer (-Z) ✓ both point at viewer

## The Fix

### 1. Updated vec() Function (line 675-679)
```javascript
const vec = (idx) => new THREE.Vector3(
    -landmarks[idx].x,   // Mirror X for display
    -landmarks[idx].y,   // Flip Y (MediaPipe Y is down)
    -landmarks[idx].z    // Flip Z to match keypoint visualization
);
```

### 2. Rest Axes (Already Correct)
The arm rest axes were already correct for the negated coordinate system:
- Left arm: `(-1, 0, 0)` - matches negated MediaPipe +X
- Right arm: `(1, 0, 0)` - matches negated MediaPipe -X

No changes needed to rest axes.

## Files Modified

- `static/js/MediaPipePoseDriver.js`
  - Updated `vec()` function to negate Z (line 678)
  - Updated comments explaining the coordinate transform (lines 661-679)
  - Updated arm rest axes comments (lines 711-716)

## Verification Steps

1. Open the diagnostic page with body mesh loaded
2. Enable "Show 3D Keypoints" to see purple keypoints
3. Start MediaPipe tracking
4. Test movements:
   - **Tilt forward**: Both keypoints and mesh should tilt toward camera
   - **Raise arms**: Both keypoints and mesh arms should raise up
   - **T-pose**: Mesh arms should align with keypoint positions

## Key Lesson

**Always keep coordinate transforms consistent between visualization and deformation.**

The keypoint visualization was the "source of truth" for what appears correct in the scene. The skeleton deformation must use the identical transform to ensure the mesh follows what the user sees.

## Related Code Sections

- Keypoint visualization transform: lines 746-749
- Skeleton vec() function: lines 675-679
- Arm rotation rest axes: lines 717-735
- Spine rotation: lines 690-709
- Debug arrows (uses same transform): lines 752-760
