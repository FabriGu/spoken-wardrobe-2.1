#!/usr/bin/env python3
"""
Gaussian Try-On Pipeline - Full Integration

Integrates all components:
1. Depth-based splat generation (generate_splat.py)
2. Calibration-time weight assignment (gaussian_weight_assigner.py)
3. Real-time DQS animation (gaussian_animator.py)

This is the main entry point for the Gaussian Splat try-on system.
"""

import os
import sys
import time
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gaussian_test.generate_splat import GaussianSplatGenerator
from gaussian_test.gaussian_weight_assigner import (
    GaussianWeightAssigner,
    assign_weights_from_calibration
)
from gaussian_test.gaussian_animator import (
    GaussianAnimator,
    create_animator_from_calibration
)

logger = logging.getLogger('GaussianTryOn')


@dataclass
class CalibrationMetrics:
    """Complete body measurements captured at calibration time for proper scaling."""
    # In splat space (3D, after convert_landmarks_to_3d)
    shoulder_width_3d: float = 0.0          # Distance between shoulders
    torso_height_3d: float = 0.0            # Shoulder to hip distance
    body_center_3d: Optional[np.ndarray] = None  # 3D center point

    # In screen space (normalized [0,1])
    shoulder_width_screen: float = 0.0      # Shoulder width in screen coords
    torso_height_screen: float = 0.0        # Torso height in screen coords
    body_center_screen: Optional[np.ndarray] = None  # Center in screen coords

    # Splat bounds (for scaling reference)
    splat_width: float = 2.0                # X range of splats
    splat_height: float = 2.0               # Y range of splats

    # Frame info at calibration
    frame_width: int = 1280
    frame_height: int = 720


@dataclass
class TryOnState:
    """Current state of the try-on pipeline"""
    # Generation
    splat_positions: Optional[np.ndarray] = None
    splat_colors: Optional[np.ndarray] = None
    ply_path: Optional[str] = None

    # Calibration
    is_calibrated: bool = False
    calibration_landmarks: Optional[np.ndarray] = None
    calibration_landmarks_3d: Optional[np.ndarray] = None  # In splat space
    calibration_body_center: Optional[np.ndarray] = None   # Body center at calibration (DEPRECATED)
    calibration_body_scale: float = 1.0                    # Body scale at calibration (DEPRECATED)
    calibration_metrics: Optional[CalibrationMetrics] = None  # NEW: Complete metrics
    skinning_weights: Optional[np.ndarray] = None

    # Animation
    animator: Optional[GaussianAnimator] = None
    current_positions: Optional[np.ndarray] = None

    # Stats
    generation_time: float = 0.0
    calibration_time: float = 0.0
    last_animation_time: float = 0.0
    frame_count: int = 0


