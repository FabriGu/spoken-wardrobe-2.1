"""
MediaPipe Pose Tracker for Spoken Wardrobe

Provides RGB-only pose detection using MediaPipe Tasks API (PoseLandmarker).
This replaces OAK-D BlazePose, eliminating the depth camera dependency.

The interface is designed to be compatible with the existing BoneRotationCalculator,
which expects a body object with landmarks_world attribute.

Usage:
    from src.pose import MediaPipePoseTracker

    tracker = MediaPipePoseTracker()

    # In main loop:
    frame = camera.read()
    body = tracker.process_frame(frame)
    if body:
        bone_rotations = bone_calculator.compute_bone_rotations(body)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass, field

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Model path - download if not present
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "pose_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"


@dataclass
class PoseBody:
    """
    Container for pose landmarks compatible with BoneRotationCalculator.

    Provides landmarks_world attribute as a list of [x, y, z] coordinates
    for all 33 MediaPipe pose landmarks.

    Coordinate system (MediaPipe world landmarks):
        - Origin at hip center
        - X: positive = right
        - Y: positive = DOWN (important: opposite to Three.js!)
        - Z: positive = toward camera
    """
    landmarks_world: List[List[float]]
    landmarks_normalized: Optional[List[List[float]]] = None
    visibility: Optional[List[float]] = None

    # Convenience accessors for key landmarks
    @property
    def left_shoulder(self) -> Optional[List[float]]:
        return self.landmarks_world[11] if len(self.landmarks_world) > 11 else None

    @property
    def right_shoulder(self) -> Optional[List[float]]:
        return self.landmarks_world[12] if len(self.landmarks_world) > 12 else None

    @property
    def left_hip(self) -> Optional[List[float]]:
        return self.landmarks_world[23] if len(self.landmarks_world) > 23 else None

    @property
    def right_hip(self) -> Optional[List[float]]:
        return self.landmarks_world[24] if len(self.landmarks_world) > 24 else None


class MediaPipePoseTracker:
    """
    MediaPipe pose tracker using the Tasks API (PoseLandmarker).

    Provides the same interface as OAK-D BlazePose tracker for easy replacement.
    Uses RGB-only detection - no depth camera required.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        static_image_mode: bool = False
    ):
        """
        Initialize the pose tracker.

        Args:
            model_path: Path to pose_landmarker.task model file
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for landmark tracking
            static_image_mode: If True, treat each frame as independent image
        """
        if model_path is None:
            model_path = str(DEFAULT_MODEL_PATH)

        self.model_path = Path(model_path)

        # Download model if not present
        if not self.model_path.exists():
            self._download_model()

        # Configure pose landmarker
        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        running_mode = VisionRunningMode.IMAGE if static_image_mode else VisionRunningMode.VIDEO

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=running_mode,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False
        )

        self.landmarker = PoseLandmarker.create_from_options(options)
        self.static_image_mode = static_image_mode
        self._frame_timestamp_ms = 0

        print(f"[MediaPipePoseTracker] Initialized with model: {self.model_path}")

    def _download_model(self):
        """Download the pose landmarker model if not present."""
        import urllib.request

        print(f"[MediaPipePoseTracker] Downloading model from {MODEL_URL}...")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            urllib.request.urlretrieve(MODEL_URL, str(self.model_path))
            print(f"[MediaPipePoseTracker] Model downloaded to {self.model_path}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download pose landmarker model: {e}\n"
                f"Please download manually from:\n{MODEL_URL}\n"
                f"And save to: {self.model_path}"
            )

    def process_frame(self, frame: np.ndarray) -> Optional[PoseBody]:
        """
        Process a video frame and return pose landmarks.

        Args:
            frame: BGR image from OpenCV (np.ndarray)

        Returns:
            PoseBody object with landmarks_world, or None if no pose detected
        """
        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Run detection
        if self.static_image_mode:
            results = self.landmarker.detect(mp_image)
        else:
            self._frame_timestamp_ms += 33  # ~30fps
            results = self.landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        # Check if pose detected
        if not results.pose_landmarks or len(results.pose_landmarks) == 0:
            return None

        # Extract world landmarks (3D coordinates in meters)
        if results.pose_world_landmarks and len(results.pose_world_landmarks) > 0:
            world_landmarks = results.pose_world_landmarks[0]
            landmarks_world = [
                [lm.x, lm.y, lm.z] for lm in world_landmarks
            ]
        else:
            # Fallback to normalized landmarks if world not available
            landmarks = results.pose_landmarks[0]
            landmarks_world = [
                [lm.x, lm.y, lm.z] for lm in landmarks
            ]

        # Extract normalized landmarks
        landmarks = results.pose_landmarks[0]
        landmarks_normalized = [
            [lm.x, lm.y, lm.z] for lm in landmarks
        ]

        # Extract visibility scores
        visibility = [lm.visibility for lm in landmarks]

        return PoseBody(
            landmarks_world=landmarks_world,
            landmarks_normalized=landmarks_normalized,
            visibility=visibility
        )

    def next_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[PoseBody]]:
        """
        Process frame and return (frame, body) tuple.

        This method provides compatibility with the OAK-D tracker interface.

        Args:
            frame: BGR image from OpenCV

        Returns:
            Tuple of (frame, PoseBody or None)
        """
        body = self.process_frame(frame)
        return frame, body

    def draw_landmarks(
        self,
        frame: np.ndarray,
        body: Optional[PoseBody],
        draw_connections: bool = True
    ) -> np.ndarray:
        """
        Draw pose landmarks on frame.

        Args:
            frame: BGR image
            body: PoseBody with landmarks
            draw_connections: Whether to draw bone connections

        Returns:
            Frame with landmarks drawn
        """
        if body is None or body.landmarks_normalized is None:
            return frame

        output = frame.copy()
        h, w = output.shape[:2]

        # Draw landmarks
        for i, lm in enumerate(body.landmarks_normalized):
            x = int(lm[0] * w)
            y = int(lm[1] * h)

            # Color based on visibility
            vis = body.visibility[i] if body.visibility else 1.0
            color = (0, int(255 * vis), int(255 * (1 - vis)))

            cv2.circle(output, (x, y), 4, color, -1)

        # Draw connections
        if draw_connections:
            connections = [
                (11, 12),  # shoulders
                (11, 13), (13, 15),  # left arm
                (12, 14), (14, 16),  # right arm
                (11, 23), (12, 24),  # torso
                (23, 24),  # hips
                (23, 25), (25, 27),  # left leg
                (24, 26), (26, 28),  # right leg
            ]

            for start_idx, end_idx in connections:
                if start_idx < len(body.landmarks_normalized) and end_idx < len(body.landmarks_normalized):
                    start = body.landmarks_normalized[start_idx]
                    end = body.landmarks_normalized[end_idx]

                    x1, y1 = int(start[0] * w), int(start[1] * h)
                    x2, y2 = int(end[0] * w), int(end[1] * h)

                    cv2.line(output, (x1, y1), (x2, y2), (0, 255, 0), 2)

        return output

    def close(self):
        """Release resources."""
        if hasattr(self, 'landmarker'):
            self.landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_mediapipe_tracker():
    """Test the MediaPipe tracker with webcam."""
    print("Testing MediaPipe Pose Tracker...")
    print("Press 'q' to quit")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera")
        return

    tracker = MediaPipePoseTracker()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame, body = tracker.next_frame(frame)

            if body:
                frame = tracker.draw_landmarks(frame, body)

                # Display landmark info
                cv2.putText(frame, "Pose detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Show sample world landmark (left shoulder)
                ls = body.landmarks_world[11]
                cv2.putText(frame, f"L.Shoulder: ({ls[0]:.2f}, {ls[1]:.2f}, {ls[2]:.2f})",
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            else:
                cv2.putText(frame, "No pose detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("MediaPipe Pose Test", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        tracker.close()


if __name__ == "__main__":
    test_mediapipe_tracker()
