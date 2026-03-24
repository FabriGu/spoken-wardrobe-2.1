#!/usr/bin/env python3
"""
Gaussian Weight Assigner - Calibration-Time Weight Assignment

Assigns skinning weights to Gaussian splats based on proximity to
MediaPipe/BlazePose body landmarks. Called once at calibration time
when user aligns in T-pose.

The user's skeleton at calibration becomes the "invisible rigged mesh"
that drives splat animation.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger('GaussianWeightAssigner')


@dataclass
class Bone:
    """Represents a bone defined by two landmark indices"""
    name: str
    start_idx: int  # MediaPipe landmark index for bone start
    end_idx: int    # MediaPipe landmark index for bone end
    sigma: float = 0.15  # Gaussian falloff radius (adjustable per bone)


# BlazePose/MediaPipe landmark indices
# Reference: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
LANDMARK_NAMES = {
    0: 'nose',
    11: 'left_shoulder',
    12: 'right_shoulder',
    13: 'left_elbow',
    14: 'right_elbow',
    15: 'left_wrist',
    16: 'right_wrist',
    23: 'left_hip',
    24: 'right_hip',
    25: 'left_knee',
    26: 'right_knee',
    27: 'left_ankle',
    28: 'right_ankle',
}


# Define bones for clothing animation (focus on torso and upper body)
DEFAULT_BONES = [
    # Spine/Torso (virtual bones for torso rigidity)
    Bone('spine', 11, 23, sigma=0.20),      # Left shoulder to left hip
    Bone('spine_r', 12, 24, sigma=0.20),    # Right shoulder to right hip

    # Arms
    Bone('left_upper_arm', 11, 13, sigma=0.12),   # Shoulder to elbow
    Bone('right_upper_arm', 12, 14, sigma=0.12),
    Bone('left_lower_arm', 13, 15, sigma=0.10),   # Elbow to wrist
    Bone('right_lower_arm', 14, 16, sigma=0.10),

    # Legs (for pants/skirts)
    Bone('left_upper_leg', 23, 25, sigma=0.15),   # Hip to knee
    Bone('right_upper_leg', 24, 26, sigma=0.15),
    Bone('left_lower_leg', 25, 27, sigma=0.12),   # Knee to ankle
    Bone('right_lower_leg', 26, 28, sigma=0.12),

    # Shoulders (for sleeve attachment)
    Bone('shoulders', 11, 12, sigma=0.18),  # Left to right shoulder

    # Hips (for waistband)
    Bone('hips', 23, 24, sigma=0.16),       # Left to right hip
]


class GaussianWeightAssigner:
    """
    Assigns skinning weights to Gaussian splats based on proximity to bones.

    Uses Gaussian falloff: w = exp(-(d/σ)²) where d is distance to bone
    and σ controls the influence radius.

    Weights are normalized so each splat's weights sum to 1.0.
    """

    def __init__(self, bones: List[Bone] = None, min_weight: float = 0.001):
        """
        Initialize weight assigner.

        Args:
            bones: List of bones to use. Defaults to DEFAULT_BONES.
            min_weight: Minimum weight threshold. Weights below this are zeroed.
        """
        self.bones = bones or DEFAULT_BONES
        self.min_weight = min_weight
        self.bone_names = [b.name for b in self.bones]
        logger.info(f"Weight assigner initialized with {len(self.bones)} bones")

    def compute_weights(
        self,
        splat_positions: np.ndarray,
        landmarks_3d: np.ndarray,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Compute skinning weights for all splats.

        Args:
            splat_positions: (N, 3) array of splat 3D positions
            landmarks_3d: (33, 3) array of MediaPipe 3D landmarks (x, y, z)
            normalize: If True, normalize weights to sum to 1.0 per splat

        Returns:
            (N, num_bones) array of skinning weights
        """
        num_splats = len(splat_positions)
        num_bones = len(self.bones)
        weights = np.zeros((num_splats, num_bones), dtype=np.float32)

        logger.debug(f"Computing weights for {num_splats} splats, {num_bones} bones")

        for bone_idx, bone in enumerate(self.bones):
            # Get bone endpoints from landmarks
            p0 = landmarks_3d[bone.start_idx]  # Bone start
            p1 = landmarks_3d[bone.end_idx]    # Bone end

            # Compute distance from each splat to this bone segment
            distances = self._point_to_segment_distance(
                splat_positions, p0, p1
            )

            # Apply Gaussian falloff: w = exp(-(d/σ)²)
            bone_weights = np.exp(-np.square(distances / bone.sigma))

            # Threshold small weights
            bone_weights[bone_weights < self.min_weight] = 0.0

            weights[:, bone_idx] = bone_weights

        if normalize:
            # Normalize weights so each splat's weights sum to 1.0
            weight_sums = weights.sum(axis=1, keepdims=True)
            # Avoid division by zero for splats far from all bones
            weight_sums = np.maximum(weight_sums, 1e-8)
            weights = weights / weight_sums

        # Log stats
        active_per_splat = (weights > 0).sum(axis=1)
        logger.debug(f"  Average bones per splat: {active_per_splat.mean():.2f}")
        logger.debug(f"  Max bones per splat: {active_per_splat.max()}")
        logger.debug(f"  Splats with no bones: {(active_per_splat == 0).sum()}")

        return weights

    def _point_to_segment_distance(
        self,
        points: np.ndarray,
        p0: np.ndarray,
        p1: np.ndarray
    ) -> np.ndarray:
        """
        Compute shortest distance from points to a line segment.

        Uses parametric projection: finds closest point on segment [p0, p1]
        and returns distance to that point.

        Args:
            points: (N, 3) array of points
            p0: (3,) start of segment
            p1: (3,) end of segment

        Returns:
            (N,) array of distances
        """
        # Segment vector
        v = p1 - p0
        segment_length_sq = np.dot(v, v)

        if segment_length_sq < 1e-10:
            # Degenerate segment (p0 == p1), just distance to point
            return np.linalg.norm(points - p0, axis=1)

        # Projection parameter t: closest point = p0 + t * v
        # t is clamped to [0, 1] to stay on segment
        t = np.dot(points - p0, v) / segment_length_sq
        t = np.clip(t, 0.0, 1.0)

        # Closest point on segment for each input point
        closest = p0 + t[:, np.newaxis] * v

        # Distance to closest point
        return np.linalg.norm(points - closest, axis=1)

    def convert_landmarks_to_3d(
        self,
        landmarks_2d: np.ndarray,
        depth_map: np.ndarray = None,
        image_shape: Tuple[int, int] = None,
        default_depth: float = 0.0,
        depth_scale: float = 0.5
    ) -> np.ndarray:
        """
        Convert MediaPipe 2D landmarks (normalized) to 3D coordinates.

        If depth_map is provided, samples depth at each landmark location.
        Otherwise uses the landmark's z-value (distance from camera).

        Args:
            landmarks_2d: (33, 3) array of landmarks with (x, y, z) where
                          x, y are normalized [0,1] and z is relative depth
            depth_map: Optional (H, W) depth map to sample from
            image_shape: (H, W) of the original image
            default_depth: Default z value if no depth available
            depth_scale: Scale factor for depth values

        Returns:
            (33, 3) array of 3D coordinates in splat space (centered at 0)
        """
        landmarks_3d = np.zeros((33, 3), dtype=np.float32)

        for i, lm in enumerate(landmarks_2d):
            # Convert normalized [0,1] to centered [-1, 1]
            x = (lm[0] - 0.5) * 2.0
            y = (0.5 - lm[1]) * 2.0  # Flip Y for OpenGL convention

            # Get depth
            if depth_map is not None and image_shape is not None:
                # Sample depth map at landmark position
                h, w = image_shape
                px = int(np.clip(lm[0] * w, 0, w - 1))
                py = int(np.clip(lm[1] * h, 0, h - 1))
                z = (depth_map[py, px] - 0.5) * depth_scale
            else:
                # Use MediaPipe's z estimate (distance from camera)
                # MediaPipe z is roughly in meters, normalize it
                z = lm[2] * depth_scale if len(lm) > 2 else default_depth

            landmarks_3d[i] = [x, y, z]

        return landmarks_3d

    def save_weights(
        self,
        weights: np.ndarray,
        output_path: str,
        bone_names: List[str] = None
    ):
        """
        Save weights to numpy file for later use.

        Args:
            weights: (N, num_bones) weight array
            output_path: Path to save .npz file
            bone_names: Optional list of bone names (uses self.bone_names if None)
        """
        bone_names = bone_names or self.bone_names
        np.savez(
            output_path,
            weights=weights,
            bone_names=bone_names
        )
        logger.info(f"Saved weights to {output_path}")

    def load_weights(self, input_path: str) -> Tuple[np.ndarray, List[str]]:
        """
        Load weights from numpy file.

        Args:
            input_path: Path to .npz file

        Returns:
            Tuple of (weights array, bone names list)
        """
        data = np.load(input_path, allow_pickle=True)
        weights = data['weights']
        bone_names = list(data['bone_names'])
        logger.info(f"Loaded weights from {input_path}: {weights.shape}")
        return weights, bone_names


