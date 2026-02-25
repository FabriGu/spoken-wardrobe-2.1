/**
 * MediaPipePoseDriver.js
 *
 * Real-time pose detection using MediaPipe Tasks API in the browser.
 * Drives skeleton bones based on detected body landmarks.
 *
 * MediaPipe Pose Landmark indices:
 * 0: nose, 1: left_eye_inner, 2: left_eye, 3: left_eye_outer,
 * 4: right_eye_inner, 5: right_eye, 6: right_eye_outer,
 * 7: left_ear, 8: right_ear, 9: mouth_left, 10: mouth_right,
 * 11: left_shoulder, 12: right_shoulder,
 * 13: left_elbow, 14: right_elbow,
 * 15: left_wrist, 16: right_wrist,
 * 17: left_pinky, 18: right_pinky,
 * 19: left_index, 20: right_index,
 * 21: left_thumb, 22: right_thumb,
 * 23: left_hip, 24: right_hip,
 * 25: left_knee, 26: right_knee,
 * 27: left_ankle, 28: right_ankle,
 * 29: left_heel, 30: right_heel,
 * 31: left_foot_index, 32: right_foot_index
 */

import * as THREE from 'three';

export class MediaPipePoseDriver {
    constructor() {
        this.poseLandmarker = null;
        this.video = null;
        this.canvas = null;
        this.ctx = null;
        this.skeleton = null;
        this.boneMap = null;

        this.enabled = false;
        this.initialized = false;
        this.lastVideoTime = -1;

        // Landmark smoothing
        this.smoothingFactor = 0.3;
        this.previousLandmarks = null;

        // Countdown before skeleton control starts
        this.countdownSeconds = 3;
        this.countdownRemaining = 0;
        this.skeletonControlEnabled = false;

        // 3D keypoint visualization
        this.keypointGroup = null;
        this.showKeypoints = true;
        this.keypointColor = 0x9933ff; // Purple

        // Calibration for matching body mesh
        this.calibrated = false;
        this.keypointScale = 1.0;
        this.keypointOffsetY = 1.0;
        this.keypointOffsetX = 0.0;
        this.keypointOffsetZ = 0.0;

        // Manual adjustment controls (applied on top of calibration)
        // Default values tuned for rigged_full_v1.glb body mesh
        this.manualOffsetY = -0.25;
        this.manualOffsetZ = 0.1;
        this.manualScaleMultiplier = 1.0;

        // Callbacks
        this.onPoseDetected = null;
        this.onCountdown = null; // Called with remaining seconds
        this.onError = null;

        // Model URL (lite version for faster loading)
        this.modelUrl = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

        // WASM base path
        this.wasmBasePath = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';
    }

