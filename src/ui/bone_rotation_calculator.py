"""
Bone Rotation Calculator for Spoken Wardrobe

Converts BlazePose 33 landmarks into 9 bone rotations (quaternions) for
skeletal animation in Three.js.

The 9 bones match the pre-rigged body mesh structure:
    1. spine           - mid_hips → mid_shoulders
    2. left_upper_arm  - left_shoulder → left_elbow
    3. left_lower_arm  - left_elbow → left_wrist
    4. right_upper_arm - right_shoulder → right_elbow
    5. right_lower_arm - right_elbow → right_wrist
    6. left_upper_leg  - left_hip → left_knee
    7. left_lower_leg  - left_knee → left_ankle
    8. right_upper_leg - right_hip → right_knee
    9. right_lower_leg - right_knee → right_ankle

Coordinate Systems:
    - BlazePose world: Y-DOWN, Z toward camera (origin at mid-hips)
      (negative Y = above hips, positive Y = below hips)
    - Three.js: Y-up, Z toward camera
    - Transform: Flip Y axis (negate x and z quaternion components)

Usage:
    from src.ui.bone_rotation_calculator import BoneRotationCalculator

    calculator = BoneRotationCalculator()
    body = tracker.next_frame()[1]
    bone_rotations = calculator.compute_bone_rotations(body)
    # bone_rotations = {'spine': {'x': 0, 'y': 0.1, 'z': 0, 'w': 0.99}, ...}
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple


class BoneRotationCalculator:
    """
    Converts BlazePose landmarks to 9 bone rotation quaternions.

    Each bone rotation represents the rotation from the T-pose reference
    to the current pose, expressed as a quaternion {x, y, z, w}.
    """

    # BlazePose landmark indices
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    # Bone names matching the GLB armature (case-sensitive)
    BONE_NAMES = [
        'spine',
        'left_upper_arm', 'left_lower_arm',
        'right_upper_arm', 'right_lower_arm',
        'left_upper_leg', 'left_lower_leg',
        'right_upper_leg', 'right_lower_leg'
    ]

    # T-pose reference vectors (normalized directions in local space)
    # These represent the "rest pose" direction for each bone
    T_POSE_DIRECTIONS = {
        'spine': np.array([0, 1, 0]),           # Pointing up
        'left_upper_arm': np.array([-1, 0, 0]),  # Pointing left
        'left_lower_arm': np.array([-1, 0, 0]),  # Pointing left
        'right_upper_arm': np.array([1, 0, 0]),  # Pointing right
        'right_lower_arm': np.array([1, 0, 0]),  # Pointing right
        'left_upper_leg': np.array([0, -1, 0]),  # Pointing down
        'left_lower_leg': np.array([0, -1, 0]),  # Pointing down
        'right_upper_leg': np.array([0, -1, 0]), # Pointing down
        'right_lower_leg': np.array([0, -1, 0]), # Pointing down
    }

    def __init__(self, smoothing_factor: float = 0.3, debug: bool = False):
        """
        Initialize the bone rotation calculator.

        Args:
            smoothing_factor: Factor for exponential smoothing (0-1, higher = smoother)
            debug: If True, print debug information to console
        """
        self.smoothing_factor = smoothing_factor
        self.debug = debug
        self._prev_rotations: Optional[Dict[str, Dict[str, float]]] = None

    def compute_bone_rotations(self, body) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Compute rotation quaternions for all 9 bones from BlazePose landmarks.

        Args:
            body: BlazePose Body object with landmarks_world attribute

        Returns:
            Dictionary mapping bone_name → quaternion {x, y, z, w},
            or None if landmarks not available
        """
        if body is None or not hasattr(body, 'landmarks_world'):
            return None

        lm = body.landmarks_world
        if lm is None or len(lm) < 29:  # Need up to ankle (index 28)
            return None

        try:
            rotations = {}

            # --- SPINE ---
            # Direction from mid-hips to mid-shoulders
            mid_hips = self._midpoint(lm[self.LEFT_HIP], lm[self.RIGHT_HIP])
            mid_shoulders = self._midpoint(lm[self.LEFT_SHOULDER], lm[self.RIGHT_SHOULDER])
            spine_dir = self._normalize(mid_shoulders - mid_hips)
            rotations['spine'] = self._direction_to_quaternion(
                spine_dir, self.T_POSE_DIRECTIONS['spine']
            )

            # --- LEFT ARM ---
            left_upper_arm_dir = self._normalize(
                np.array(lm[self.LEFT_ELBOW]) - np.array(lm[self.LEFT_SHOULDER])
            )
            rotations['left_upper_arm'] = self._direction_to_quaternion(
                left_upper_arm_dir, self.T_POSE_DIRECTIONS['left_upper_arm']
            )

            left_lower_arm_dir = self._normalize(
                np.array(lm[self.LEFT_WRIST]) - np.array(lm[self.LEFT_ELBOW])
            )
            rotations['left_lower_arm'] = self._direction_to_quaternion(
                left_lower_arm_dir, self.T_POSE_DIRECTIONS['left_lower_arm']
            )

            # --- RIGHT ARM ---
            right_upper_arm_dir = self._normalize(
                np.array(lm[self.RIGHT_ELBOW]) - np.array(lm[self.RIGHT_SHOULDER])
            )
            rotations['right_upper_arm'] = self._direction_to_quaternion(
                right_upper_arm_dir, self.T_POSE_DIRECTIONS['right_upper_arm']
            )

            right_lower_arm_dir = self._normalize(
                np.array(lm[self.RIGHT_WRIST]) - np.array(lm[self.RIGHT_ELBOW])
            )
            rotations['right_lower_arm'] = self._direction_to_quaternion(
                right_lower_arm_dir, self.T_POSE_DIRECTIONS['right_lower_arm']
            )

            # --- LEFT LEG ---
            left_upper_leg_dir = self._normalize(
                np.array(lm[self.LEFT_KNEE]) - np.array(lm[self.LEFT_HIP])
            )
            rotations['left_upper_leg'] = self._direction_to_quaternion(
                left_upper_leg_dir, self.T_POSE_DIRECTIONS['left_upper_leg']
            )

            left_lower_leg_dir = self._normalize(
                np.array(lm[self.LEFT_ANKLE]) - np.array(lm[self.LEFT_KNEE])
            )
            rotations['left_lower_leg'] = self._direction_to_quaternion(
                left_lower_leg_dir, self.T_POSE_DIRECTIONS['left_lower_leg']
            )

            # --- RIGHT LEG ---
            right_upper_leg_dir = self._normalize(
                np.array(lm[self.RIGHT_KNEE]) - np.array(lm[self.RIGHT_HIP])
            )
            rotations['right_upper_leg'] = self._direction_to_quaternion(
                right_upper_leg_dir, self.T_POSE_DIRECTIONS['right_upper_leg']
            )

            right_lower_leg_dir = self._normalize(
                np.array(lm[self.RIGHT_ANKLE]) - np.array(lm[self.RIGHT_KNEE])
            )
            rotations['right_lower_leg'] = self._direction_to_quaternion(
                right_lower_leg_dir, self.T_POSE_DIRECTIONS['right_lower_leg']
            )

            # Apply coordinate transform: BlazePose Y-down → Three.js Y-up
            for bone_name in rotations:
                rotations[bone_name] = self._transform_to_threejs(rotations[bone_name])

            # Apply smoothing
            if self._prev_rotations is not None:
                rotations = self._smooth_rotations(rotations)

            self._prev_rotations = rotations

            if self.debug:
                self._print_debug(rotations)

            return rotations

        except (IndexError, TypeError, ValueError) as e:
            if self.debug:
                print(f"[BoneRotationCalculator] Error: {e}")
            return None

    def _midpoint(self, p1, p2) -> np.ndarray:
        """Compute midpoint between two points."""
        return (np.array(p1) + np.array(p2)) / 2

    def _normalize(self, v: np.ndarray) -> np.ndarray:
        """Normalize a vector, returning zero vector if length is zero."""
        length = np.linalg.norm(v)
        if length < 1e-8:
            return np.array([0, 0, 0])
        return v / length

    def _direction_to_quaternion(self, current_dir: np.ndarray,
                                  reference_dir: np.ndarray) -> Dict[str, float]:
        """
        Compute quaternion rotation from reference direction to current direction.

        Uses the axis-angle representation: rotation axis = cross product,
        rotation angle = arccos of dot product.

        Args:
            current_dir: Current bone direction (normalized)
            reference_dir: T-pose reference direction (normalized)

        Returns:
            Quaternion as {x, y, z, w}
        """
        # Handle zero-length vectors
        if np.linalg.norm(current_dir) < 1e-8:
            return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}

        # Normalize inputs
        current_dir = self._normalize(current_dir)
        reference_dir = self._normalize(reference_dir)

        # Compute rotation axis (cross product)
        axis = np.cross(reference_dir, current_dir)
        axis_length = np.linalg.norm(axis)

        # Handle parallel vectors (no rotation needed)
        if axis_length < 1e-8:
            # Check if same or opposite direction
            dot = np.dot(reference_dir, current_dir)
            if dot > 0:
                # Same direction - identity quaternion
                return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}
            else:
                # Opposite direction - 180° rotation around any perpendicular axis
                perp = self._get_perpendicular(reference_dir)
                return {'x': float(perp[0]), 'y': float(perp[1]),
                        'z': float(perp[2]), 'w': 0.0}

        # Normalize axis
        axis = axis / axis_length

        # Compute angle (clamped to valid range for arccos)
        dot = np.clip(np.dot(reference_dir, current_dir), -1.0, 1.0)
        angle = np.arccos(dot)

        # Convert axis-angle to quaternion: q = (sin(θ/2)*axis, cos(θ/2))
        half_angle = angle / 2
        sin_half = np.sin(half_angle)
        cos_half = np.cos(half_angle)

        return {
            'x': float(axis[0] * sin_half),
            'y': float(axis[1] * sin_half),
            'z': float(axis[2] * sin_half),
            'w': float(cos_half)
        }

    def _get_perpendicular(self, v: np.ndarray) -> np.ndarray:
        """Get a unit vector perpendicular to v."""
        if abs(v[0]) < 0.9:
            return self._normalize(np.cross(v, np.array([1, 0, 0])))
        else:
            return self._normalize(np.cross(v, np.array([0, 1, 0])))

    def _transform_to_threejs(self, quat: Dict[str, float]) -> Dict[str, float]:
        """
        Transform quaternion from BlazePose coordinate system to Three.js.

        BlazePose world: Y-DOWN, X-right, Z-toward camera
        Three.js:        Y-UP, X-right, Z-toward camera

        To flip Y axis for a quaternion, we negate the x and z components
        (the rotation axis components that are affected by the Y-flip).
        """
        return {
            'x': float(-quat['x']),  # Flip around Y axis
            'y': float(quat['y']),
            'z': float(-quat['z']),  # Flip around Y axis
            'w': float(quat['w'])
        }

    def _smooth_rotations(self, new_rotations: Dict[str, Dict[str, float]]
                          ) -> Dict[str, Dict[str, float]]:
        """
        Apply exponential smoothing to reduce jitter.

        Uses SLERP-like behavior by linearly interpolating quaternion components
        and renormalizing.
        """
        alpha = 1.0 - self.smoothing_factor
        smoothed = {}

        for bone_name, new_q in new_rotations.items():
            if bone_name in self._prev_rotations:
                prev_q = self._prev_rotations[bone_name]

                # Linear interpolation of quaternion components
                smoothed_q = {
                    'x': alpha * new_q['x'] + self.smoothing_factor * prev_q['x'],
                    'y': alpha * new_q['y'] + self.smoothing_factor * prev_q['y'],
                    'z': alpha * new_q['z'] + self.smoothing_factor * prev_q['z'],
                    'w': alpha * new_q['w'] + self.smoothing_factor * prev_q['w'],
                }

                # Renormalize quaternion
                length = np.sqrt(
                    smoothed_q['x']**2 + smoothed_q['y']**2 +
                    smoothed_q['z']**2 + smoothed_q['w']**2
                )
                if length > 1e-8:
                    smoothed_q = {k: v / length for k, v in smoothed_q.items()}

                smoothed[bone_name] = smoothed_q
            else:
                smoothed[bone_name] = new_q

        return smoothed

    def _print_debug(self, rotations: Dict[str, Dict[str, float]]):
        """Print debug information about computed rotations."""
        print("\n[BoneRotationCalculator] Bone Rotations:")
        for bone_name in self.BONE_NAMES:
            if bone_name in rotations:
                q = rotations[bone_name]
                # Convert to axis-angle for readability
                angle = 2 * np.arccos(np.clip(q['w'], -1, 1))
                angle_deg = np.degrees(angle)
                print(f"  {bone_name:18s}: angle={angle_deg:6.1f}° "
                      f"q=({q['x']:+.3f}, {q['y']:+.3f}, {q['z']:+.3f}, {q['w']:+.3f})")

    def reset(self):
        """Reset smoothing state."""
        self._prev_rotations = None


