#!/usr/bin/env python3
"""
Gaussian Animator - Real-time Splat Animation with Dual Quaternion Skinning

Transforms Gaussian splat positions in real-time based on body tracking.
Uses Dual Quaternion Skinning (DQS) for smooth deformation without
volume loss artifacts common with Linear Blend Skinning (LBS).

Called every frame during try-on mode.
"""

import numpy as np
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
import time

logger = logging.getLogger('GaussianAnimator')


@dataclass
class DualQuaternion:
    """
    Dual Quaternion for rigid body transformation.

    A dual quaternion q = q_real + ε * q_dual represents both
    rotation (q_real) and translation (encoded in q_dual).

    Better than matrices for blending multiple transforms.
    """
    real: np.ndarray  # (4,) quaternion [w, x, y, z]
    dual: np.ndarray  # (4,) quaternion [w, x, y, z]

    @staticmethod
    def from_rotation_translation(
        rotation: np.ndarray,
        translation: np.ndarray
    ) -> 'DualQuaternion':
        """
        Create dual quaternion from rotation quaternion and translation vector.

        Args:
            rotation: (4,) quaternion [w, x, y, z]
            translation: (3,) translation vector

        Returns:
            DualQuaternion
        """
        # Real part is just the rotation
        q_real = rotation.copy()

        # Dual part: q_dual = 0.5 * t * q_real
        # where t is a pure quaternion [0, tx, ty, tz]
        t = np.array([0.0, translation[0], translation[1], translation[2]])
        q_dual = 0.5 * quaternion_multiply(t, q_real)

        return DualQuaternion(real=q_real, dual=q_dual)

    @staticmethod
    def identity() -> 'DualQuaternion':
        """Create identity dual quaternion (no transformation)"""
        return DualQuaternion(
            real=np.array([1.0, 0.0, 0.0, 0.0]),
            dual=np.array([0.0, 0.0, 0.0, 0.0])
        )

    def get_rotation(self) -> np.ndarray:
        """Extract rotation quaternion"""
        return self.real.copy()

    def get_translation(self) -> np.ndarray:
        """Extract translation vector"""
        # t = 2 * q_dual * conjugate(q_real)
        q_conj = quaternion_conjugate(self.real)
        t_quat = 2.0 * quaternion_multiply(self.dual, q_conj)
        return t_quat[1:4]  # [x, y, z]

    def normalize(self) -> 'DualQuaternion':
        """Normalize dual quaternion"""
        norm = np.linalg.norm(self.real)
        if norm > 1e-8:
            return DualQuaternion(
                real=self.real / norm,
                dual=self.dual / norm
            )
        return self

    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """
        Transform a 3D point using this dual quaternion.

        Args:
            point: (3,) position vector

        Returns:
            (3,) transformed position
        """
        # Method: p' = q * p * conjugate(q) for rotation
        # then add translation
        rotation = self.real
        translation = self.get_translation()

        # Rotate point using quaternion
        rotated = quaternion_rotate_point(rotation, point)

        # Add translation
        return rotated + translation


def quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """
    Multiply two quaternions [w, x, y, z].

    Args:
        q1, q2: (4,) quaternions

    Returns:
        (4,) result quaternion
    """
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2

    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ])


def quaternion_conjugate(q: np.ndarray) -> np.ndarray:
    """Quaternion conjugate: negate imaginary parts"""
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quaternion_rotate_point(q: np.ndarray, p: np.ndarray) -> np.ndarray:
    """
    Rotate a point using a quaternion.

    Uses: p' = q * p * conjugate(q)

    Args:
        q: (4,) unit quaternion [w, x, y, z]
        p: (3,) point

    Returns:
        (3,) rotated point
    """
    # Convert point to quaternion form [0, x, y, z]
    p_quat = np.array([0.0, p[0], p[1], p[2]])

    # q * p * q*
    q_conj = quaternion_conjugate(q)
    result = quaternion_multiply(quaternion_multiply(q, p_quat), q_conj)

    return result[1:4]  # Return xyz


