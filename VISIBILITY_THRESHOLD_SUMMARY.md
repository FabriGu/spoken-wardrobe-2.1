# Visibility Threshold Feature - Summary

## What Was Added

A **visibility threshold** that prevents the mesh from updating when MediaPipe's confidence in joint detection is too low.

## Where to Change the Threshold

**File:** `static/js/MediaPipePoseDriver.js`  
**Line:** 46 (in the constructor)

```javascript
// Visibility threshold for joint tracking (0.0 - 1.0)
// Joints with visibility below this value will not affect the mesh
// CHANGE THIS VALUE to adjust sensitivity (higher = more strict, lower = more permissive)
this.visibilityThreshold = 0.98;
```

### Threshold Values Guide

| Value | Behavior |
|-------|----------|
| `0.98` | Very strict - only updates when MediaPipe is 98%+ confident (DEFAULT) |
| `0.90` | Strict - allows slightly more occlusion/noise |
| `0.75` | Moderate - balances stability and responsiveness |
| `0.50` | Permissive - updates even with low confidence |
| `0.00` | No filtering - always updates (not recommended) |

## How It Works

1. **Before each bone rotation**, the code checks if the required landmarks are visible:
   ```javascript
   if (this.boneMap.leftUpperArm && allVisible(L.rightShoulder, L.rightElbow)) {
       // Only update if both shoulder AND elbow are visible
   }
   ```

2. **If any joint in a limb is below the threshold**, the entire limb segment doesn't update
   - This prevents partial/incomplete poses from affecting the mesh
   - The mesh maintains its last known good pose until visibility improves

3. **Applied to all body parts:**
   - Spine (requires all 4 shoulder/hip joints)
   - Arms (requires shoulder + elbow, elbow + wrist)
   - Legs (requires hip + knee, knee + ankle)

## Files Modified

- `static/js/MediaPipePoseDriver.js`
  - Added `this.visibilityThreshold = 0.98` property (line 46)
  - Added `isVisible()` helper function (line 691)
  - Added `allVisible()` helper function (line 696)
  - Added visibility checks to spine update (line 702)
  - Added visibility checks to arm updates (lines 737, 742, 748, 753)
  - Added visibility checks to leg updates (lines 842, 847, 853, 858)

## Quick Test

1. Set threshold to `0.98` (strict)
2. Move one arm out of camera view
3. The hidden arm should stop moving while the visible arm continues tracking
4. Lower threshold to `0.50` and test again - the arm should track even when partially occluded