# Test function for standalone testing
def test_bone_rotation_calculator():
    """Test the calculator with mock landmarks."""
    print("Testing BoneRotationCalculator...")

    calculator = BoneRotationCalculator(debug=True)

    # Create mock body with T-pose landmarks
    class MockBody:
        def __init__(self):
            # T-pose landmarks (Y-down coordinate system)
            self.landmarks_world = [None] * 33

            # Shoulders at y=0.4, hips at y=0.0 (relative, Y-down)
            self.landmarks_world[11] = [-0.2, 0.4, 0]   # left_shoulder
            self.landmarks_world[12] = [0.2, 0.4, 0]    # right_shoulder
            self.landmarks_world[23] = [-0.1, 0.0, 0]   # left_hip
            self.landmarks_world[24] = [0.1, 0.0, 0]    # right_hip

            # Arms extended horizontally (T-pose)
            self.landmarks_world[13] = [-0.5, 0.4, 0]   # left_elbow
            self.landmarks_world[14] = [0.5, 0.4, 0]    # right_elbow
            self.landmarks_world[15] = [-0.8, 0.4, 0]   # left_wrist
            self.landmarks_world[16] = [0.8, 0.4, 0]    # right_wrist

            # Legs straight down
            self.landmarks_world[25] = [-0.1, -0.4, 0]  # left_knee
            self.landmarks_world[26] = [0.1, -0.4, 0]   # right_knee
            self.landmarks_world[27] = [-0.1, -0.8, 0]  # left_ankle
            self.landmarks_world[28] = [0.1, -0.8, 0]   # right_ankle

    # Test T-pose (should produce identity-ish rotations)
    print("\n=== T-POSE TEST ===")
    body = MockBody()
    rotations = calculator.compute_bone_rotations(body)

    if rotations:
        print("T-pose rotations computed successfully!")
        # In T-pose, rotations should be close to identity (w ≈ 1, xyz ≈ 0)
    else:
        print("ERROR: Failed to compute T-pose rotations")

    # Test with arm raised
    print("\n=== ARM RAISED TEST ===")
    body.landmarks_world[13] = [-0.4, 0.7, 0]   # left_elbow raised
    body.landmarks_world[15] = [-0.3, 1.0, 0]   # left_wrist raised
    calculator.reset()
    rotations = calculator.compute_bone_rotations(body)

    if rotations:
        print("Arm raised rotations computed successfully!")
    else:
        print("ERROR: Failed to compute arm raised rotations")


if __name__ == "__main__":
    test_bone_rotation_calculator()
