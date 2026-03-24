#!/usr/bin/env python3
"""
Live Gaussian Splat Try-On Demo

Real-time virtual try-on using:
- Webcam or OAK-D camera
- MediaPipe/BlazePose for body tracking
- Gaussian Splat animation pipeline

Controls:
- SPACE: Start 3-2-1 countdown for calibration
- R: Reset calibration
- G: Generate new splat from image
- L: Load existing splat
- Q/ESC: Quit
- +/-: Adjust splat scale
- D: Toggle landmark display
"""

import os
import sys
import cv2
import time
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import pipeline components
from gaussian_test.gaussian_tryon_pipeline import GaussianTryOnPipeline

logger = logging.getLogger('LiveTryOn')


class DemoState(Enum):
    """Current state of the demo"""
    INITIALIZING = "initializing"
    NO_SPLAT = "no_splat"
    WAITING_FOR_BODY = "waiting_for_body"
    READY_TO_CALIBRATE = "ready_to_calibrate"
    COUNTDOWN = "countdown"  # New: countdown before calibration
    LIVE_TRYON = "live_tryon"
    ERROR = "error"


@dataclass
class DemoConfig:
    """Demo configuration"""
    camera_id: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    use_oak_d: bool = False
    splat_scale: float = 1.0
    show_landmarks: bool = True
    show_skeleton: bool = True
    show_fps: bool = True
    countdown_seconds: int = 3  # Countdown duration before calibration