def assign_weights_from_calibration(
    splat_positions: np.ndarray,
    calibration_landmarks: np.ndarray,
    depth_map: np.ndarray = None,
    image_shape: Tuple[int, int] = None,
    depth_scale: float = 0.5
) -> Tuple[np.ndarray, GaussianWeightAssigner]:
    """
    High-level function to assign weights during T-pose calibration.

    This is the main entry point called when user strikes A/T-pose.

    Args:
        splat_positions: (N, 3) array of splat positions
        calibration_landmarks: (33, 3) MediaPipe landmarks from calibration frame
        depth_map: Optional depth map for better z-estimation
        image_shape: (H, W) of calibration frame
        depth_scale: Scale for depth values

    Returns:
        Tuple of (weights array, assigner object for later use)
    """
    assigner = GaussianWeightAssigner()

    # Convert landmarks to 3D splat space
    landmarks_3d = assigner.convert_landmarks_to_3d(
        calibration_landmarks,
        depth_map=depth_map,
        image_shape=image_shape,
        depth_scale=depth_scale
    )

    # Compute weights
    weights = assigner.compute_weights(splat_positions, landmarks_3d)

    logger.info(f"Assigned weights: {weights.shape} ({weights.nbytes / 1024:.1f} KB)")

    return weights, assigner


