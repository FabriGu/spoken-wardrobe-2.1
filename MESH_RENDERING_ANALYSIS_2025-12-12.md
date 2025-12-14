# Mesh Rendering Analysis - December 12, 2025

## Problem Statement

The 3D clothing mesh is not rendering visually in the Spoken Wardrobe application, despite console logs showing successful loading:
- `mesh_ready received! Size: 9682.6 KB`
- `GLB parsed successfully`
- `Mesh visible: true`
- `Canvas dimensions: 2122 x 3840`

---

## Step 1: Previous Fixes Attempted (All Failed)

| Fix Attempted | Result |
|--------------|--------|
| Changed `calibrate()` to `calibrate_offset()` | Fixed crash, but mesh still invisible |
| Added `resetToCenter()` method | No visual change |
| Changed camera z from 3 → 2 | No visual change |
| Changed targetSize from 1.5 → 3.0 → 2.2 | No visual change |
| Added CSS z-index rules for CALIBRATING state | No visual change |
| Added body class toggle for `calibrating-active` | No visual change |

**Conclusion**: The issue is NOT simple positioning or z-index. Something more fundamental is wrong.

---

## Step 2: Current Implementation Analysis

### File: `static/js/three_scene.js`

```javascript
// Current Camera Settings
this.camera = new THREE.PerspectiveCamera(
    75,                                    // FOV: 75°
    window.innerWidth / window.innerHeight,
    0.1,
    1000
);
this.camera.position.z = 2;               // Distance: 2 units

// Current Lighting (only 2 lights)
const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
directionalLight.position.set(0, 1, 2);

// Current Renderer (missing encoding/tone mapping)
this.renderer = new THREE.WebGLRenderer({
    canvas: this.canvas,
    antialias: true,
    alpha: true
});
this.renderer.setClearColor(0x000000, 0);  // No sRGB, no tone mapping

// Current Mesh Centering (manual calculation)
this.clothingMesh.position.x = -center.x * scaleFactor;
this.clothingMesh.position.y = -center.y * scaleFactor;
this.clothingMesh.position.z = 0;
const targetSize = 2.2;
```

---

## Step 3: Working Implementation Analysis

### File: `spoken-wardrobe-2/tests/rodin_mesh_viewer.html`

```javascript
// Working Camera Settings
camera = new THREE.PerspectiveCamera(
    50,                                    // FOV: 50° (narrower = larger objects)
    window.innerWidth / window.innerHeight,
    0.01,
    100
);
camera.position.set(0, 0, 2.5);           // Distance: 2.5 units

// Working Lighting (4 lights for PBR)
ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.5);  // SKY/GROUND
directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
directionalLight.position.set(2, 2, 1);
secondaryLight = new THREE.DirectionalLight(0xffffff, 0.4);
secondaryLight.position.set(-1, 1, -1);

// Working Renderer (with proper encoding)
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

// Working Mesh Centering (subtract center vector)
const box = new THREE.Box3().setFromObject(loadedMesh);
const center = box.getCenter(new THREE.Vector3());
loadedMesh.position.sub(center);          // KEY: Direct vector subtraction
const maxDim = Math.max(size.x, size.y, size.z);
const scale = 1.5 / maxDim;               // Target: 1.5 units
loadedMesh.scale.multiplyScalar(scale);
```

---

## Step 4: Critical Differences

| Aspect | Working Version | Current Version | Impact |
|--------|-----------------|-----------------|--------|
| **Camera FOV** | 50° | 75° | 75° makes objects appear much smaller |
| **Camera Z** | 2.5 | 2 | Closer but with wider FOV = smaller objects |
| **Near Plane** | 0.01 | 0.1 | Current may clip close objects |
| **Far Plane** | 100 | 1000 | Minor impact |
| **Ambient Light** | 0.6 | 0.6 | Same |
| **Hemisphere Light** | YES (0.5) | NO | Missing sky/ground gradient |
| **Directional Light** | 1.0 at (2,2,1) | 0.8 at (0,1,2) | Lower intensity, different angle |
| **Secondary Light** | YES (0.4) | NO | Missing fill light |
| **sRGB Encoding** | YES | NO | Colors may appear wrong |
| **Tone Mapping** | ACES Filmic | NO | PBR materials may render black |
| **Centering Method** | `position.sub(center)` | Manual calculation | Potential math error |
| **Target Scale** | 1.5 | 2.2 | Different sizing |

