/**
 * Effects Module Index
 *
 * Visual effects for the Dreamwear Lookbook.
 * Import all effects from this single file.
 */

export { PointCloudDissolver } from './PointCloudDissolver.js';
export { CurveTextFlow } from './CurveTextFlow.js';
export { PostProcessingManager } from './PostProcessingManager.js';

/**
 * Usage Example:
 *
 * ```javascript
 * import { PointCloudDissolver, CurveTextFlow, PostProcessingManager } from './effects/index.js';
 *
 * // Point Cloud Dissolution
 * const dissolver = new PointCloudDissolver({
 *     particleSize: 0.02,
 *     scatterRadius: 2.0,
 *     dissolveDuration: 2.0
 * });
 * const pointCloud = dissolver.createFromMesh(myMesh);
 * scene.add(pointCloud);
 * dissolver.dissolve(); // Start dissolution
 * // Later: dissolver.reform(); // Reform back to mesh
 *
 * // Orbiting Text
 * const textFlow = new CurveTextFlow({
 *     fontSize: 0.15,
 *     orbitSpeed: 0.1,
 *     numCurves: 3
 * });
 * const textGroup = await textFlow.init(['dream', 'red', 'flowing'], meshCenter);
 * scene.add(textGroup);
 *
 * // Post-Processing
 * const postProcessing = new PostProcessingManager(renderer, scene, camera);
 * postProcessing.applyPreset('dreamy'); // or 'raw', 'vhs', 'glitch', 'clean'
 *
 * // In animation loop:
 * postProcessing.update(elapsedTime);
 * postProcessing.render();
 * ```
 */
