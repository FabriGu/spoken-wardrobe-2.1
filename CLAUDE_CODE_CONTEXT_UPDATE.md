# Claude Code Context Update - MediaPipe Mesh Deformation System

## Overview
This document summarizes all changes made to fix the MediaPipe-to-body-mesh deformation system in the Spoken Wardrobe project.

---

## 1. Coordinate Transform Fix

**Problem:** Mesh tilted opposite to MediaPipe keypoints (forward tilt → backward mesh).

**Root Cause:** Keypoint visualization used `(-x, -y, -z)` transform but skeleton used `(-x, -y, z)` - the Z axis was inconsistent.

**Fix:** Changed `vec()` function to negate all three axes: `(-x, -y, -z)`

**Location:** `static/js/MediaPipePoseDriver.js`, lines 682-686

---

## 2. Side Mapping Fix (Mirrored Webcam)

**Problem:** User's left arm controlled mesh right arm and vice versa.

**Root Cause:** Webcam feed is mirrored (like looking in a mirror), so MediaPipe's "left" corresponds to user's "right" side.

**Fix:** Swapped landmark indices in arm updates:
- User's LEFT arm ← MediaPipe RIGHT landmarks (lines 737, 742)
- User's RIGHT arm ← MediaPipe LEFT landmarks (lines 748, 753)

**Location:** `static/js/MediaPipePoseDriver.js`, lines 721-755

---

## 3. Visibility Threshold Feature

**Feature:** Prevent mesh updates when MediaPipe confidence is low.

**Configuration:** 
```javascript
this.visibilityThreshold = 0.98;  // Line 46
```

**Behavior:** 
- Each joint must have visibility ≥ 0.98 (98%) to affect mesh
- If any joint in a limb is below threshold, that limb doesn't update
- Mesh maintains last known good pose

**Adjustable Range:** 0.0 (no filtering) to 1.0 (perfect visibility required)

**Location:** `static/js/MediaPipePoseDriver.js`, lines 46, 691-696, 702-858

---

## 4. Position Alignment Fix

**Problem:** Mesh followed keypoint orientation but was offset in position (lower/inward).

**Root Cause:** Keypoint visualization applied manual offsets (`manualOffsetY = -0.25`, `manualOffsetZ = 0.1`) but skeleton only rotated without translating.

**Fix:** Added position translation to spine bone using the same transform as keypoint visualization.

**Adjustable Controls:**
```javascript
this.manualOffsetY = -0.25;  // Line 73 - Shift down/up
this.manualOffsetZ = 0.1;    // Line 74 - Shift forward/back
```

**Location:** `static/js/MediaPipePoseDriver.js`, lines 730-765

---

## 5. Debug Visualization

**Feature:** Arrow helpers showing arm directions and rest axes.

**Toggle:** Check "Show Debug Arrows" in diagnostic HTML or set `poseDriver.setDebugArrowsVisible(true)`

**Location:** `static/js/MediaPipePoseDriver.js`, lines 54-57, 379-444, 769-836

---

## Key Configuration Points

| Setting | Location | Default | Description |
|---------|----------|---------|-------------|
| `visibilityThreshold` | Line 46 | 0.98 | Min confidence for joint tracking |
| `manualOffsetY` | Line 73 | -0.25 | Vertical offset for alignment |
| `manualOffsetZ` | Line 74 | 0.1 | Depth offset for alignment |
| `smoothingFactor` | Line 40 | 0.3 | Rotation smoothing (0=instant, 1=no change) |

---

## Coordinate System Reference

**MediaPipe World Landmarks:**
- X+ = person's LEFT
- Y+ = DOWN
- Z+ = toward camera

**Three.js Scene (after `vec()` transform):**
- X+ = viewer's LEFT (character's left, mirrored)
- Y+ = UP
- Z+ = toward viewer

**Transform:** `vec = (-x, -y, -z)`

---

## Bone Mapping (with mirrored webcam correction)

| Mesh Bone | MediaPipe Landmarks | Rest Axis |
|-----------|---------------------|-----------|
| leftUpperArm | rightShoulder → rightElbow | (1, 0, 0) |
| leftLowerArm | rightElbow → rightWrist | (1, 0, 0) |
| rightUpperArm | leftShoulder → leftElbow | (-1, 0, 0) |
| rightLowerArm | leftElbow → leftWrist | (-1, 0, 0) |
| spine | left/right Shoulder/Hip centers | (0, 1, 0) |

---

## Related Documentation Files

1. `MEDIAPIPE_MESH_DEFORMATION_FIX_SUMMARY.md` - Coordinate transform fix details
2. `VISIBILITY_THRESHOLD_SUMMARY.md` - Visibility threshold feature guide
3. `MESH_POSITION_ALIGNMENT_FIX.md` - Position alignment fix details
4. `MIGHTY_HATCHING_KURZWEIL.md` (in .claude/plans/) - Original implementation plan

---

## Testing Checklist

- [ ] Tilt forward → mesh tilts forward
- [ ] Raise left arm → mesh left arm raises
- [ ] Raise right arm → mesh right arm raises
- [ ] Arm positions align with purple keypoints
- [ ] Moving arm out of camera view → arm stops updating (if visibility threshold enabled)
- [ ] Debug arrows show correct directions