---

## Step 5: Root Cause Hypothesis

### Most Likely Cause: Missing Tone Mapping + sRGB Encoding

PBR (Physically Based Rendering) materials from Rodin API expect:
1. **sRGB color encoding** for correct color interpretation
2. **Tone mapping** to map HDR values to displayable range

Without these, PBR materials can render as:
- Completely black (values out of range)
- Extremely dark (incorrect gamma)
- Wrong colors (linear vs sRGB mismatch)

### Secondary Cause: Insufficient Lighting

PBR materials require multiple light sources to render properly:
- **Ambient**: Base illumination
- **Hemisphere**: Sky/ground gradient for natural look
- **Directional**: Main light source with shadows
- **Fill light**: Reduces harsh shadows

With only 2 lights (current), dark areas of the mesh may be completely black.

### Third Cause: Camera FOV Mismatch

FOV 75° vs 50° significantly affects perceived object size:
- At 75° FOV, objects appear ~33% smaller
- Combined with distance changes, mesh may be much smaller than expected

---

## Step 6: Recommended Fix

### Phase 1: Renderer Setup (Critical)

```javascript
// Add after renderer creation
this.renderer.outputEncoding = THREE.sRGBEncoding;
this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
this.renderer.toneMappingExposure = 1.0;
```

### Phase 2: Camera Settings

```javascript
// Change camera initialization
this.camera = new THREE.PerspectiveCamera(
    50,                                    // Narrower FOV
    window.innerWidth / window.innerHeight,
    0.01,                                  // Closer near plane
    100                                    // Reasonable far plane
);
this.camera.position.set(0, 0, 2.5);      // Slightly further back
```

### Phase 3: Enhanced Lighting

```javascript
// Replace current lighting with:
const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
this.scene.add(ambientLight);

const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.5);
this.scene.add(hemisphereLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
directionalLight.position.set(2, 2, 1);
this.scene.add(directionalLight);

const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
fillLight.position.set(-1, 1, -1);
this.scene.add(fillLight);
```

### Phase 4: Mesh Centering (Simplified)

```javascript
// In loadMeshFromBase64, after calculating box/center/size:
this.clothingMesh.position.sub(center);   // Direct subtraction
const maxDim = Math.max(size.x, size.y, size.z);
const scale = 1.5 / maxDim;
this.clothingMesh.scale.multiplyScalar(scale);
```

---

## Step 7: Verification Checklist

After implementing fixes, verify:

1. [ ] Red debug cube appears at origin (add temporarily)
2. [ ] Canvas has semi-transparent background (add temporarily)
3. [ ] Console shows "Mesh center in camera frustum: true"
4. [ ] Mesh appears on screen during CALIBRATING state
5. [ ] Mesh responds to body tracking during TRY_ON state

---

## Additional Notes

### Test Files Available

The working version includes test HTML files that can be opened directly:
- `spoken-wardrobe-2/tests/rodin_mesh_viewer.html` - Best reference
- Can be used to test GLB files independently

### CSS Z-Index (Already Correct)

```css
body.calibrating-active #canvas-container,
body.try-on-active #canvas-container {
    z-index: 15;
}
```

The CSS appears correct. The issue is in Three.js rendering, not CSS visibility.

---

## Summary

The mesh is loading correctly but not rendering due to:

1. **Missing sRGB encoding and tone mapping** (CRITICAL)
2. **Insufficient lighting for PBR materials** (HIGH)
3. **Wrong camera FOV making mesh appear too small** (MEDIUM)
4. **Different centering approach** (LOW)

Fix priority: Renderer settings > Lighting > Camera > Centering