def blend_dual_quaternions(
    dqs: List[DualQuaternion],
    weights: np.ndarray
) -> DualQuaternion:
    """
    Blend multiple dual quaternions with weights (DLB - Dual Linear Blending).

    Args:
        dqs: List of dual quaternions
        weights: (N,) array of weights (should sum to 1)

    Returns:
        Blended dual quaternion
    """
    # Ensure all quaternions are in same hemisphere (flip if needed)
    # to avoid shortest path issues
    reference = dqs[0].real
    blended_real = np.zeros(4)
    blended_dual = np.zeros(4)

    for dq, w in zip(dqs, weights):
        if w < 1e-8:
            continue

        real = dq.real
        dual = dq.dual

        # Flip if in opposite hemisphere
        if np.dot(reference, real) < 0:
            real = -real
            dual = -dual

        blended_real += w * real
        blended_dual += w * dual

    return DualQuaternion(real=blended_real, dual=blended_dual).normalize()


class GaussianAnimator:
    """
    Real-time Gaussian splat animator using Dual Quaternion Skinning.

    Workflow:
    1. At calibration: store rest pose (T-pose) bone transforms
    2. Each frame: compute relative transforms and apply to splats
    """

    def __init__(self, bone_names: List[str]):
        """
        Initialize animator.

        Args:
            bone_names: List of bone names (must match weight assigner)
        """
        self.bone_names = bone_names
        self.num_bones = len(bone_names)

        # Rest pose transforms (set during calibration)
        self.rest_transforms: Optional[List[DualQuaternion]] = None
        self.rest_positions: Optional[np.ndarray] = None

        # Pre-allocated arrays for performance
        self._transformed_positions = None

        logger.info(f"Animator initialized with {self.num_bones} bones")

    def set_rest_pose(
        self,
        rest_positions: np.ndarray,
        rest_landmarks: np.ndarray
    ):
        """
        Set the rest pose (T-pose) from calibration.

        Args:
            rest_positions: (N, 3) splat positions at rest
            rest_landmarks: (33, 3) MediaPipe landmarks at calibration (3D)
        """
        self.rest_positions = rest_positions.copy()
        self.rest_transforms = self._compute_bone_transforms(rest_landmarks)

        # Pre-allocate output array
        self._transformed_positions = np.empty_like(rest_positions)

        logger.info(f"Rest pose set: {len(rest_positions)} splats")

    def _compute_bone_transforms(
        self,
        landmarks_3d: np.ndarray
    ) -> List[DualQuaternion]:
        """
        Compute bone transforms from landmarks.

        Each bone transform is defined by the bone's midpoint (translation)
        and orientation (rotation from parent).

        Args:
            landmarks_3d: (33, 3) 3D landmarks

        Returns:
            List of DualQuaternion transforms
        """
        transforms = []

        # Bone definitions (must match weight assigner)
        bone_defs = [
            (11, 23),  # spine
            (12, 24),  # spine_r
            (11, 13),  # left_upper_arm
            (12, 14),  # right_upper_arm
            (13, 15),  # left_lower_arm
            (14, 16),  # right_lower_arm
            (23, 25),  # left_upper_leg
            (24, 26),  # right_upper_leg
            (25, 27),  # left_lower_leg
            (26, 28),  # right_lower_leg
            (11, 12),  # shoulders
            (23, 24),  # hips
        ]

        for start_idx, end_idx in bone_defs:
            p0 = landmarks_3d[start_idx]
            p1 = landmarks_3d[end_idx]

            # Bone midpoint as translation
            midpoint = (p0 + p1) / 2.0

            # Bone direction
            bone_dir = p1 - p0
            bone_len = np.linalg.norm(bone_dir)

            if bone_len > 1e-6:
                bone_dir = bone_dir / bone_len

                # Compute rotation from reference direction to bone direction
                # Reference: bones initially point along Y axis
                ref_dir = np.array([0.0, -1.0, 0.0])
                rotation = self._rotation_between_vectors(ref_dir, bone_dir)
            else:
                rotation = np.array([1.0, 0.0, 0.0, 0.0])

            dq = DualQuaternion.from_rotation_translation(rotation, midpoint)
            transforms.append(dq)

        return transforms

    def _rotation_between_vectors(
        self,
        v1: np.ndarray,
        v2: np.ndarray
    ) -> np.ndarray:
        """
        Compute quaternion rotation from v1 to v2.

        Args:
            v1, v2: (3,) normalized vectors

        Returns:
            (4,) quaternion [w, x, y, z]
        """
        v1 = v1 / (np.linalg.norm(v1) + 1e-8)
        v2 = v2 / (np.linalg.norm(v2) + 1e-8)

        dot = np.clip(np.dot(v1, v2), -1.0, 1.0)

        if dot > 0.9999:
            # Vectors are nearly parallel
            return np.array([1.0, 0.0, 0.0, 0.0])

        if dot < -0.9999:
            # Vectors are nearly opposite - use arbitrary perpendicular axis
            axis = np.cross(np.array([1.0, 0.0, 0.0]), v1)
            if np.linalg.norm(axis) < 0.01:
                axis = np.cross(np.array([0.0, 1.0, 0.0]), v1)
            axis = axis / np.linalg.norm(axis)
            return np.array([0.0, axis[0], axis[1], axis[2]])

        # General case
        axis = np.cross(v1, v2)
        axis = axis / (np.linalg.norm(axis) + 1e-8)

        half_angle = np.arccos(dot) / 2.0
        s = np.sin(half_angle)
        c = np.cos(half_angle)

        return np.array([c, axis[0]*s, axis[1]*s, axis[2]*s])

    def animate(
        self,
        weights: np.ndarray,
        current_landmarks: np.ndarray,
        use_gpu: bool = False
    ) -> np.ndarray:
        """
        Animate splats based on current pose.

        Args:
            weights: (N, num_bones) skinning weights
            current_landmarks: (33, 3) current MediaPipe landmarks (3D)
            use_gpu: If True, use GPU acceleration (requires PyTorch)

        Returns:
            (N, 3) transformed splat positions
        """
        if self.rest_transforms is None:
            raise RuntimeError("Rest pose not set. Call set_rest_pose first.")

        start_time = time.time()

        # Compute current bone transforms
        current_transforms = self._compute_bone_transforms(current_landmarks)

        # Compute relative transforms (current relative to rest)
        relative_transforms = self._compute_relative_transforms(
            self.rest_transforms, current_transforms
        )

        if use_gpu:
            return self._animate_gpu(weights, relative_transforms)
        else:
            return self._animate_cpu(weights, relative_transforms)

    def _compute_relative_transforms(
        self,
        rest: List[DualQuaternion],
        current: List[DualQuaternion]
    ) -> List[DualQuaternion]:
        """
        Compute relative transforms: current * inverse(rest)
        """
        relative = []
        for rest_dq, curr_dq in zip(rest, current):
            # Relative rotation: curr_rot * conjugate(rest_rot)
            rel_rot = quaternion_multiply(
                curr_dq.real,
                quaternion_conjugate(rest_dq.real)
            )

            # Relative translation
            rel_trans = curr_dq.get_translation() - rest_dq.get_translation()

            relative.append(DualQuaternion.from_rotation_translation(
                rel_rot, rel_trans
            ))

        return relative

    def _animate_cpu(
        self,
        weights: np.ndarray,
        transforms: List[DualQuaternion]
    ) -> np.ndarray:
        """
        CPU implementation of DQS animation.

        Args:
            weights: (N, num_bones) weights
            transforms: List of relative bone transforms

        Returns:
            (N, 3) transformed positions
        """
        num_splats = len(self.rest_positions)
        output = self._transformed_positions

        for i in range(num_splats):
            pos = self.rest_positions[i]
            w = weights[i]

            # Gather active bones for this splat
            active_dqs = []
            active_weights = []

            for bone_idx in range(self.num_bones):
                if w[bone_idx] > 1e-6:
                    active_dqs.append(transforms[bone_idx])
                    active_weights.append(w[bone_idx])

            if len(active_dqs) == 0:
                # No bones affect this splat, keep original position
                output[i] = pos
            elif len(active_dqs) == 1:
                # Single bone, direct transform
                output[i] = active_dqs[0].transform_point(pos)
            else:
                # Blend multiple bones
                blended = blend_dual_quaternions(
                    active_dqs, np.array(active_weights)
                )
                output[i] = blended.transform_point(pos)

        return output

    def _animate_gpu(
        self,
        weights: np.ndarray,
        transforms: List[DualQuaternion]
    ) -> np.ndarray:
        """
        GPU implementation using PyTorch for parallel computation.

        Significantly faster for large splat counts (10k+).
        """
        try:
            import torch

            # Detect device
            if torch.backends.mps.is_available():
                device = torch.device('mps')
            elif torch.cuda.is_available():
                device = torch.device('cuda')
            else:
                # Fall back to CPU
                return self._animate_cpu(weights, transforms)

            # Convert to tensors
            positions = torch.tensor(
                self.rest_positions, dtype=torch.float32, device=device
            )
            weights_t = torch.tensor(weights, dtype=torch.float32, device=device)

            # Stack transforms into tensors
            # Shape: (num_bones, 4) for real and dual parts
            real_parts = torch.tensor(
                np.stack([t.real for t in transforms]),
                dtype=torch.float32, device=device
            )
            dual_parts = torch.tensor(
                np.stack([t.dual for t in transforms]),
                dtype=torch.float32, device=device
            )

            # Compute blended dual quaternions for all splats at once
            # (N, num_bones) @ (num_bones, 4) -> (N, 4)
            blended_real = torch.matmul(weights_t, real_parts)
            blended_dual = torch.matmul(weights_t, dual_parts)

            # Normalize
            norms = torch.norm(blended_real, dim=1, keepdim=True).clamp(min=1e-8)
            blended_real = blended_real / norms
            blended_dual = blended_dual / norms

            # Extract rotation and translation
            # Translation: t = 2 * dual * conjugate(real)
            real_conj = blended_real * torch.tensor(
                [1.0, -1.0, -1.0, -1.0], device=device
            )

            # Quaternion multiply: dual * real_conj
            t_quat = self._batch_quat_multiply(blended_dual, real_conj)
            translations = 2.0 * t_quat[:, 1:4]

            # Rotate positions using blended rotation quaternions
            rotated = self._batch_quat_rotate(blended_real, positions)

            # Add translation
            output = rotated + translations

            return output.cpu().numpy()

        except ImportError:
            logger.warning("PyTorch not available, falling back to CPU")
            return self._animate_cpu(weights, transforms)

    def _batch_quat_multiply(
        self,
        q1: 'torch.Tensor',
        q2: 'torch.Tensor'
    ) -> 'torch.Tensor':
        """Batch quaternion multiplication"""
        w1, x1, y1, z1 = q1[:, 0], q1[:, 1], q1[:, 2], q1[:, 3]
        w2, x2, y2, z2 = q2[:, 0], q2[:, 1], q2[:, 2], q2[:, 3]

        import torch
        return torch.stack([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ], dim=1)

    def _batch_quat_rotate(
        self,
        q: 'torch.Tensor',
        p: 'torch.Tensor'
    ) -> 'torch.Tensor':
        """Batch quaternion rotation of points"""
        import torch

        # Convert points to quaternion form [0, x, y, z]
        zeros = torch.zeros(p.shape[0], 1, device=p.device)
        p_quat = torch.cat([zeros, p], dim=1)

        # Conjugate of q
        q_conj = q * torch.tensor([1.0, -1.0, -1.0, -1.0], device=q.device)

        # q * p * q_conj
        temp = self._batch_quat_multiply(q, p_quat)
        result = self._batch_quat_multiply(temp, q_conj)

        return result[:, 1:4]


