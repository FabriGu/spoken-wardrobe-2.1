/**
 * ThreeScene Diagnostic Patch
 * 
 * This file contains modifications to apply to three_scene.js for diagnostic purposes.
 * Apply these changes manually or use the diagnostic version during debugging.
 * 
 * KEY CHANGES:
 * 1. Import and use SkinWeightTransferDiagnostic instead of SkinWeightTransfer
 * 2. Add detailed logging at each step of mesh loading
 * 3. Verify skeleton state before binding
 * 4. Export diagnostic data for analysis
 */

// PATCH 1: Replace the import statement
// FROM:
// import { SkinWeightTransfer } from './SkinWeightTransfer.js';
// TO:
// import { SkinWeightTransferDiagnostic } from './SkinWeightTransferDiagnostic.js';

// PATCH 2: Replace weightTransfer initialization in loadBodyMesh()
// FROM:
// this.weightTransfer = new SkinWeightTransfer({
//     useWeightInpainting: true,
//     debugVisualization: this.debugMode
// });
// TO:
// this.weightTransfer = new SkinWeightTransferDiagnostic({
//     useWeightInpainting: true,
//     debugVisualization: this.debugMode,
//     validateBeforeTransfer: true,
//     validateAfterTransfer: true
// });

// PATCH 3: Add skeleton state verification before weight transfer
// Add this code BEFORE calling this.weightTransfer.transfer():

/*
// CRITICAL: Verify skeleton is in rest pose before weight transfer
console.log('[ThreeScene] Verifying skeleton state before weight transfer...');
const nonRestBones = this.skeleton.bones.filter(bone => {
    const isIdentity = bone.matrixWorld.elements.every((v, idx) => {
        const expected = idx === 0 || idx === 5 || idx === 10 || idx === 15 ? 1 : 0;
        return Math.abs(v - expected) < 0.001;
    });
    return !isIdentity;
});

if (nonRestBones.length > 0) {
    console.warn('[ThreeScene] ⚠️ Skeleton NOT in rest pose! Resetting...');
    console.warn('[ThreeScene] Non-rest bones:', nonRestBones.map(b => b.name));
    
    // Reset all bones to identity
    this.skeleton.bones.forEach(bone => {
        bone.position.set(0, 0, 0);
        bone.quaternion.set(0, 0, 0, 1);
        bone.scale.set(1, 1, 1);
    });
    this.skeleton.update();
    
    // Recalculate bind matrices
    this.skeleton.calculateInverses();
    console.log('[ThreeScene] Skeleton reset to rest pose');
}
*/

// PATCH 4: Replace the weight transfer call to capture diagnostics
// FROM:
// this.skinnedClothingMesh = this.weightTransfer.transfer(
//     this.bodyMesh,
//     loadedMesh
// );
// TO:
/*
try {
    this.skinnedClothingMesh = this.weightTransfer.transfer(
        this.bodyMesh,
        loadedMesh
    );
    
    // Print diagnostic report
    const report = this.weightTransfer.printDiagnosticReport();
    
    // Store report for export
    window.weightTransferReport = report;
    
    if (report.errors.length > 0) {
        console.error('[ThreeScene] Weight transfer completed with errors!');
        console.error('[ThreeScene] Check window.weightTransferReport for details');
    }
} catch (error) {
    console.error('[ThreeScene] Weight transfer failed:', error);
    throw error;
}
*/

// PATCH 5: Add detailed logging after creating SkinnedMesh
// Add after: this.skinnedClothingMesh.bind(skeleton);
/*
console.log('[ThreeScene] SkinnedMesh created:');
console.log('  - Geometry vertices:', this.skinnedClothingMesh.geometry.attributes.position.count);
console.log('  - Skeleton bones:', this.skinnedClothingMesh.skeleton?.bones.length);
console.log('  - Position:', this.skinnedClothingMesh.position.toArray());
console.log('  - Scale:', this.skinnedClothingMesh.scale.toArray());
console.log('  - Visible:', this.skinnedClothingMesh.visible);
console.log('  - Frustum culled:', this.skinnedClothingMesh.frustumCulled);

// Verify bone matrices
const hasInvalidMatrices = this.skeleton.bones.some(bone => {
    return bone.matrixWorld.elements.some(v => isNaN(v) || !isFinite(v));
});
if (hasInvalidMatrices) {
    console.error('[ThreeScene] ⚠️ Skeleton has invalid matrices!');
}
*/

// PATCH 6: Export diagnostic function for manual testing
// Add this method to the ThreeScene class:

/*
exportDiagnosticReport() {
    if (this.weightTransfer && this.weightTransfer.getDiagnosticReport) {
        const report = this.weightTransfer.getDiagnosticReport();
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `weight_transfer_diagnostic_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        console.log('[ThreeScene] Diagnostic report exported');
    } else {
        console.warn('[ThreeScene] No diagnostic data available');
    }
}
*/

// INSTRUCTIONS FOR USE:
// 
// 1. To enable diagnostics, add ?debug=true to the URL
// 2. Open browser console to see detailed logs
// 3. After weight transfer, access window.weightTransferReport in console
// 4. Call app.threeScene.exportDiagnosticReport() to download full report
//
// COMMON ISSUES TO LOOK FOR:
//
// 1. "Skeleton NOT in rest pose" - This is the #1 cause of crumpling
//    Solution: Reset skeleton before binding (PATCH 3)
//
// 2. "Significant size mismatch" - Body and clothing different scales
//    Solution: Normalize scales before weight transfer
//
// 3. "Vertices with zero weight" - Clothing vertices not matching body
//    Solution: Adjust distance threshold or clothing position
//
// 4. "Invalid bone index" - Mismatched skeleton/weight arrays
//    Solution: Verify skeleton bone count matches weight indices
