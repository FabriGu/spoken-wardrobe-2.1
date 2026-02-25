# Claude Code Context Update - MediaPipe Mesh Deformation System (Final)

## Project Overview
Real-time body mesh deformation driven by MediaPipe pose detection for the Spoken Wardrobe interactive installation.

---

## System Architecture

### Key Components
1. **MediaPipePoseDriver.js** - Main driver that processes landmarks and drives skeleton
2. **three_scene.js** - Three.js scene management, body mesh loading
3. **SkeletalAnimator.js** - Alternative bone rotation system (not currently used)
4. **BodyMeshRestPoseFix.js** - Rest pose handling for weight transfer

### Data Flow
```
Webcam → MediaPipe → Landmarks → vec() transform → Bone rotations → Mesh deformation
```

---

## Critical Configuration Points

### 1. Z Offset for Keypoint Visualization
**File:** `static/js/MediaPipePoseDriver.js`  
**Line:** 74

```javascript
this.manualOffsetZ = -0.25;  // Z offset for keypoint visualization (negative = closer to camera)
```

**Purpose:** Shifts the purple keypoint spheres forward/backward in the scene.  
**Negative** = closer to camera (toward viewer), **Positive** = further from camera.

### 2. Y Offset for Keypoint Visualization
**File:** `static/js/MediaPipePoseDriver.js`  
**Line:** 73

```javascript
this.manualOffsetY = -0.25;  // Shift down (negative) or up (positive)
```

### 3. Visibility Threshold
**File:** `static/js/MediaPipePoseDriver.js`  
**Line:** 46

```javascript
this.visibilityThreshold = 0.98;  // 0.0 to 1.0 (higher = more strict)
```

### 4. Smoothing Factor
**File:** `static/js/MediaPipePoseDriver.js`  
**Line:** 40

```javascript
this.smoothingFactor = 0.3;  // 0.0 = instant, 1.0 = no change
```

---

## Coordinate System (CRITICAL)

### MediaPipe World Landmarks
- X+ = person's LEFT
- Y+ = DOWN
- Z+ = toward camera

### Three.js Scene
- X+ = viewer's RIGHT (character's left)
- Y+ = UP
- Z+ = toward viewer

### Transform Function vec()
**Location:** Lines 667-686 in MediaPipePoseDriver.js

```javascript
const vec = (idx) => new THREE.Vector3(
    -landmarks[idx].x,   // Mirror X (person's left → viewer's left)
    -landmarks[idx].y,   // Flip Y (MediaPipe down → Three.js up)
    landmarks[idx].z     // Keep Z (both point toward camera/viewer)
);
```

**Why Z is NOT negated:** MediaPipe Z+ (toward camera) and Three.js Z+ (toward viewer) are the SAME direction. Negating Z would invert forward/backward motion.

---

## Bone Mapping (Mirrored Webcam Correction)

The webcam is mirrored (like looking in a mirror), so MediaPipe's "left" corresponds to the user's RIGHT side.

| User's Body Part | MediaPipe Landmarks | Mesh Bone | Rest Axis |
|------------------|---------------------|-----------|-----------|
| Left arm | RIGHT (shoulder→elbow→wrist) | leftUpperArm/leftLowerArm | (1, 0, 0) |
| Right arm | LEFT (shoulder→elbow→wrist) | rightUpperArm/rightLowerArm | (-1, 0, 0) |
| Left leg | LEFT (hip→knee→ankle) | leftUpperLeg/leftLowerLeg | (0, -1, 0) |
| Right leg | RIGHT (hip→knee→ankle) | rightUpperLeg/rightLowerLeg | (0, -1, 0) |
| Spine | Both shoulders + both hips | spine | (0, 1, 0) |

**Location:** Lines 745-766 in MediaPipePoseDriver.js

---

## Visibility System

Each bone update checks if required landmarks are visible enough:

```javascript
// Example: Left upper arm requires right shoulder AND right elbow
if (this.boneMap.leftUpperArm && allVisible(L.rightShoulder, L.rightElbow)) {
    // Update bone
}
```

**Visibility threshold** (0.98 = 98% confidence) is checked against each landmark's `visibility` property from MediaPipe.

---

## Key Methods

### _updateSkeleton(landmarks)
**Location:** Lines 654-870  
Main update loop that:
1. Transforms landmarks using `vec()`
2. Computes bone rotations from directions
3. Applies visibility checks
4. Updates bone quaternions with smoothing

### _applyRotation(bone, targetQuat, debugName)
**Location:** Lines 873-890  
Applies rotation to bone with:
- Rest pose preservation (stores restQuaternion)
- Smooth interpolation (slerp with smoothingFactor)

### computeRotation(fromIdx, toIdx, restAxis, debugLabel)
**Helper inside _updateSkeleton**  
Computes quaternion rotation from rest axis to target direction.

---

## Debug Features

### Debug Arrows
Toggle with checkbox in diagnostic HTML or:
```javascript
poseDriver.setDebugArrowsVisible(true);
```

Shows:
- Green arrow: Left arm direction
- Blue arrow: Right arm direction
- Red arrow: Left rest axis
- Cyan arrow: Right rest axis

### Console Logging
Set `this._debugLogged = false` to re-enable one-time debug logs on next tracking start.

---

## Common Issues & Solutions

### Forward/Backward Inverted
**Cause:** Z was being negated in vec()  
**Fix:** Keep Z as-is: `vec = (-x, -y, z)`

### Left/Right Crossed
**Cause:** Not accounting for mirrored webcam  
**Fix:** Swap landmark indices (user's left ← MediaPipe right)

### Mesh Offset from Keypoints
**Cause:** manualOffsetY/Z not applied to skeleton position  
**Current behavior:** Only affects keypoint visualization, not mesh (by design)

### Low Confidence Tracking
**Cause:** Visibility threshold too high  
**Fix:** Lower `visibilityThreshold` (e.g., 0.90 or 0.75)

---

## Files Modified During Development

1. `static/js/MediaPipePoseDriver.js` - Main driver (coordinate transforms, bone mapping, visibility checks)
2. `static/mediapipe_diagnostic.html` - Added debug arrows checkbox

---

## Testing Checklist

- [ ] Tilt forward → mesh tilts forward
- [ ] Tilt backward → mesh tilts backward
- [ ] Raise left arm → mesh left arm raises
- [ ] Raise right arm → mesh right arm raises
- [ ] Move arm left/right → mesh follows correctly
- [ ] Purple keypoints align with body position
- [ ] Moving arm out of view → arm stops updating (visibility threshold)

---

## Related Documentation

- `MEDIAPIPE_MESH_DEFORMATION_FIX_SUMMARY.md` - Coordinate transform history
- `VISIBILITY_THRESHOLD_SUMMARY.md` - Visibility system details
- `MIGHTY_HATCHING_KURZWEIL.md` - Original implementation plan (in .claude/plans/)

---

## Last Updated
2026-02-25