def create_animator_from_calibration(
    splat_positions: np.ndarray,
    weights: np.ndarray,
    calibration_landmarks: np.ndarray,
    bone_names: List[str]
) -> GaussianAnimator:
    """
    Create and configure animator from calibration data.

    Args:
        splat_positions: (N, 3) splat positions
        weights: (N, num_bones) skinning weights
        calibration_landmarks: (33, 3) landmarks from T-pose calibration
        bone_names: List of bone names

    Returns:
        Configured GaussianAnimator ready for animation
    """
    animator = GaussianAnimator(bone_names)
    animator.set_rest_pose(splat_positions, calibration_landmarks)
    return animator


# Test/demo
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # Generate test data
    np.random.seed(42)
    num_splats = 1000
    num_bones = 12

    # Random splat positions
    splat_positions = np.column_stack([
        np.random.uniform(-1, 1, num_splats),
        np.random.uniform(-1, 1, num_splats),
        np.random.randn(num_splats) * 0.1
    ]).astype(np.float32)

    # Random weights (normalized)
    weights = np.random.rand(num_splats, num_bones).astype(np.float32)
    weights = weights / weights.sum(axis=1, keepdims=True)

    # Fake T-pose landmarks
    rest_landmarks = np.zeros((33, 3), dtype=np.float32)
    rest_landmarks[11] = [-0.3, -0.5, 0.0]  # Left shoulder
    rest_landmarks[12] = [0.3, -0.5, 0.0]   # Right shoulder
    rest_landmarks[13] = [-0.7, -0.5, 0.0]  # Left elbow
    rest_landmarks[14] = [0.7, -0.5, 0.0]   # Right elbow
    rest_landmarks[15] = [-1.0, -0.5, 0.0]  # Left wrist
    rest_landmarks[16] = [1.0, -0.5, 0.0]   # Right wrist
    rest_landmarks[23] = [-0.2, 0.1, 0.0]   # Left hip
    rest_landmarks[24] = [0.2, 0.1, 0.0]    # Right hip
    rest_landmarks[25] = [-0.2, 0.5, 0.0]   # Left knee
    rest_landmarks[26] = [0.2, 0.5, 0.0]    # Right knee
    rest_landmarks[27] = [-0.2, 0.9, 0.0]   # Left ankle
    rest_landmarks[28] = [0.2, 0.9, 0.0]    # Right ankle

    # Pose with bent arm
    current_landmarks = rest_landmarks.copy()
    current_landmarks[13] = [-0.5, -0.3, 0.0]  # Elbow raised
    current_landmarks[15] = [-0.5, -0.1, 0.0]  # Wrist raised

    bone_names = [
        'spine', 'spine_r', 'left_upper_arm', 'right_upper_arm',
        'left_lower_arm', 'right_lower_arm', 'left_upper_leg',
        'right_upper_leg', 'left_lower_leg', 'right_lower_leg',
        'shoulders', 'hips'
    ]

    print("\n" + "=" * 60)
    print("GAUSSIAN ANIMATOR TEST")
    print("=" * 60)

    # Create animator
    animator = create_animator_from_calibration(
        splat_positions, weights, rest_landmarks, bone_names
    )

    # Test CPU animation
    start = time.time()
    for _ in range(10):
        output_cpu = animator.animate(weights, current_landmarks, use_gpu=False)
    cpu_time = (time.time() - start) / 10

    print(f"\nCPU animation time: {cpu_time * 1000:.2f}ms per frame")
    print(f"Output shape: {output_cpu.shape}")
    print(f"Position delta (mean): {np.mean(np.abs(output_cpu - splat_positions)):.4f}")

    # Test GPU animation
    start = time.time()
    for _ in range(10):
        output_gpu = animator.animate(weights, current_landmarks, use_gpu=True)
    gpu_time = (time.time() - start) / 10

    print(f"\nGPU animation time: {gpu_time * 1000:.2f}ms per frame")
    print(f"Speedup: {cpu_time / gpu_time:.1f}x")

    # Verify outputs match
    if np.allclose(output_cpu, output_gpu, rtol=1e-4, atol=1e-5):
        print("\nCPU and GPU outputs match!")
    else:
        diff = np.abs(output_cpu - output_gpu).max()
        print(f"\nMax difference between CPU/GPU: {diff:.6f}")