class PoseDetector:
    """Wrapper for MediaPipe pose detection"""

    def __init__(self):
        import mediapipe as mp
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Store last results for drawing
        self._last_results = None

        logger.info("MediaPipe Pose initialized")

    def detect(self, frame_rgb: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect pose landmarks.

        Args:
            frame_rgb: RGB frame

        Returns:
            (33, 3) array of landmarks or None if no body detected
        """
        results = self.pose.process(frame_rgb)

        # Store results for later drawing
        self._last_results = results

        if results.pose_landmarks is None:
            return None

        # Extract landmarks as numpy array for pipeline
        landmarks = np.array([
            [lm.x, lm.y, lm.z]
            for lm in results.pose_landmarks.landmark
        ], dtype=np.float32)

        return landmarks

    def draw_landmarks(self, frame: np.ndarray, landmarks: np.ndarray = None) -> np.ndarray:
        """
        Draw pose landmarks on frame.

        Uses the original MediaPipe results object for proper drawing.
        The landmarks parameter is ignored - we use stored results.
        """
        if self._last_results is None or self._last_results.pose_landmarks is None:
            return frame

        self.mp_drawing.draw_landmarks(
            frame,
            self._last_results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
        )

        return frame


class LiveTryOnDemo:
    """
    Live virtual try-on demonstration.

    Captures camera feed, detects body pose, and overlays
    animated Gaussian splats on the user.
    """

    def __init__(self, config: DemoConfig = None):
        self.config = config or DemoConfig()
        self.state = DemoState.INITIALIZING
        self.error_message = ""

        # Components
        self.camera = None
        self.pose_detector = None
        self.pipeline = None

        # State tracking
        self.current_landmarks = None
        self.countdown_start_time = None
        self.fps_history = []
        self.frame_count = 0

        # Splat rendering
        self.splat_positions_2d = None
        self.splat_colors = None

    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("Initializing live demo...")

            # Initialize camera
            logger.info(f"Opening camera {self.config.camera_id}...")
            self.camera = cv2.VideoCapture(self.config.camera_id)

            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency

            if not self.camera.isOpened():
                raise RuntimeError(f"Failed to open camera {self.config.camera_id}")

            # Read a few frames to warm up camera (macOS requirement)
            for _ in range(5):
                self.camera.read()

            # Get actual resolution
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info(f"Camera opened: {actual_width}x{actual_height}")

            # Initialize pose detector
            logger.info("Initializing pose detector...")
            self.pose_detector = PoseDetector()

            # Initialize pipeline
            logger.info("Initializing Gaussian pipeline...")
            self.pipeline = GaussianTryOnPipeline(
                use_depth=True,
                use_gpu=True,
                num_splats=10000
            )

            self.state = DemoState.NO_SPLAT
            logger.info("Initialization complete!")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.state = DemoState.ERROR
            self.error_message = str(e)
            return False

    def load_splat(self, ply_path: str) -> bool:
        """Load splat from PLY file"""
        if self.pipeline.load_from_ply(ply_path):
            self.splat_colors = self.pipeline.state.splat_colors
            self.state = DemoState.WAITING_FOR_BODY
            return True
        return False

    def generate_splat(self, image_path: str) -> bool:
        """Generate splat from clothing image"""
        result = self.pipeline.generate_from_image(image_path)
        if result['success']:
            self.splat_colors = self.pipeline.state.splat_colors
            self.state = DemoState.WAITING_FOR_BODY
            return True
        return False

    def check_t_pose(self, landmarks: np.ndarray) -> bool:
        """
        Check if user is in T-pose.

        T-pose criteria:
        - Arms extended horizontally (elbows at shoulder height)
        - Wrists at shoulder height
        - Arms straight (elbow between shoulder and wrist)
        """
        # Landmark indices
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_ELBOW = 13
        RIGHT_ELBOW = 14
        LEFT_WRIST = 15
        RIGHT_WRIST = 16

        # Get relevant landmarks
        ls = landmarks[LEFT_SHOULDER]
        rs = landmarks[RIGHT_SHOULDER]
        le = landmarks[LEFT_ELBOW]
        re = landmarks[RIGHT_ELBOW]
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]

        # Shoulder height (average y of shoulders)
        shoulder_height = (ls[1] + rs[1]) / 2

        # Check: elbows near shoulder height (within 15% of frame)
        elbow_height_ok = (
            abs(le[1] - shoulder_height) < 0.15 and
            abs(re[1] - shoulder_height) < 0.15
        )

        # Check: wrists near shoulder height
        wrist_height_ok = (
            abs(lw[1] - shoulder_height) < 0.15 and
            abs(rw[1] - shoulder_height) < 0.15
        )

        # Check: arms extended (wrists outside shoulders)
        arms_extended = (
            lw[0] < ls[0] - 0.1 and  # Left wrist left of left shoulder
            rw[0] > rs[0] + 0.1      # Right wrist right of right shoulder
        )

        return elbow_height_ok and wrist_height_ok and arms_extended

    def project_splats_to_2d(
        self,
        positions_3d: np.ndarray,
        landmarks: np.ndarray,
        frame_shape: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project 3D splat positions to 2D screen coordinates with proper scaling.

        Uses CalibrationMetrics for mathematically correct scaling:
        1. Compute scale factor based on body proportions
        2. Map splat coordinates to body region on screen
        3. Track body movement via delta from calibration

        Returns:
            Tuple of (positions_2d, sizes) where sizes are based on depth
        """
        height, width = frame_shape[:2]

        # Landmark indices
        LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
        LEFT_HIP, RIGHT_HIP = 23, 24

        # Current body metrics (in screen space [0,1])
        curr_shoulder_center = (landmarks[LEFT_SHOULDER][:2] + landmarks[RIGHT_SHOULDER][:2]) / 2
        curr_hip_center = (landmarks[LEFT_HIP][:2] + landmarks[RIGHT_HIP][:2]) / 2
        curr_body_center = (curr_shoulder_center + curr_hip_center) / 2
        curr_shoulder_width = abs(landmarks[RIGHT_SHOULDER][0] - landmarks[LEFT_SHOULDER][0])
        curr_torso_height = abs(landmarks[LEFT_HIP][1] - landmarks[LEFT_SHOULDER][1])

        # Get calibration metrics
        metrics = self.pipeline.state.calibration_metrics

        if metrics is None:
            # Fallback if not calibrated properly
            scale = curr_shoulder_width * self.config.splat_scale
            positions_2d = np.zeros((len(positions_3d), 2), dtype=np.float32)
            positions_2d[:, 0] = (positions_3d[:, 0] * scale + 0.5) * width
            positions_2d[:, 1] = (positions_3d[:, 1] * scale + 0.5) * height  # Same Y convention
            sizes = np.ones(len(positions_3d)) * 3
            return positions_2d, sizes

        # === PROPER SCALE CALCULATION ===
        # The splat should fit the body. Scale maps splat units to screen units.
        #
        # Formula: scale = body_size_screen / splat_size
        # This makes the splat cover the body region.
        #
        # We use shoulder width as primary reference, with distance adjustment.

        # Scale factor: how much of screen width does one splat unit cover?
        # At calibration: splat_width units should cover shoulder_width_screen of frame
        scale_at_calibration = metrics.shoulder_width_screen / max(metrics.splat_width, 0.01)

        # Distance adjustment: if user moves closer/farther, shoulders appear larger/smaller
        distance_ratio = curr_shoulder_width / max(metrics.shoulder_width_screen, 0.01)

        # Combined scale (splat units to screen normalized [0,1])
        scale = scale_at_calibration * distance_ratio * self.config.splat_scale

        # === BODY TRACKING ===
        # Compute how much the body center has moved since calibration
        body_delta = curr_body_center - metrics.body_center_screen

        # === PROJECT POSITIONS ===
        positions_2d = np.zeros((len(positions_3d), 2), dtype=np.float32)

        # Splat positions are centered around 0, so:
        # screen_pos = splat_pos * scale + body_center
        # Then convert to pixels

        # X: splat space -> screen normalized -> add tracking delta -> pixels
        x_screen = positions_3d[:, 0] * scale + metrics.body_center_screen[0] + body_delta[0]
        positions_2d[:, 0] = x_screen * width

        # Y: splat Y convention: negative=top, positive=bottom (matches screen coords)
        # Screen Y: 0=top, 1=bottom (normalized) or 0=top, H=bottom (pixels)
        # NO negation needed - both use same convention
        y_screen = positions_3d[:, 1] * scale + metrics.body_center_screen[1] + body_delta[1]
        positions_2d[:, 1] = y_screen * height

        # === COMPUTE SPLAT SIZES ===
        # Base size proportional to scale (larger when closer)
        base_size_pixels = scale * width * 0.008  # 0.8% of scaled width

        # Depth variation: closer splats slightly larger
        z_values = positions_3d[:, 2]
        z_min, z_max = z_values.min(), z_values.max()
        z_range = max(z_max - z_min, 0.001)
        z_normalized = (z_values - z_min) / z_range  # 0 = back, 1 = front

        # Size range: base to base*1.5 based on depth
        sizes = base_size_pixels * (1.0 + z_normalized * 0.5)
        sizes = np.clip(sizes, 2, 15)  # Reasonable pixel range

        return positions_2d, sizes

    def render_splats(
        self,
        frame: np.ndarray,
        positions_2d: np.ndarray,
        colors: np.ndarray,
        sizes: np.ndarray = None,
        alpha: float = 0.7
    ) -> np.ndarray:
        """
        Render splats on frame with depth-based sizing.

        Closer splats are rendered larger and on top.
        """
        height, width = frame.shape[:2]

        if sizes is None:
            sizes = np.ones(len(positions_2d)) * 3

        # Create overlay
        overlay = frame.copy()

        # Sort by depth (z) for proper occlusion - render back to front
        if self.pipeline.state.current_positions is not None:
            z_order = np.argsort(self.pipeline.state.current_positions[:, 2])
        else:
            z_order = np.arange(len(positions_2d))

        # Render each splat
        for idx in z_order:
            x, y = positions_2d[idx]
            size = max(1, int(sizes[idx]))

            # Skip if outside frame (with margin for size)
            if x < -size or x >= width + size or y < -size or y >= height + size:
                continue

            # Color (BGR for OpenCV)
            color = (
                int(np.clip(colors[idx, 2] * 255, 0, 255)),  # B
                int(np.clip(colors[idx, 1] * 255, 0, 255)),  # G
                int(np.clip(colors[idx, 0] * 255, 0, 255))   # R
            )

            # Draw filled circle with size based on depth
            cv2.circle(overlay, (int(x), int(y)), size, color, -1)

        # Blend with original frame
        result = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        return result

    def draw_ui(self, frame: np.ndarray) -> np.ndarray:
        """Draw UI overlay"""
        height, width = frame.shape[:2]

        # Colors
        WHITE = (255, 255, 255)
        GREEN = (0, 255, 0)
        RED = (0, 0, 255)
        YELLOW = (0, 255, 255)
        CYAN = (255, 255, 0)

        # State-specific UI
        if self.state == DemoState.NO_SPLAT:
            self._draw_text(frame, "No splat loaded", (20, 40), WHITE, scale=1.0)
            self._draw_text(frame, "Press 'L' to load or 'G' to generate", (20, 80), CYAN)

        elif self.state == DemoState.WAITING_FOR_BODY:
            self._draw_text(frame, "Waiting for body...", (20, 40), YELLOW, scale=1.0)
            self._draw_text(frame, "Stand in front of camera", (20, 80), WHITE)

        elif self.state == DemoState.READY_TO_CALIBRATE:
            self._draw_text(frame, "Body detected!", (20, 40), GREEN, scale=1.0)
            self._draw_text(frame, "Press SPACE to start calibration", (20, 80), CYAN)
            self._draw_text(frame, "Strike a T-pose during countdown", (20, 120), WHITE)

            # Draw T-pose guide
            self._draw_tpose_guide(frame)

        elif self.state == DemoState.COUNTDOWN:
            # Calculate remaining seconds
            if self.countdown_start_time is not None:
                elapsed = time.time() - self.countdown_start_time
                remaining = max(0, self.config.countdown_seconds - elapsed)
                countdown_num = int(remaining) + 1  # 3, 2, 1

                if countdown_num > 0 and countdown_num <= self.config.countdown_seconds:
                    # Draw large countdown number in center
                    countdown_text = str(countdown_num)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 8.0
                    thickness = 15

                    # Get text size for centering
                    (text_w, text_h), baseline = cv2.getTextSize(
                        countdown_text, font, font_scale, thickness
                    )

                    # Center position
                    text_x = (width - text_w) // 2
                    text_y = (height + text_h) // 2

                    # Draw shadow
                    cv2.putText(frame, countdown_text, (text_x + 4, text_y + 4),
                               font, font_scale, (0, 0, 0), thickness + 4)
                    # Draw countdown number
                    cv2.putText(frame, countdown_text, (text_x, text_y),
                               font, font_scale, GREEN, thickness)

                    # Instructions
                    self._draw_text(frame, "GET INTO T-POSE!", (20, 40), YELLOW, scale=1.0)

                    # Draw T-pose guide
                    self._draw_tpose_guide(frame)

        elif self.state == DemoState.LIVE_TRYON:
            # Show FPS
            if self.config.show_fps and self.fps_history:
                avg_fps = sum(self.fps_history) / len(self.fps_history)
                self._draw_text(frame, f"FPS: {avg_fps:.0f}", (width - 120, 40), GREEN)

            # Instructions
            self._draw_text(frame, "LIVE TRY-ON", (20, 40), GREEN, scale=1.0)
            self._draw_text(frame, "R: Reset | Q: Quit | +/-: Scale", (20, height - 20), WHITE, scale=0.5)

        elif self.state == DemoState.ERROR:
            self._draw_text(frame, "ERROR", (20, 40), RED, scale=1.0)
            self._draw_text(frame, self.error_message[:50], (20, 80), WHITE)

        # Always show controls at bottom
        controls = "SPACE: Calibrate | L: Load | G: Generate | R: Reset | Q: Quit"
        self._draw_text(frame, controls, (10, height - 10), WHITE, scale=0.4)

        return frame

    def _draw_text(
        self,
        frame: np.ndarray,
        text: str,
        pos: Tuple[int, int],
        color: Tuple[int, int, int],
        scale: float = 0.7
    ):
        """Draw text with background"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2

        # Get text size for background
        (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)

        # Draw background
        x, y = pos
        cv2.rectangle(frame, (x - 5, y - text_height - 5),
                     (x + text_width + 5, y + baseline + 5), (0, 0, 0), -1)

        # Draw text
        cv2.putText(frame, text, pos, font, scale, color, thickness)

    def _draw_tpose_guide(self, frame: np.ndarray):
        """Draw T-pose guide overlay"""
        height, width = frame.shape[:2]
        cx, cy = width // 2, height // 2

        # Simple stick figure in T-pose
        color = (100, 100, 100)
        thickness = 2

        # Head
        cv2.circle(frame, (cx, cy - 80), 20, color, thickness)

        # Body
        cv2.line(frame, (cx, cy - 60), (cx, cy + 40), color, thickness)

        # Arms (horizontal)
        cv2.line(frame, (cx - 100, cy - 40), (cx + 100, cy - 40), color, thickness)

        # Legs
        cv2.line(frame, (cx, cy + 40), (cx - 40, cy + 120), color, thickness)
        cv2.line(frame, (cx, cy + 40), (cx + 40, cy + 120), color, thickness)

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame"""
        frame_start = time.time()

        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect pose
        landmarks = self.pose_detector.detect(frame_rgb)
        self.current_landmarks = landmarks

        # State machine
        if self.state == DemoState.WAITING_FOR_BODY:
            if landmarks is not None:
                self.state = DemoState.READY_TO_CALIBRATE

        elif self.state == DemoState.READY_TO_CALIBRATE:
            if landmarks is None:
                self.state = DemoState.WAITING_FOR_BODY
            # Just wait for SPACE key (handled in run() loop)

        elif self.state == DemoState.COUNTDOWN:
            # Countdown is running - check if complete
            if self.countdown_start_time is not None:
                elapsed = time.time() - self.countdown_start_time
                if elapsed >= self.config.countdown_seconds:
                    # Countdown complete - calibrate now!
                    if landmarks is not None:
                        self.calibrate(landmarks)
                    else:
                        # No body detected at calibration moment
                        logger.warning("No body detected at calibration, resetting")
                        self.countdown_start_time = None
                        self.state = DemoState.WAITING_FOR_BODY

        elif self.state == DemoState.LIVE_TRYON:
            if landmarks is not None:
                # Animate splats
                transformed = self.pipeline.animate(landmarks)

                # Project to 2D with depth-based sizes
                positions_2d, sizes = self.project_splats_to_2d(
                    transformed, landmarks, frame.shape
                )

                # Render splats with depth visualization
                frame = self.render_splats(frame, positions_2d, self.splat_colors, sizes)

        # Draw landmarks if enabled
        if self.config.show_landmarks and landmarks is not None:
            frame = self.pose_detector.draw_landmarks(frame, landmarks)

        # Draw UI
        frame = self.draw_ui(frame)

        # Update FPS
        frame_time = time.time() - frame_start
        fps = 1.0 / frame_time if frame_time > 0 else 0
        self.fps_history.append(fps)
        if len(self.fps_history) > 30:
            self.fps_history.pop(0)

        self.frame_count += 1

        return frame

    def calibrate(self, landmarks: np.ndarray):
        """Perform calibration with current landmarks"""
        logger.info("Calibrating...")

        success = self.pipeline.calibrate(landmarks)

        if success:
            self.state = DemoState.LIVE_TRYON
            self.countdown_start_time = None
            logger.info("Calibration successful!")
        else:
            self.state = DemoState.ERROR
            self.error_message = "Calibration failed"

    def reset(self):
        """Reset calibration"""
        self.pipeline.state.is_calibrated = False
        self.pipeline.state.skinning_weights = None
        self.pipeline.state.animator = None
        self.countdown_start_time = None

        if self.pipeline.state.splat_positions is not None:
            self.state = DemoState.WAITING_FOR_BODY
        else:
            self.state = DemoState.NO_SPLAT

        logger.info("Reset complete")

    def run(self):
        """Main demo loop"""
        if not self.initialize():
            return

        # Try to load default splat
        default_ply = Path(__file__).parent / "output"
        ply_files = list(default_ply.glob("clothing_only_*.ply"))
        if ply_files:
            latest_ply = sorted(ply_files)[-1]
            logger.info(f"Loading default splat: {latest_ply}")
            self.load_splat(str(latest_ply))

        # Warm up camera (macOS needs this)
        logger.info("Warming up camera...")
        for _ in range(10):
            self.camera.read()
            time.sleep(0.05)

        logger.info("Starting main loop. Press 'Q' to quit.")

        window_name = "Gaussian Splat Try-On Demo"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        consecutive_failures = 0
        max_failures = 30

        try:
            while True:
                # Capture frame with retry logic
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.warning("Attempting camera reconnect...")
                        self.camera.release()
                        time.sleep(0.5)
                        self.camera = cv2.VideoCapture(self.config.camera_id)
                        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        consecutive_failures = 0
                        if not self.camera.isOpened():
                            logger.error("Camera reconnect failed, exiting")
                            break
                        continue
                    time.sleep(0.033)  # ~30fps retry rate
                    continue

                consecutive_failures = 0  # Reset on success

                # Flip horizontally for mirror effect
                frame = cv2.flip(frame, 1)

                # Process frame
                frame = self.process_frame(frame)

                # Display
                cv2.imshow(window_name, frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q') or key == 27:  # Q or ESC
                    break
                elif key == ord(' '):  # Space - start countdown
                    if self.state == DemoState.READY_TO_CALIBRATE:
                        logger.info("Starting calibration countdown...")
                        self.countdown_start_time = time.time()
                        self.state = DemoState.COUNTDOWN
                elif key == ord('r'):  # R - reset
                    self.reset()
                elif key == ord('l'):  # L - load splat
                    self._load_splat_dialog()
                elif key == ord('g'):  # G - generate splat
                    self._generate_splat_dialog()
                elif key == ord('+') or key == ord('='):
                    self.config.splat_scale *= 1.1
                    logger.info(f"Scale: {self.config.splat_scale:.2f}")
                elif key == ord('-'):
                    self.config.splat_scale *= 0.9
                    logger.info(f"Scale: {self.config.splat_scale:.2f}")
                elif key == ord('d'):
                    self.config.show_landmarks = not self.config.show_landmarks

        finally:
            self.cleanup()

    def _load_splat_dialog(self):
        """Simple file selection for loading splat"""
        output_dir = Path(__file__).parent / "output"
        ply_files = list(output_dir.glob("*.ply"))

        if not ply_files:
            logger.warning("No PLY files found in output/")
            return

        # Use most recent
        latest = sorted(ply_files)[-1]
        logger.info(f"Loading: {latest}")
        self.load_splat(str(latest))

    def _generate_splat_dialog(self):
        """Generate splat from default test image"""
        test_image = Path(__file__).parent / "test_images" / "clothing_test.png"

        if not test_image.exists():
            logger.warning(f"Test image not found: {test_image}")
            return

        logger.info(f"Generating from: {test_image}")
        self.generate_splat(str(test_image))

    def cleanup(self):
        """Clean up resources"""
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
        logger.info("Cleanup complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Live Gaussian Splat Try-On Demo')
    parser.add_argument('--camera', type=int, default=0, help='Camera ID')
    parser.add_argument('--width', type=int, default=1280, help='Camera width')
    parser.add_argument('--height', type=int, default=720, help='Camera height')
    parser.add_argument('--no-landmarks', action='store_true', help='Hide landmarks')
    parser.add_argument('--scale', type=float, default=1.0, help='Initial splat scale')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # Create config
    config = DemoConfig(
        camera_id=args.camera,
        camera_width=args.width,
        camera_height=args.height,
        show_landmarks=not args.no_landmarks,
        splat_scale=args.scale
    )

    # Run demo
    demo = LiveTryOnDemo(config)
    demo.run()


if __name__ == '__main__':
    main()
