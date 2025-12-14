"""
Mesh Calibrator for Spoken Wardrobe

Computes mesh position, scale, and rotation from BlazePose body landmarks.
This enables accurate alignment of generated 3D clothing meshes with the
user's body in real-time.

BlazePose Landmark Reference (33 landmarks):
    0: nose
    11: left_shoulder, 12: right_shoulder
    13: left_elbow, 14: right_elbow
    15: left_wrist, 16: right_wrist
    23: left_hip, 24: right_hip
    25: left_knee, 26: right_knee

Coordinate Systems:
    - BlazePose world coords: meters, Y-DOWN, origin at mid-hips
      (negative Y = above hips, positive Y = below hips)
    - Three.js coords: meters, Y-up, Z toward camera
    - Transform: three_y = -blazepose_y

Usage:
    from src.ui.mesh_calibrator import MeshCalibrator

    calibrator = MeshCalibrator()

    # Get transform from body landmarks
    body = tracker.next_frame()[1]
    if body and body.landmarks_world is not None:
        transform = calibrator.compute_transform(body)
        # transform = {'position': {x, y, z}, 'scale': float, 'rotation': {x, y, z}}

    # Validate A-pose
    if calibrator.validate_a_pose(body):
        print("User is in valid A-pose")
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple


class MeshCalibrator:
    """
    Computes mesh transform from BlazePose landmarks for accurate body alignment.

    Attributes:
        reference_shoulder_width: Average human shoulder width in meters (for scale reference)
        smoothing_factor: Factor for exponential smoothing of transform updates
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

    def __init__(self, reference_shoulder_width: float = 0.4,
                 smoothing_factor: float = 0.3):
        """
        Initialize the mesh calibrator.

        Args:
            reference_shoulder_width: Reference shoulder width in meters for scale calculation
            smoothing_factor: Smoothing factor for transform updates (0-1, higher = more smoothing)
        """
        self.reference_shoulder_width = reference_shoulder_width
        self.smoothing_factor = smoothing_factor

        # Previous transform for smoothing
        self._prev_transform: Optional[Dict[str, Any]] = None

        # Calibration offset (set during A-pose capture)
        self._calibration_offset = np.array([0.0, 0.0, 0.0])

    def compute_transform(self, body, apply_smoothing: bool = True) -> Optional[Dict[str, Any]]:
        """
        Compute mesh position, scale, and rotation from body landmarks.

        Uses shoulder and hip landmarks to determine:
        - Position: Center of torso (average of shoulders and hips)
        - Scale: Based on shoulder width ratio to reference
        - Rotation: Y-axis rotation based on shoulder line orientation

        Args:
            body: BlazePose Body object with landmarks_world attribute
            apply_smoothing: Whether to apply exponential smoothing

        Returns:
            Dictionary with position (x,y,z), scale (float), rotation (x,y,z radians),
            or None if landmarks not available
        """
        if body is None or not hasattr(body, 'landmarks_world'):
            return None

        lm = body.landmarks_world
        if lm is None or len(lm) < 25:
            return None

        try:
            # Extract key landmarks
            left_shoulder = np.array(lm[self.LEFT_SHOULDER])
            right_shoulder = np.array(lm[self.RIGHT_SHOULDER])
            left_hip = np.array(lm[self.LEFT_HIP])
            right_hip = np.array(lm[self.RIGHT_HIP])

            # 1. Compute body center (mid-torso)
            mid_shoulders = (left_shoulder + right_shoulder) / 2
            mid_hips = (left_hip + right_hip) / 2
            body_center = (mid_shoulders + mid_hips) / 2

            # Apply calibration offset
            body_center = body_center - self._calibration_offset

            # 2. Compute scale from shoulder width
            shoulder_width = np.linalg.norm(left_shoulder - right_shoulder)
            scale_factor = shoulder_width / self.reference_shoulder_width

            # Clamp scale to reasonable range
            scale_factor = np.clip(scale_factor, 0.5, 2.0)

            # 3. Compute Y-axis rotation from shoulder line
            shoulder_vec = right_shoulder - left_shoulder
            y_rotation = float(np.arctan2(shoulder_vec[2], shoulder_vec[0]))

            # 4. Get depth from body xyz if available
            if hasattr(body, 'xyz') and body.xyz is not None:
                depth = body.xyz[2] / 1000  # Convert mm to meters
            else:
                depth = 2.0  # Default depth

            # Build transform dict
            transform = {
                'position': {
                    'x': float(body_center[0]),
                    'y': float(-body_center[1]),  # Flip Y: BlazePose Y-down → Three.js Y-up
                    'z': float(depth)
                },
                'scale': float(scale_factor),
                'rotation': {
                    'x': 0.0,
                    'y': float(y_rotation),
                    'z': 0.0
                }
            }

            # Apply smoothing if enabled and we have a previous transform
            if apply_smoothing and self._prev_transform is not None:
                transform = self._smooth_transform(transform)

            self._prev_transform = transform
            return transform

        except (IndexError, TypeError, ValueError) as e:
            print(f"[MeshCalibrator] Error computing transform: {e}")
            return None

    def _smooth_transform(self, new_transform: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply exponential smoothing to reduce jitter.

        Args:
            new_transform: New computed transform

        Returns:
            Smoothed transform
        """
        alpha = 1.0 - self.smoothing_factor

        smoothed = {
            'position': {
                'x': alpha * new_transform['position']['x'] +
                     self.smoothing_factor * self._prev_transform['position']['x'],
                'y': alpha * new_transform['position']['y'] +
                     self.smoothing_factor * self._prev_transform['position']['y'],
                'z': alpha * new_transform['position']['z'] +
                     self.smoothing_factor * self._prev_transform['position']['z'],
            },
            'scale': alpha * new_transform['scale'] +
                     self.smoothing_factor * self._prev_transform['scale'],
            'rotation': {
                'x': alpha * new_transform['rotation']['x'] +
                     self.smoothing_factor * self._prev_transform['rotation']['x'],
                'y': alpha * new_transform['rotation']['y'] +
                     self.smoothing_factor * self._prev_transform['rotation']['y'],
                'z': alpha * new_transform['rotation']['z'] +
                     self.smoothing_factor * self._prev_transform['rotation']['z'],
            }
        }

        return smoothed

    def calibrate_offset(self, body) -> bool:
        """
        Set calibration offset from current body position.

        Call this when the user is in the desired reference position (e.g., A-pose).
        The offset will be subtracted from future transform calculations.

        Args:
            body: BlazePose Body object

        Returns:
            True if calibration was successful
        """
        if body is None or not hasattr(body, 'landmarks_world'):
            return False

        lm = body.landmarks_world
        if lm is None or len(lm) < 25:
            return False

        try:
            # Compute current body center
            mid_shoulders = (np.array(lm[self.LEFT_SHOULDER]) +
                           np.array(lm[self.RIGHT_SHOULDER])) / 2
            mid_hips = (np.array(lm[self.LEFT_HIP]) +
                       np.array(lm[self.RIGHT_HIP])) / 2
            body_center = (mid_shoulders + mid_hips) / 2

            # Set as offset (so this position becomes origin)
            self._calibration_offset = body_center
            print(f"[MeshCalibrator] Calibration offset set: {self._calibration_offset}")
            return True

        except (IndexError, TypeError) as e:
            print(f"[MeshCalibrator] Calibration failed: {e}")
            return False

    def validate_a_pose(self, body, arm_threshold: float = 0.4) -> Dict[str, Any]:
        """
        Check if the user is in a valid A-pose (arms extended at ~45 degrees).

        In A-pose:
        - Arms should be extended outward (not at sides)
        - Arms should be below shoulder level (not T-pose)
        - Both arms should be relatively symmetric

        Args:
            body: BlazePose Body object
            arm_threshold: Maximum allowed arm angle ratio for valid A-pose

        Returns:
            Dictionary with:
            - valid: Boolean indicating if pose is valid
            - left_ratio: Left arm angle ratio
            - right_ratio: Right arm angle ratio
            - message: Description of pose status
        """
        if body is None or not hasattr(body, 'landmarks_world'):
            return {'valid': False, 'left_ratio': 0, 'right_ratio': 0,
                    'message': 'No body detected'}

        lm = body.landmarks_world
        if lm is None or len(lm) < 17:
            return {'valid': False, 'left_ratio': 0, 'right_ratio': 0,
                    'message': 'Insufficient landmarks'}

        try:
            # Get arm vectors (wrist - shoulder)
            left_arm = np.array(lm[self.LEFT_WRIST]) - np.array(lm[self.LEFT_SHOULDER])
            right_arm = np.array(lm[self.RIGHT_WRIST]) - np.array(lm[self.RIGHT_SHOULDER])

            # Calculate arm angle ratios (vertical / horizontal)
            # Low ratio = more horizontal (arms extended)
            left_ratio = abs(left_arm[1]) / (abs(left_arm[0]) + 0.001)
            right_ratio = abs(right_arm[1]) / (abs(right_arm[0]) + 0.001)

            # Check if both arms are extended (low vertical component)
            left_valid = left_ratio < arm_threshold
            right_valid = right_ratio < arm_threshold
            valid = left_valid and right_valid

            # Generate message
            if valid:
                message = "Good A-pose!"
            elif not left_valid and not right_valid:
                message = "Extend both arms outward"
            elif not left_valid:
                message = "Extend left arm outward"
            else:
                message = "Extend right arm outward"

            return {
                'valid': valid,
                'left_ratio': float(left_ratio),
                'right_ratio': float(right_ratio),
                'message': message
            }

        except (IndexError, TypeError, ValueError) as e:
            return {'valid': False, 'left_ratio': 0, 'right_ratio': 0,
                    'message': f'Error: {e}'}

    def get_torso_bounds(self, body) -> Optional[Dict[str, float]]:
        """
        Get the bounding box of the torso region for mask alignment.

        Args:
            body: BlazePose Body object

        Returns:
            Dictionary with top, bottom, left, right bounds (in normalized coords),
            or None if landmarks not available
        """
        if body is None or not hasattr(body, 'landmarks'):
            return None

        lm = body.landmarks  # Use screen-space landmarks
        if lm is None or len(lm) < 25:
            return None

        try:
            # Get shoulder and hip landmarks (screen coords)
            left_shoulder = lm[self.LEFT_SHOULDER]
            right_shoulder = lm[self.RIGHT_SHOULDER]
            left_hip = lm[self.LEFT_HIP]
            right_hip = lm[self.RIGHT_HIP]

            # Calculate bounds
            left = min(left_shoulder[0], left_hip[0])
            right = max(right_shoulder[0], right_hip[0])
            top = min(left_shoulder[1], right_shoulder[1])
            bottom = max(left_hip[1], right_hip[1])

            return {
                'left': float(left),
                'right': float(right),
                'top': float(top),
                'bottom': float(bottom),
                'width': float(right - left),
                'height': float(bottom - top)
            }

        except (IndexError, TypeError) as e:
            return None

    def reset(self):
        """Reset calibration and smoothing state."""
        self._prev_transform = None
        self._calibration_offset = np.array([0.0, 0.0, 0.0])
