# Three.js Mesh Debugging Guide

This document contains debugging code to diagnose why 3D meshes may not be rendering in the Spoken Wardrobe UI.

## Problem Context

Despite console logs showing successful mesh loading:
- `mesh_ready received! Size: 9682.6 KB`
- `GLB parsed successfully`
- `Mesh visible: true`
- `Canvas dimensions: 2122 x 3840`

The mesh does NOT appear visually on screen.

## Possible Failure Points

| # | Issue | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Canvas hidden by CSS | HIGH | Browser DevTools inspect `#three-canvas` |
| 2 | Canvas 0x0 size | MEDIUM | Check `canvas.width` and `canvas.height` |
| 3 | Mesh outside camera view | MEDIUM | Add debug cube at (0,0,0) |
| 4 | WebGL context invalid | LOW | Add background color test |
| 5 | z-index class not applied | MEDIUM | Check body classList |
| 6 | State overlay covers canvas | HIGH | Check state screen background |

---

## Debug Code to Add

### 1. three_scene.js - Add in `init()` after lighting setup

```javascript
// DEBUG: Add a cube at origin to verify scene renders
const debugGeometry = new THREE.BoxGeometry(0.3, 0.3, 0.3);
const debugMaterial = new THREE.MeshStandardMaterial({ color: 0xff0000 });
this.debugCube = new THREE.Mesh(debugGeometry, debugMaterial);
this.debugCube.position.set(0, 0, 0);
this.scene.add(this.debugCube);
console.log('[ThreeScene] DEBUG: Added red cube at origin');

// DEBUG: Force semi-transparent red background to verify canvas is visible
this.renderer.setClearColor(0xff0000, 0.3);

// DEBUG: Log canvas computed styles
const computedStyle = window.getComputedStyle(this.canvas);
console.log('[ThreeScene] DEBUG Canvas visibility:', {
    display: computedStyle.display,
    visibility: computedStyle.visibility,
    opacity: computedStyle.opacity,
    zIndex: computedStyle.zIndex,
    width: computedStyle.width,
    height: computedStyle.height,
    position: computedStyle.position
});
```

### 2. three_scene.js - Add in `animate()` at the start

```javascript
// DEBUG: Rotate the debug cube to verify animation loop is running
if (this.debugCube) {
    this.debugCube.rotation.y += 0.01;
}

// DEBUG: Log canvas size once
if (!this._loggedCanvasOnce) {
    console.log('[ThreeScene] DEBUG animate() running, canvas size:',
        this.canvas.width, 'x', this.canvas.height);
    console.log('[ThreeScene] DEBUG renderer size:',
        this.renderer.domElement.width, 'x', this.renderer.domElement.height);
    console.log('[ThreeScene] DEBUG camera position:', this.camera.position);
    this._loggedCanvasOnce = true;
}
```

### 3. three_scene.js - Add at end of `loadMeshFromBase64()`

```javascript
// DEBUG: Log camera and mesh world positions
console.log('[ThreeScene] DEBUG Camera position:', this.camera.position);
console.log('[ThreeScene] DEBUG Mesh world position:', this.clothingMesh.position);
console.log('[ThreeScene] DEBUG Mesh bounds:', { size, center });

// Check if mesh is in camera frustum
this.camera.updateMatrixWorld();
const frustum = new THREE.Frustum();
frustum.setFromProjectionMatrix(
    new THREE.Matrix4().multiplyMatrices(
        this.camera.projectionMatrix,
        this.camera.matrixWorldInverse
    )
);
const meshCenter = new THREE.Vector3();
new THREE.Box3().setFromObject(this.clothingMesh).getCenter(meshCenter);
const inFrustum = frustum.containsPoint(meshCenter);
console.log('[ThreeScene] DEBUG Mesh center in camera frustum:', inFrustum, 'at', meshCenter);
```

### 4. state_manager.js - Add after body class toggle

```javascript
// DEBUG: Log body classes
console.log('[StateManager] DEBUG Body classes after toggle:',
    document.body.className,
    'State:', normalizedState);
```

### 5. app.js - Add in onStateChange handler

```javascript
// DEBUG: Check z-index after state transition
setTimeout(() => {
    const canvasContainer = document.getElementById('canvas-container');
    const uiOverlay = document.getElementById('ui-overlay');
    const threeCanvas = document.getElementById('three-canvas');
    console.log('[App] DEBUG z-index check:', {
        bodyClasses: document.body.className,
        canvasContainerZ: window.getComputedStyle(canvasContainer).zIndex,
        uiOverlayZ: window.getComputedStyle(uiOverlay).zIndex,
        threeCanvasDisplay: window.getComputedStyle(threeCanvas).display,
        threeCanvasOpacity: window.getComputedStyle(threeCanvas).opacity,
        threeCanvasWidth: window.getComputedStyle(threeCanvas).width,
        threeCanvasHeight: window.getComputedStyle(threeCanvas).height
    });
}, 100);
```

---

## What to Look For When Testing

1. **Red tint on screen** → Canvas is visible, Three.js is rendering
2. **Spinning red cube** → Camera and scene are working correctly
3. **`DEBUG Canvas visibility`** → Check display/opacity/z-index values
4. **`DEBUG Body classes after toggle`** → Should show `calibrating-active` during CALIBRATING
5. **`DEBUG z-index check`** → Should show canvasContainerZ: "15" during CALIBRATING/TRY_ON
6. **`DEBUG Mesh center in camera frustum: true`** → Mesh is within camera view

---

## Interpretation

| Symptom | Diagnosis |
|---------|-----------|
| No red tint, no cube | Canvas is hidden by CSS or not rendering |
| Red tint but no cube | WebGL issue or camera pointing wrong direction |
| Cube visible but no mesh | Mesh loading issue or mesh positioned outside view |
| Everything works except mesh | Check mesh material, texture, or scale issues |

---

## Removal

After debugging, remove all code blocks marked with `// DEBUG:` and:
- Delete `debugCube` creation and rotation
- Revert `setClearColor(0xff0000, 0.3)` to `setClearColor(0x000000, 0)`
- Remove all console.log statements containing `DEBUG`
- Remove `_loggedCanvasOnce` flag