class GaussianTryOnPipeline:
    """
    Main pipeline for Gaussian Splat virtual try-on.

    Usage:
        pipeline = GaussianTryOnPipeline()

        # 1. Generate splat from clothing image
        pipeline.generate_from_image("clothing.png")

        # 2. Calibrate with user's T-pose
        pipeline.calibrate(t_pose_landmarks)

        # 3. Animate each frame with live landmarks
        while running:
            transformed = pipeline.animate(current_landmarks)
            render(transformed)
    """

    def __init__(
        self,
        use_depth: bool = True,
        use_gpu: bool = True,
        num_splats: int = 10000,
        depth_scale: float = 0.5
    ):
        """
        Initialize the try-on pipeline.

        Args:
            use_depth: Use depth estimation for 3D splats
            use_gpu: Use GPU for animation (recommended)
            num_splats: Number of splats to generate
            depth_scale: Scale factor for depth values
        """
        self.use_depth = use_depth
        self.use_gpu = use_gpu
        self.num_splats = num_splats
        self.depth_scale = depth_scale

        # Initialize components
        self.generator = None
        self.weight_assigner = GaussianWeightAssigner()

        # State
        self.state = TryOnState()

        logger.info("GaussianTryOnPipeline initialized")
        logger.info(f"  use_depth={use_depth}, use_gpu={use_gpu}")
        logger.info(f"  num_splats={num_splats}, depth_scale={depth_scale}")

    def generate_from_image(
        self,
        image_path: str,
        output_dir: str = None
    ) -> Dict:
        """
        Generate Gaussian splats from a clothing image.

        Args:
            image_path: Path to clothing image (PNG with transparency)
            output_dir: Directory for output files (optional)

        Returns:
            Dict with generation results
        """
        logger.info(f"Generating splats from: {image_path}")
        start_time = time.time()

        # Lazy-load generator (loads depth model)
        if self.generator is None:
            logger.info("Loading splat generator...")
            self.generator = GaussianSplatGenerator(use_depth=self.use_depth)

        # Generate
        result = self.generator.generate(
            image_path,
            depth_scale=self.depth_scale
        )

        if not result['success']:
            logger.error(f"Generation failed: {result['errors']}")
            return result

        # Load generated PLY to get positions/colors
        self.state.ply_path = result['output']
        self.state.splat_positions, self.state.splat_colors = self._load_ply(
            result['output']
        )

        self.state.generation_time = time.time() - start_time
        logger.info(f"Generated {len(self.state.splat_positions)} splats in "
                   f"{self.state.generation_time:.2f}s")

        return result

    def load_from_ply(self, ply_path: str) -> bool:
        """
        Load existing splats from PLY file.

        Args:
            ply_path: Path to PLY file

        Returns:
            True if successful
        """
        try:
            self.state.splat_positions, self.state.splat_colors = self._load_ply(
                ply_path
            )
            self.state.ply_path = ply_path
            logger.info(f"Loaded {len(self.state.splat_positions)} splats from {ply_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load PLY: {e}")
            return False

    def calibrate(
        self,
        landmarks_3d: np.ndarray,
        depth_map: np.ndarray = None,
        image_shape: Tuple[int, int] = None
    ) -> bool:
        """
        Calibrate with user's T-pose.

        This is called once when user strikes T-pose. It:
        1. Stores calibration landmarks
        2. Computes skinning weights for all splats
        3. Initializes animator with rest pose

        Args:
            landmarks_3d: (33, 3) MediaPipe landmarks (normalized or 3D)
            depth_map: Optional depth map for better z-estimation
            image_shape: (H, W) of calibration frame

        Returns:
            True if calibration successful
        """
        if self.state.splat_positions is None:
            logger.error("Cannot calibrate: no splats loaded")
            return False

        logger.info("Calibrating with T-pose...")
        start_time = time.time()

        # Store calibration landmarks (raw screen coordinates)
        self.state.calibration_landmarks = landmarks_3d.copy()

        # Convert to 3D splat space (centered coordinates)
        landmarks_3d_centered = self.weight_assigner.convert_landmarks_to_3d(
            landmarks_3d,
            depth_map=depth_map,
            image_shape=image_shape,
            depth_scale=self.depth_scale
        )
        self.state.calibration_landmarks_3d = landmarks_3d_centered.copy()

        # Compute comprehensive calibration metrics for proper scaling
        LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
        LEFT_HIP, RIGHT_HIP = 23, 24

        # === 3D METRICS (in splat space) ===
        shoulder_center_3d = (landmarks_3d_centered[LEFT_SHOULDER] +
                              landmarks_3d_centered[RIGHT_SHOULDER]) / 2
        hip_center_3d = (landmarks_3d_centered[LEFT_HIP] +
                         landmarks_3d_centered[RIGHT_HIP]) / 2
        body_center_3d = (shoulder_center_3d + hip_center_3d) / 2

        shoulder_width_3d = np.linalg.norm(
            landmarks_3d_centered[RIGHT_SHOULDER] -
            landmarks_3d_centered[LEFT_SHOULDER]
        )
        torso_height_3d = np.linalg.norm(
            landmarks_3d_centered[LEFT_HIP] -
            landmarks_3d_centered[LEFT_SHOULDER]
        )

        # === SCREEN METRICS (normalized [0,1]) ===
        shoulder_center_screen = (landmarks_3d[LEFT_SHOULDER][:2] +
                                  landmarks_3d[RIGHT_SHOULDER][:2]) / 2
        hip_center_screen = (landmarks_3d[LEFT_HIP][:2] +
                             landmarks_3d[RIGHT_HIP][:2]) / 2
        body_center_screen = (shoulder_center_screen + hip_center_screen) / 2

        shoulder_width_screen = np.abs(
            landmarks_3d[RIGHT_SHOULDER][0] - landmarks_3d[LEFT_SHOULDER][0]
        )
        torso_height_screen = np.abs(
            landmarks_3d[LEFT_HIP][1] - landmarks_3d[LEFT_SHOULDER][1]
        )

        # === SPLAT BOUNDS ===
        splat_x_range = self.state.splat_positions[:, 0].max() - self.state.splat_positions[:, 0].min()
        splat_y_range = self.state.splat_positions[:, 1].max() - self.state.splat_positions[:, 1].min()

        # === STORE METRICS ===
        self.state.calibration_metrics = CalibrationMetrics(
            shoulder_width_3d=shoulder_width_3d,
            torso_height_3d=torso_height_3d,
            body_center_3d=body_center_3d.copy(),
            shoulder_width_screen=shoulder_width_screen,
            torso_height_screen=torso_height_screen,
            body_center_screen=body_center_screen.copy(),
            splat_width=splat_x_range,
            splat_height=splat_y_range,
            frame_width=image_shape[1] if image_shape else 1280,
            frame_height=image_shape[0] if image_shape else 720
        )

        # Keep deprecated fields for backwards compatibility
        self.state.calibration_body_center = body_center_3d.copy()
        self.state.calibration_body_scale = shoulder_width_3d

        logger.debug(f"  Calibration metrics:")
        logger.debug(f"    Shoulder width (3D): {shoulder_width_3d:.3f}")
        logger.debug(f"    Shoulder width (screen): {shoulder_width_screen:.3f}")
        logger.debug(f"    Torso height (3D): {torso_height_3d:.3f}")
        logger.debug(f"    Splat bounds: {splat_x_range:.2f} x {splat_y_range:.2f}")

        # Compute skinning weights
        self.state.skinning_weights = self.weight_assigner.compute_weights(
            self.state.splat_positions,
            landmarks_3d_centered
        )

        # Create animator
        self.state.animator = create_animator_from_calibration(
            self.state.splat_positions,
            self.state.skinning_weights,
            landmarks_3d_centered,
            self.weight_assigner.bone_names
        )

        self.state.is_calibrated = True
        self.state.calibration_time = time.time() - start_time
        self.state.current_positions = self.state.splat_positions.copy()

        logger.info(f"Calibration complete in {self.state.calibration_time:.2f}s")
        logger.info(f"  Weights shape: {self.state.skinning_weights.shape}")

        return True

    def animate(
        self,
        current_landmarks: np.ndarray,
        depth_map: np.ndarray = None,
        image_shape: Tuple[int, int] = None
    ) -> np.ndarray:
        """
        Animate splats with current pose.

        Called every frame during try-on.

        Args:
            current_landmarks: (33, 3) current MediaPipe landmarks
            depth_map: Optional depth map for z-estimation
            image_shape: (H, W) of current frame

        Returns:
            (N, 3) transformed splat positions
        """
        if not self.state.is_calibrated:
            logger.warning("Not calibrated, returning original positions")
            return self.state.splat_positions

        start_time = time.time()

        # Convert landmarks to 3D
        current_3d = self.weight_assigner.convert_landmarks_to_3d(
            current_landmarks,
            depth_map=depth_map,
            image_shape=image_shape,
            depth_scale=self.depth_scale
        )

        # Animate
        self.state.current_positions = self.state.animator.animate(
            self.state.skinning_weights,
            current_3d,
            use_gpu=self.use_gpu
        )

        self.state.last_animation_time = time.time() - start_time
        self.state.frame_count += 1

        return self.state.current_positions

    def get_stats(self) -> Dict:
        """Get current pipeline statistics"""
        fps = 1.0 / self.state.last_animation_time if self.state.last_animation_time > 0 else 0

        return {
            'is_calibrated': self.state.is_calibrated,
            'num_splats': len(self.state.splat_positions) if self.state.splat_positions is not None else 0,
            'generation_time_ms': self.state.generation_time * 1000,
            'calibration_time_ms': self.state.calibration_time * 1000,
            'animation_time_ms': self.state.last_animation_time * 1000,
            'animation_fps': fps,
            'frame_count': self.state.frame_count,
            'use_gpu': self.use_gpu
        }

    def save_state(self, output_path: str):
        """Save current calibration state for later use"""
        if not self.state.is_calibrated:
            logger.warning("Cannot save: not calibrated")
            return

        np.savez(
            output_path,
            splat_positions=self.state.splat_positions,
            splat_colors=self.state.splat_colors,
            calibration_landmarks=self.state.calibration_landmarks,
            skinning_weights=self.state.skinning_weights,
            bone_names=self.weight_assigner.bone_names
        )
        logger.info(f"Saved state to {output_path}")

    def load_state(self, state_path: str) -> bool:
        """Load previously saved calibration state"""
        try:
            data = np.load(state_path, allow_pickle=True)

            self.state.splat_positions = data['splat_positions']
            self.state.splat_colors = data['splat_colors']
            self.state.calibration_landmarks = data['calibration_landmarks']
            self.state.skinning_weights = data['skinning_weights']
            bone_names = list(data['bone_names'])

            # Recreate animator
            landmarks_3d = self.weight_assigner.convert_landmarks_to_3d(
                self.state.calibration_landmarks
            )
            self.state.animator = create_animator_from_calibration(
                self.state.splat_positions,
                self.state.skinning_weights,
                landmarks_3d,
                bone_names
            )

            self.state.is_calibrated = True
            self.state.current_positions = self.state.splat_positions.copy()

            logger.info(f"Loaded state from {state_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False

    def _load_ply(self, path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load positions and colors from PLY file.

        Note: This is a simplified loader. For production, use a proper
        PLY library like plyfile or open3d.
        """
        import struct

        positions = []
        colors = []

        with open(path, 'rb') as f:
            # Read header
            header_lines = []
            while True:
                line = f.readline().decode('ascii').strip()
                header_lines.append(line)
                if line == 'end_header':
                    break

            # Parse header for vertex count
            num_vertices = 0
            for line in header_lines:
                if line.startswith('element vertex'):
                    num_vertices = int(line.split()[-1])
                    break

            # Read binary data
            # Format: x y z nx ny nz f_dc_0 f_dc_1 f_dc_2 f_rest[45] opacity scale[3] rot[4]
            # Total: 3 + 3 + 3 + 45 + 1 + 3 + 4 = 62 floats per vertex
            floats_per_vertex = 62
            SH_C0 = 0.28209479177387814

            for _ in range(num_vertices):
                data = struct.unpack('<' + 'f' * floats_per_vertex,
                                    f.read(4 * floats_per_vertex))

                # Position
                positions.append([data[0], data[1], data[2]])

                # Color from SH DC component (indices 6, 7, 8)
                r = data[6] * SH_C0 + 0.5
                g = data[7] * SH_C0 + 0.5
                b = data[8] * SH_C0 + 0.5
                colors.append([
                    np.clip(r, 0, 1),
                    np.clip(g, 0, 1),
                    np.clip(b, 0, 1)
                ])

        return np.array(positions, dtype=np.float32), np.array(colors, dtype=np.float32)


# Demo/test
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    print("\n" + "=" * 60)
    print("GAUSSIAN TRY-ON PIPELINE TEST")
    print("=" * 60)

    # Initialize pipeline
    pipeline = GaussianTryOnPipeline(
        use_depth=True,
        use_gpu=True,
        num_splats=10000
    )

    # Test with existing PLY or generate new
    test_image = Path(__file__).parent / "test_images" / "clothing_test.png"
    test_ply = Path(__file__).parent / "output" / "clothing_test_20260311_203213.ply"

    if test_ply.exists():
        print(f"\nLoading existing PLY: {test_ply}")
        pipeline.load_from_ply(str(test_ply))
    elif test_image.exists():
        print(f"\nGenerating from image: {test_image}")
        result = pipeline.generate_from_image(str(test_image))
        if not result['success']:
            print("Generation failed!")
            sys.exit(1)
    else:
        print("No test files found. Creating synthetic data...")
        # Create synthetic splats for testing
        np.random.seed(42)
        num_splats = 10000
        pipeline.state.splat_positions = np.column_stack([
            np.random.uniform(-1, 1, num_splats),
            np.random.uniform(-1, 1, num_splats),
            np.random.randn(num_splats) * 0.1
        ]).astype(np.float32)
        pipeline.state.splat_colors = np.random.rand(num_splats, 3).astype(np.float32)

    # Create synthetic T-pose landmarks
    print("\nCreating synthetic T-pose landmarks...")
    t_pose = np.zeros((33, 3), dtype=np.float32)
    t_pose[0] = [0.5, 0.1, 0.0]    # Nose
    t_pose[11] = [0.35, 0.25, 0.0]  # Left shoulder
    t_pose[12] = [0.65, 0.25, 0.0]  # Right shoulder
    t_pose[13] = [0.15, 0.25, 0.0]  # Left elbow (T-pose)
    t_pose[14] = [0.85, 0.25, 0.0]  # Right elbow
    t_pose[15] = [0.0, 0.25, 0.0]   # Left wrist
    t_pose[16] = [1.0, 0.25, 0.0]   # Right wrist
    t_pose[23] = [0.40, 0.55, 0.0]  # Left hip
    t_pose[24] = [0.60, 0.55, 0.0]  # Right hip
    t_pose[25] = [0.40, 0.75, 0.0]  # Left knee
    t_pose[26] = [0.60, 0.75, 0.0]  # Right knee
    t_pose[27] = [0.40, 0.95, 0.0]  # Left ankle
    t_pose[28] = [0.60, 0.95, 0.0]  # Right ankle

    # Calibrate
    print("\nCalibrating with T-pose...")
    pipeline.calibrate(t_pose)

    # Create animation pose (bent arm)
    print("\nCreating animation pose (bent arm)...")
    current_pose = t_pose.copy()
    current_pose[13] = [0.25, 0.15, 0.0]  # Elbow bent
    current_pose[15] = [0.35, 0.05, 0.0]  # Wrist raised

    # Benchmark animation
    print("\nRunning animation benchmark...")
    num_frames = 100

    # Warmup
    for _ in range(5):
        pipeline.animate(current_pose)

    # Benchmark
    start = time.time()
    for i in range(num_frames):
        # Simulate varying pose
        pose = current_pose.copy()
        pose[13][1] += 0.05 * np.sin(i * 0.1)  # Oscillate elbow
        transformed = pipeline.animate(pose)
    total_time = time.time() - start

    # Print stats
    stats = pipeline.get_stats()
    print("\n" + "-" * 40)
    print("PIPELINE STATS")
    print("-" * 40)
    print(f"Splats:              {stats['num_splats']}")
    print(f"Calibrated:          {stats['is_calibrated']}")
    print(f"Generation time:     {stats['generation_time_ms']:.1f} ms")
    print(f"Calibration time:    {stats['calibration_time_ms']:.1f} ms")
    print(f"Animation time:      {stats['animation_time_ms']:.2f} ms")
    print(f"Animation FPS:       {stats['animation_fps']:.0f}")
    print(f"GPU enabled:         {stats['use_gpu']}")
    print(f"\nBenchmark ({num_frames} frames):")
    print(f"  Total time:        {total_time:.2f}s")
    print(f"  Average FPS:       {num_frames / total_time:.0f}")
    print(f"  Per-frame time:    {total_time / num_frames * 1000:.2f} ms")

    # Save state for later use
    state_path = Path(__file__).parent / "output" / "tryon_state.npz"
    pipeline.save_state(str(state_path))
    print(f"\nSaved state to: {state_path}")