    /**
     * Initialize MediaPipe and webcam
     */
    async init() {
        if (this.initialized) return true;

        try {
            console.log('[MediaPipePoseDriver] Initializing...');

            // Load MediaPipe vision module
            const { PoseLandmarker, FilesetResolver } = await this._loadMediaPipe();

            // Initialize fileset
            const vision = await FilesetResolver.forVisionTasks(this.wasmBasePath);

            // Create pose landmarker
            this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: this.modelUrl,
                    delegate: 'GPU'
                },
                runningMode: 'VIDEO',
                numPoses: 1,
                minPoseDetectionConfidence: 0.5,
                minPosePresenceConfidence: 0.5,
                minTrackingConfidence: 0.5,
                outputSegmentationMasks: false
            });

            console.log('[MediaPipePoseDriver] Pose landmarker created');

            // Setup webcam
            await this._setupWebcam();

            this.initialized = true;
            console.log('[MediaPipePoseDriver] Initialized successfully');
            return true;

        } catch (error) {
            console.error('[MediaPipePoseDriver] Initialization failed:', error);
            if (this.onError) this.onError(error);
            return false;
        }
    }

    /**
     * Load MediaPipe Tasks Vision module
     */
    async _loadMediaPipe() {
        // Try dynamic import
        try {
            const module = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm');
            return {
                PoseLandmarker: module.PoseLandmarker,
                FilesetResolver: module.FilesetResolver
            };
        } catch (e) {
            console.warn('[MediaPipePoseDriver] ESM import failed, trying alternative:', e);
        }

        // Fallback: Load via script tag
        return new Promise((resolve, reject) => {
            if (window._mediapipeVision) {
                resolve(window._mediapipeVision);
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs';
            script.type = 'module';

            // Use a different approach - create inline module
            const moduleScript = document.createElement('script');
            moduleScript.type = 'module';
            moduleScript.textContent = `
                import { PoseLandmarker, FilesetResolver } from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs';
                window._mediapipeVision = { PoseLandmarker, FilesetResolver };
                window.dispatchEvent(new CustomEvent('mediapipe-ready'));
            `;

            const handleReady = () => {
                window.removeEventListener('mediapipe-ready', handleReady);
                if (window._mediapipeVision) {
                    resolve(window._mediapipeVision);
                } else {
                    reject(new Error('MediaPipe failed to load'));
                }
            };

            window.addEventListener('mediapipe-ready', handleReady);
            document.head.appendChild(moduleScript);

            setTimeout(() => {
                window.removeEventListener('mediapipe-ready', handleReady);
                reject(new Error('MediaPipe load timeout'));
            }, 30000);
        });
    }

    /**
     * Setup webcam video stream
     */
    async _setupWebcam() {
        // Create video element
        this.video = document.createElement('video');
        this.video.setAttribute('autoplay', '');
        this.video.setAttribute('playsinline', '');
        this.video.style.display = 'none';
        document.body.appendChild(this.video);

        // Create canvas for debugging/preview
        this.canvas = document.createElement('canvas');
        this.canvas.width = 640;
        this.canvas.height = 480;
        this.ctx = this.canvas.getContext('2d');

        // Get webcam stream
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'user'
            }
        });

        this.video.srcObject = stream;
        await this.video.play();

        console.log('[MediaPipePoseDriver] Webcam ready');
    }

    /**
     * Set the skeleton to drive
     */
    setSkeleton(skeleton) {
        this.skeleton = skeleton;
        this._buildBoneMap();
        console.log('[MediaPipePoseDriver] Skeleton set with', skeleton.bones.length, 'bones');
    }

    /**
     * Build mapping from MediaPipe landmarks to skeleton bones
     */
    _buildBoneMap() {
        if (!this.skeleton) return;

        this.boneMap = {};
        const bones = this.skeleton.bones;

        // Find bones by name
        for (const bone of bones) {
            const name = bone.name.toLowerCase();

            if (name.includes('spine') || name.includes('root')) {
                this.boneMap.spine = bone;
            } else if (name.includes('left') && name.includes('upper') && name.includes('arm')) {
                this.boneMap.leftUpperArm = bone;
            } else if (name.includes('left') && name.includes('lower') && name.includes('arm')) {
                this.boneMap.leftLowerArm = bone;
            } else if (name.includes('right') && name.includes('upper') && name.includes('arm')) {
                this.boneMap.rightUpperArm = bone;
            } else if (name.includes('right') && name.includes('lower') && name.includes('arm')) {
                this.boneMap.rightLowerArm = bone;
            } else if (name.includes('left') && name.includes('upper') && name.includes('leg')) {
                this.boneMap.leftUpperLeg = bone;
            } else if (name.includes('left') && name.includes('lower') && name.includes('leg')) {
                this.boneMap.leftLowerLeg = bone;
            } else if (name.includes('right') && name.includes('upper') && name.includes('leg')) {
                this.boneMap.rightUpperLeg = bone;
            } else if (name.includes('right') && name.includes('lower') && name.includes('leg')) {
                this.boneMap.rightLowerLeg = bone;
            }
        }

        console.log('[MediaPipePoseDriver] Bone map:', Object.keys(this.boneMap));
    }

    /**
     * Start pose detection with optional countdown
     * @param {boolean} withCountdown - Whether to use countdown before skeleton control
     */
    start(withCountdown = true) {
        if (!this.initialized) {
            console.warn('[MediaPipePoseDriver] Not initialized');
            return;
        }

        this.enabled = true;
        this.skeletonControlEnabled = !withCountdown;

        if (withCountdown) {
            this.countdownRemaining = this.countdownSeconds;
            console.log(`[MediaPipePoseDriver] Starting with ${this.countdownSeconds}s countdown...`);
            this._startCountdown();
        } else {
            this.skeletonControlEnabled = true;
        }

        this._detectLoop();
        console.log('[MediaPipePoseDriver] Started');
    }

    /**
     * Countdown timer before skeleton control begins
     */
    _startCountdown() {
        const tick = () => {
            if (!this.enabled) return;

            if (this.countdownRemaining > 0) {
                console.log(`[MediaPipePoseDriver] ${this.countdownRemaining}...`);
                if (this.onCountdown) {
                    this.onCountdown(this.countdownRemaining);
                }
                this.countdownRemaining--;
                setTimeout(tick, 1000);
            } else {
                this.skeletonControlEnabled = true;
                console.log('[MediaPipePoseDriver] Skeleton control enabled!');
                if (this.onCountdown) {
                    this.onCountdown(0); // Signal countdown complete
                }
            }
        };
        tick();
    }

    /**
     * Stop pose detection
     */
    stop() {
        this.enabled = false;
        this.skeletonControlEnabled = false;
        this.countdownRemaining = 0;
        console.log('[MediaPipePoseDriver] Stopped');
    }

    /**
     * Set the Three.js scene for keypoint visualization
     */
    setScene(scene) {
        this.scene = scene;
        this._createKeypointGroup();
    }

    /**
     * Create 3D keypoint visualization group
     */
    _createKeypointGroup() {
        if (!this.scene) return;

        // Remove existing group
        if (this.keypointGroup) {
            this.scene.remove(this.keypointGroup);
        }

        this.keypointGroup = new THREE.Group();
        this.keypointGroup.name = 'MediaPipeKeypoints';

        // Create 33 keypoint spheres
        const geometry = new THREE.SphereGeometry(0.02, 8, 8);
        const material = new THREE.MeshBasicMaterial({ color: this.keypointColor });

        for (let i = 0; i < 33; i++) {
            const sphere = new THREE.Mesh(geometry, material);
            sphere.visible = false;
            this.keypointGroup.add(sphere);
        }

        // Create connection lines
        const lineMaterial = new THREE.LineBasicMaterial({ color: this.keypointColor, opacity: 0.5, transparent: true });
        const connections = [
            [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
            [11, 23], [12, 24], [23, 24],
            [23, 25], [25, 27], [24, 26], [26, 28]
        ];

        this.keypointConnections = connections;
        this.connectionLines = [];

        for (const [i, j] of connections) {
            const points = [new THREE.Vector3(), new THREE.Vector3()];
            const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(lineGeometry, lineMaterial);
            line.visible = false;
            this.keypointGroup.add(line);
            this.connectionLines.push({ line, indices: [i, j] });
        }

        this.scene.add(this.keypointGroup);
    }

    /**
     * Toggle keypoint visibility
     */
    setKeypointsVisible(visible) {
        this.showKeypoints = visible;
        if (this.keypointGroup) {
            this.keypointGroup.visible = visible;
        }
    }

    /**
     * Calibrate keypoint visualization to match a body mesh
     * @param {THREE.SkinnedMesh} bodyMesh - The body mesh to calibrate against
     */
    calibrateToBodyMesh(bodyMesh) {
        if (!bodyMesh || !bodyMesh.geometry) {
            console.warn('[MediaPipePoseDriver] Cannot calibrate: invalid body mesh');
            return;
        }

        // Get the world-space bounding box of the body mesh
        bodyMesh.updateMatrixWorld(true);
        const bbox = new THREE.Box3().setFromObject(bodyMesh);
        const size = bbox.getSize(new THREE.Vector3());
        const center = bbox.getCenter(new THREE.Vector3());

        // MediaPipe world landmark coordinate system:
        // - Y points DOWN (positive = down)
        // - Origin is at hip center
        // - Head is at approximately y = -0.55 (negative, above origin)
        // - Feet are at approximately y = +0.95 (positive, below origin)
        // - Total body height ≈ 1.5m (from -0.55 to +0.95)

        const mediaPipeHeadY = -0.55;  // Head position in MediaPipe coords
        const mediaPipeFeetY = 0.95;   // Feet position in MediaPipe coords
        const mediaPipeBodyHeight = mediaPipeFeetY - mediaPipeHeadY; // ≈ 1.5m

        // Calculate scale to match body mesh height
        this.keypointScale = size.y / mediaPipeBodyHeight;

        // After Y flip transformation: y_transformed = -mediaPipeY * scale
        // Head becomes: -(-0.55) * scale = 0.55 * scale (positive, at top)
        // Feet becomes: -(0.95) * scale = -0.95 * scale (negative, at bottom)

        // To align: mesh top (bbox.max.y) should equal transformed head position + offset
        // bbox.max.y = (0.55 * scale) + offsetY
        // offsetY = bbox.max.y - (0.55 * scale)
        const transformedHeadY = -mediaPipeHeadY * this.keypointScale;
        this.keypointOffsetY = bbox.max.y - transformedHeadY;

        // X and Z: center on mesh
        this.keypointOffsetX = center.x;
        this.keypointOffsetZ = center.z;

        this.calibrated = true;

        console.log(`[MediaPipePoseDriver] Calibrated to body mesh:`);
        console.log(`  Mesh bbox: min.y=${bbox.min.y.toFixed(3)}, max.y=${bbox.max.y.toFixed(3)}`);
        console.log(`  Mesh size: ${size.x.toFixed(3)} x ${size.y.toFixed(3)} x ${size.z.toFixed(3)}`);
        console.log(`  Mesh center: (${center.x.toFixed(3)}, ${center.y.toFixed(3)}, ${center.z.toFixed(3)})`);
        console.log(`  MediaPipe height: ${mediaPipeBodyHeight.toFixed(3)}m`);
        console.log(`  Keypoint scale: ${this.keypointScale.toFixed(3)}`);
        console.log(`  Keypoint offset: (${this.keypointOffsetX.toFixed(3)}, ${this.keypointOffsetY.toFixed(3)}, ${this.keypointOffsetZ.toFixed(3)})`);

        // Update sphere size to match scale
        if (this.keypointGroup) {
            const sphereRadius = 0.02 * this.keypointScale; // Scale sphere size
            const newGeometry = new THREE.SphereGeometry(sphereRadius, 8, 8);

            this.keypointGroup.children.forEach(child => {
                if (child.isMesh) {
                    child.geometry.dispose();
                    child.geometry = newGeometry;
                }
            });
        }
    }

    /**
     * Detection loop
     */
    _detectLoop() {
        if (!this.enabled) return;

        if (this.video.currentTime !== this.lastVideoTime) {
            this.lastVideoTime = this.video.currentTime;

            const startTime = performance.now();
            const results = this.poseLandmarker.detectForVideo(this.video, startTime);

            if (results.landmarks && results.landmarks.length > 0) {
                const landmarks = results.landmarks[0];
                const worldLandmarks = results.worldLandmarks?.[0];

                // Apply smoothing
                const smoothedLandmarks = this._smoothLandmarks(worldLandmarks || landmarks);

                // Update 3D keypoint visualization
                if (this.showKeypoints && this.keypointGroup) {
                    this._updateKeypointVisualization(smoothedLandmarks);
                }

                // Update skeleton (only if countdown complete)
                if (this.skeleton && this.skeletonControlEnabled) {
                    this._updateSkeleton(smoothedLandmarks);
                }

                // Callback
                if (this.onPoseDetected) {
                    this.onPoseDetected({
                        landmarks: landmarks,
                        worldLandmarks: worldLandmarks,
                        smoothedLandmarks: smoothedLandmarks
                    });
                }
            }
        }

        requestAnimationFrame(() => this._detectLoop());
    }

    /**
     * Apply smoothing to landmarks
     */
    _smoothLandmarks(landmarks) {
        if (!this.previousLandmarks || landmarks.length !== this.previousLandmarks.length) {
            this.previousLandmarks = landmarks.map(l => ({ ...l }));
            return landmarks;
        }

        const smoothed = landmarks.map((lm, i) => {
            const prev = this.previousLandmarks[i];
            return {
                x: prev.x + (lm.x - prev.x) * this.smoothingFactor,
                y: prev.y + (lm.y - prev.y) * this.smoothingFactor,
                z: prev.z + (lm.z - prev.z) * this.smoothingFactor,
                visibility: lm.visibility
            };
        });

        this.previousLandmarks = smoothed.map(l => ({ ...l }));
        return smoothed;
    }

    /**
     * Update 3D keypoint visualization
     */
    _updateKeypointVisualization(landmarks) {
        if (!this.keypointGroup) return;

        const children = this.keypointGroup.children;

        // Use calibrated values with manual adjustments
        const scale = this.keypointScale * this.manualScaleMultiplier;
        const offsetX = this.keypointOffsetX;
        const offsetY = this.keypointOffsetY + this.manualOffsetY;  // Add manual Y offset
        const offsetZ = this.keypointOffsetZ + this.manualOffsetZ;  // Add manual Z offset

        // Helper to transform MediaPipe coords to scene coords
        const transform = (lm) => ({
            x: -lm.x * scale + offsetX,   // Mirror X and offset
            y: -lm.y * scale + offsetY,   // Flip Y and offset
            z: -lm.z * scale + offsetZ    // Offset Z
        });

        // Update keypoint spheres (first 33 children)
        for (let i = 0; i < 33 && i < landmarks.length; i++) {
            const sphere = children[i];
            if (sphere && sphere.isMesh) {
                const pos = transform(landmarks[i]);
                sphere.position.set(pos.x, pos.y, pos.z);
                sphere.visible = (landmarks[i].visibility || 0) > 0.5;
            }
        }

        // Update connection lines
        if (this.connectionLines) {
            for (let c = 0; c < this.connectionLines.length; c++) {
                const { line, indices } = this.connectionLines[c];
                const [i, j] = indices;

                if (i < landmarks.length && j < landmarks.length) {
                    const posI = transform(landmarks[i]);
                    const posJ = transform(landmarks[j]);

                    const positions = line.geometry.attributes.position;
                    positions.setXYZ(0, posI.x, posI.y, posI.z);
                    positions.setXYZ(1, posJ.x, posJ.y, posJ.z);
                    positions.needsUpdate = true;

                    const visI = landmarks[i].visibility || 0;
                    const visJ = landmarks[j].visibility || 0;
                    line.visible = visI > 0.5 && visJ > 0.5;
                }
            }
        }
    }

    /**
     * Update skeleton bones from landmarks
     */
    _updateSkeleton(landmarks) {
        if (!this.boneMap) return;

        // MediaPipe landmark indices
        const L = {
            leftShoulder: 11, rightShoulder: 12,
            leftElbow: 13, rightElbow: 14,
            leftWrist: 15, rightWrist: 16,
            leftHip: 23, rightHip: 24,
            leftKnee: 25, rightKnee: 26,
            leftAnkle: 27, rightAnkle: 28
        };

        // Helper to create vector from landmarks
        const vec = (idx) => new THREE.Vector3(
            -landmarks[idx].x,  // Mirror X for screen
            -landmarks[idx].y,  // Flip Y (MediaPipe Y is down)
            -landmarks[idx].z
        );

        // Helper to compute rotation from direction
        const computeRotation = (fromIdx, toIdx, restAxis = new THREE.Vector3(0, -1, 0)) => {
            const dir = vec(toIdx).sub(vec(fromIdx)).normalize();
            const quat = new THREE.Quaternion();
            quat.setFromUnitVectors(restAxis, dir);
            return quat;
        };

        // Update spine (based on shoulder and hip orientation)
        if (this.boneMap.spine) {
            const shoulderCenter = vec(L.leftShoulder).add(vec(L.rightShoulder)).multiplyScalar(0.5);
            const hipCenter = vec(L.leftHip).add(vec(L.rightHip)).multiplyScalar(0.5);
            const spineDir = shoulderCenter.sub(hipCenter).normalize();

            // Compute torso twist from shoulders
            const shoulderVec = vec(L.rightShoulder).sub(vec(L.leftShoulder)).normalize();

            const spineQuat = new THREE.Quaternion();
            spineQuat.setFromUnitVectors(new THREE.Vector3(0, 1, 0), spineDir);

            // Add twist
            const twistAngle = Math.atan2(shoulderVec.z, shoulderVec.x);
            const twist = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), twistAngle);
            spineQuat.multiply(twist);

            this._applyRotation(this.boneMap.spine, spineQuat);
        }

        // Update arms
        if (this.boneMap.leftUpperArm) {
            const rot = computeRotation(L.leftShoulder, L.leftElbow, new THREE.Vector3(1, 0, 0));
            this._applyRotation(this.boneMap.leftUpperArm, rot);
        }

        if (this.boneMap.leftLowerArm) {
            const rot = computeRotation(L.leftElbow, L.leftWrist, new THREE.Vector3(1, 0, 0));
            this._applyRotation(this.boneMap.leftLowerArm, rot);
        }

        if (this.boneMap.rightUpperArm) {
            const rot = computeRotation(L.rightShoulder, L.rightElbow, new THREE.Vector3(-1, 0, 0));
            this._applyRotation(this.boneMap.rightUpperArm, rot);
        }

        if (this.boneMap.rightLowerArm) {
            const rot = computeRotation(L.rightElbow, L.rightWrist, new THREE.Vector3(-1, 0, 0));
            this._applyRotation(this.boneMap.rightLowerArm, rot);
        }

        // Update legs
        if (this.boneMap.leftUpperLeg) {
            const rot = computeRotation(L.leftHip, L.leftKnee, new THREE.Vector3(0, -1, 0));
            this._applyRotation(this.boneMap.leftUpperLeg, rot);
        }

        if (this.boneMap.leftLowerLeg) {
            const rot = computeRotation(L.leftKnee, L.leftAnkle, new THREE.Vector3(0, -1, 0));
            this._applyRotation(this.boneMap.leftLowerLeg, rot);
        }

        if (this.boneMap.rightUpperLeg) {
            const rot = computeRotation(L.rightHip, L.rightKnee, new THREE.Vector3(0, -1, 0));
            this._applyRotation(this.boneMap.rightUpperLeg, rot);
        }

        if (this.boneMap.rightLowerLeg) {
            const rot = computeRotation(L.rightKnee, L.rightAnkle, new THREE.Vector3(0, -1, 0));
            this._applyRotation(this.boneMap.rightLowerLeg, rot);
        }

        // Update skeleton
        if (this.skeleton) {
            this.skeleton.update();
        }
    }

    /**
     * Apply rotation with smoothing
     */
    _applyRotation(bone, targetQuat) {
        if (!bone) return;

        // Store rest pose if not already stored
        if (!bone.userData.restQuaternion) {
            bone.userData.restQuaternion = bone.quaternion.clone();
        }

        // Combine rest pose with target rotation
        const finalQuat = bone.userData.restQuaternion.clone().multiply(targetQuat);

        // Smooth application
        bone.quaternion.slerp(finalQuat, this.smoothingFactor);
    }

    /**
     * Get the preview canvas (for debugging)
     */
    getPreviewCanvas() {
        return this.canvas;
    }

    /**
     * Draw landmarks on preview canvas
     */
    drawLandmarks(landmarks) {
        if (!this.ctx || !landmarks) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw video frame
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // Draw landmarks
        this.ctx.fillStyle = '#00FF00';
        for (const lm of landmarks) {
            const x = lm.x * this.canvas.width;
            const y = lm.y * this.canvas.height;
            this.ctx.beginPath();
            this.ctx.arc(x, y, 5, 0, Math.PI * 2);
            this.ctx.fill();
        }

        // Draw connections
        const connections = [
            [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
            [11, 23], [12, 24], [23, 24],
            [23, 25], [25, 27], [24, 26], [26, 28]
        ];

        this.ctx.strokeStyle = '#00FF00';
        this.ctx.lineWidth = 2;
        for (const [i, j] of connections) {
            if (i < landmarks.length && j < landmarks.length) {
                this.ctx.beginPath();
                this.ctx.moveTo(landmarks[i].x * this.canvas.width, landmarks[i].y * this.canvas.height);
                this.ctx.lineTo(landmarks[j].x * this.canvas.width, landmarks[j].y * this.canvas.height);
                this.ctx.stroke();
            }
        }
    }

    /**
     * Clean up resources
     */
    dispose() {
        this.stop();

        if (this.video && this.video.srcObject) {
            const tracks = this.video.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            this.video.remove();
        }

        if (this.canvas) {
            this.canvas.remove();
        }

        if (this.poseLandmarker) {
            this.poseLandmarker.close();
        }

        this.initialized = false;
        console.log('[MediaPipePoseDriver] Disposed');
    }
}

export default MediaPipePoseDriver;