# Test/demo
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # Generate test splat positions (10k splats in a plane)
    np.random.seed(42)
    num_splats = 10000
    splat_positions = np.column_stack([
        np.random.uniform(-1, 1, num_splats),  # X
        np.random.uniform(-1, 1, num_splats),  # Y
        np.random.randn(num_splats) * 0.1      # Z (small variation)
    ]).astype(np.float32)

    # Generate fake T-pose landmarks (approximate positions)
    # Using normalized coordinates [0, 1]
    fake_landmarks = np.zeros((33, 3), dtype=np.float32)

    # Head
    fake_landmarks[0] = [0.5, 0.1, 0.0]  # Nose

    # Shoulders
    fake_landmarks[11] = [0.35, 0.25, 0.0]  # Left shoulder
    fake_landmarks[12] = [0.65, 0.25, 0.0]  # Right shoulder

    # Elbows (T-pose: arms horizontal)
    fake_landmarks[13] = [0.15, 0.25, 0.0]  # Left elbow
    fake_landmarks[14] = [0.85, 0.25, 0.0]  # Right elbow

    # Wrists
    fake_landmarks[15] = [0.0, 0.25, 0.0]   # Left wrist
    fake_landmarks[16] = [1.0, 0.25, 0.0]   # Right wrist

    # Hips
    fake_landmarks[23] = [0.40, 0.55, 0.0]  # Left hip
    fake_landmarks[24] = [0.60, 0.55, 0.0]  # Right hip

    # Knees
    fake_landmarks[25] = [0.40, 0.75, 0.0]  # Left knee
    fake_landmarks[26] = [0.60, 0.75, 0.0]  # Right knee

    # Ankles
    fake_landmarks[27] = [0.40, 0.95, 0.0]  # Left ankle
    fake_landmarks[28] = [0.60, 0.95, 0.0]  # Right ankle

    print("\n" + "=" * 60)
    print("WEIGHT ASSIGNMENT TEST")
    print("=" * 60)

    weights, assigner = assign_weights_from_calibration(
        splat_positions,
        fake_landmarks
    )

    print(f"\nWeights shape: {weights.shape}")
    print(f"Bone names: {assigner.bone_names}")

    # Show weight distribution for a few bones
    for i, name in enumerate(assigner.bone_names[:5]):
        bone_weights = weights[:, i]
        print(f"\n{name}:")
        print(f"  Mean weight: {bone_weights.mean():.4f}")
        print(f"  Max weight:  {bone_weights.max():.4f}")
        print(f"  Non-zero:    {(bone_weights > 0).sum()}")

    # Save test weights
    assigner.save_weights(weights, "/tmp/test_weights.npz")

    # Verify load
    loaded_weights, loaded_names = assigner.load_weights("/tmp/test_weights.npz")
    print(f"\nLoaded weights match: {np.allclose(weights, loaded_weights)}")
