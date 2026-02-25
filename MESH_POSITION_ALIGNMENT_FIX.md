# Mesh Position Alignment Fix - Summary

## Problem
The mesh arm followed the orientation of MediaPipe keypoints but was consistently offset in position (lower and further inward). The purple keypoint spheres and mesh arms didn't align.

## Root Cause
The keypoint visualization applied manual offsets (`manualOffsetY = -0.25`, `manualOffsetZ = 0.1`) to position the purple spheres, but the skeleton only applied **rotations** to bones. The mesh stayed at its original rest pose positions while keypoints were shifted.

## The Fix
Added **position translation** to the spine bone so the entire skeleton shifts to match the keypoint offsets.

### Where the Offset is Controlled

**File:** `static/js/MediaPipePoseDriver.js`
**Lines:** 73-75

```javascript
this.manualOffsetY = -0.25;  // Shift down (negative) or up (positive)
this.manualOffsetZ = 0.1;    // Shift forward (positive) or back (negative)
```

### How to Adjust

If the mesh still appears offset from keypoints:

1. **Mesh too low** (below keypoints): Increase `manualOffsetY` (less negative)
2. **Mesh too high** (above keypoints): Decrease `manualOffsetY` (more negative)
3. **Mesh too far back**: Increase `manualOffsetZ`
4. **Mesh too far forward**: Decrease `manualOffsetZ`

### Implementation Details

The position alignment (lines 730-765 in `_updateSkeleton`):

1. Calculate spine center from shoulder/hip landmarks (same as before)
2. Apply the **same transform** used for keypoint visualization:
   ```javascript
   const scale = this.keypointScale * this.manualScaleMultiplier;
   const offsetX = this.keypointOffsetX;
   const offsetY = this.keypointOffsetY + this.manualOffsetY;
   const offsetZ = this.keypointOffsetZ + this.manualOffsetZ;
   
   const targetSpineScenePos = new THREE.Vector3(
       spineCenterMP.x * scale + offsetX,
       spineCenterMP.y * scale + offsetY,
       spineCenterMP.z * scale + offsetZ
   );
   ```
3. Convert target position to spine bone's local space
4. Apply with smoothing: `spineBone.position.lerp(targetLocal, this.smoothingFactor)`

## Files Modified

- `static/js/MediaPipePoseDriver.js`
  - Added position translation to spine update (lines 730-765)
  - Added comments explaining manual offset controls (lines 73-75)

## Testing

1. Start MediaPipe tracking
2. Raise your arm
3. The mesh arm should now align with the purple keypoint spheres
4. If offset persists, adjust `manualOffsetY` and `manualOffsetZ` values

## Important Note

The `manualOffsetY` and `manualOffsetZ` values affect **both** keypoint visualization AND mesh position. Changing them will shift both together, maintaining alignment.
