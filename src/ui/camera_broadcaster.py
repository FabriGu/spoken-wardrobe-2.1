"""
Camera Broadcaster - Continuous Frame Streaming Thread

This module provides a background thread that continuously captures frames from
the OAK-D camera and streams them to the WebSocket server, ensuring the browser
always has a live camera feed even during blocking pipeline operations.

Architecture:
    [OAK-D + BlazePose] -> [CameraBroadcaster Thread] -> [WebSocket Server] -> [Browser]
                               |
                               +-> get_latest_frame() (non-blocking, for pipeline)

The broadcaster owns the camera tracker and calls next_frame() continuously at ~30 FPS.
The main pipeline thread can get the latest frame without blocking using get_latest_frame().

Usage:
    from src.ui.camera_broadcaster import CameraBroadcaster

    # After initializing tracker and ws_server:
    broadcaster = CameraBroadcaster(tracker, ws_server, target_fps=30)
    broadcaster.start()

    # From pipeline (non-blocking):
    frame_data = broadcaster.get_latest_frame()
    if frame_data:
        frame_rgb, body = frame_data.frame_rgb, frame_data.body

    # Stop when done:
    broadcaster.stop()
    broadcaster.join()
"""

import threading
import time
import cv2
import numpy as np
from typing import Optional, Callable, Any
from dataclasses import dataclass

# Import bone rotation calculator for skeletal animation
try:
    from .bone_rotation_calculator import BoneRotationCalculator
except ImportError:
    BoneRotationCalculator = None


@dataclass
class FrameData:
    """Container for frame data with pose information."""
    frame_rgb: np.ndarray  # RGB frame (H, W, 3)
    body: Optional[Any]    # BlazePose body object (or None if no body detected)
    timestamp: float       # Capture timestamp (time.time())

    def copy(self) -> 'FrameData':
        """Create a copy of this frame data (for thread safety)."""
        return FrameData(
            frame_rgb=self.frame_rgb.copy(),
            body=self.body,  # Body object is read-only, no need to deep copy
            timestamp=self.timestamp
        )


class CameraBroadcaster(threading.Thread):
    """
    Background thread that continuously captures camera frames.

    Runs independently of the main pipeline, ensuring the browser UI always has
    fresh camera frames even during blocking operations (Whisper transcription,
    ComfyUI generation, Rodin API calls).

    The broadcaster:
    1. Calls tracker.next_frame() continuously (~30 FPS)
    2. Stores the latest frame in a thread-safe buffer
    3. Emits frames to WebSocket server for browser streaming

    The pipeline can get the latest frame at any time without blocking using
    get_latest_frame().

    Attributes:
        tracker: BlazeposeDepthai instance (owns the camera)
        ws_server: PipelineWebSocketServer for streaming to browser
        target_fps: Target frame rate for WebSocket streaming (default: 30)
    """

    def __init__(self, tracker, ws_server, target_fps: int = 30):
        """
        Initialize the camera broadcaster.

        Args:
            tracker: BlazeposeDepthai instance (must already be initialized)
            ws_server: PipelineWebSocketServer instance (or None to skip streaming)
            target_fps: Target FPS for WebSocket streaming (default: 30)
        """
        super().__init__(daemon=True, name="CameraBroadcaster")
        self.tracker = tracker
        self.ws_server = ws_server
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps

        # Thread synchronization
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[FrameData] = None

        # Optional mesh calibrator for transform computation
        self.mesh_calibrator: Optional[Any] = None

        # Bone rotation calculator for skeletal animation (9-bone rotations)
        self.bone_rotation_calculator: Optional[Any] = None
        if BoneRotationCalculator:
            self.bone_rotation_calculator = BoneRotationCalculator(smoothing_factor=0.3)

        # Skeleton drawing control (enable during CALIBRATING and TRY_ON states)
        self.draw_skeleton = False

        # Always show keypoints throughout interaction (purple/blue theme)
        self.always_show_keypoints = True

        # Statistics
        self._frame_count = 0
        self._start_time = 0
        self._last_emit_time = 0

        # Camera health tracking
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10  # Trigger recovery after this many errors
        self._camera_error = False  # Flag to signal fatal camera error
        self._last_successful_frame = 0  # Timestamp of last good frame

        # Pause control (for thermal management - camera stays init but stops capturing)
        self._paused = False

        # Optional callback for when new frames arrive
        self.on_frame: Optional[Callable[[FrameData], None]] = None

    # BlazePose skeleton connections (pairs of landmark indices)
    POSE_CONNECTIONS = [
        # Torso
        (11, 12), (11, 23), (12, 24), (23, 24),
        # Left arm
        (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
        # Right arm
        (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
        # Left leg
        (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
        # Right leg
        (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
        # Face
        (0, 1), (1, 2), (2, 3), (3, 7),
        (0, 4), (4, 5), (5, 6), (6, 8),
        (9, 10),  # Mouth
    ]

    def run(self):
        """
        Main capture loop - runs in background thread.

        Continuously captures frames from the OAK-D camera and:
        1. Stores the latest frame (thread-safe)
        2. Emits to WebSocket at target FPS
        3. Detects fatal camera errors and signals for recovery
        """
        self._running = True
        self._start_time = time.time()
        self._last_emit_time = 0
        self._last_successful_frame = time.time()
        self._consecutive_errors = 0
        self._camera_error = False

        print(f"[CameraBroadcaster] Started at {self.target_fps} FPS target")

        while self._running:
            # Skip capture when paused (thermal management)
            if self._paused:
                time.sleep(0.1)
                continue

            try:
                # Capture frame from OAK-D (this is the blocking call)
                frame, body = self.tracker.next_frame()

                if frame is None:
                    self._consecutive_errors += 1
                    if self._consecutive_errors > self._max_consecutive_errors:
                        print(f"[CameraBroadcaster] Too many consecutive null frames ({self._consecutive_errors})")
                    time.sleep(0.01)  # Brief sleep if no frame available
                    continue

                # Reset error counter on successful frame
                self._consecutive_errors = 0
                self._last_successful_frame = time.time()

                # Convert BGR to RGB (BlazePose returns BGR)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Create frame data container
                frame_data = FrameData(
                    frame_rgb=frame_rgb,
                    body=body,
                    timestamp=time.time()
                )

                # Store latest frame (thread-safe)
                with self._lock:
                    self._latest_frame = frame_data
                    self._frame_count += 1

                # Emit to WebSocket at target FPS
                current_time = time.time()
                if current_time - self._last_emit_time >= self.frame_interval:
                    self._emit_frame(frame_rgb, body)
                    self._last_emit_time = current_time

                # Call optional frame callback
                if self.on_frame:
                    try:
                        self.on_frame(frame_data)
                    except Exception as e:
                        print(f"[CameraBroadcaster] Frame callback error: {e}")

            except Exception as e:
                error_str = str(e)
                self._consecutive_errors += 1

                # Check for fatal camera errors (X_LINK_ERROR, device disconnected, etc.)
                is_fatal = any(fatal in error_str for fatal in [
                    'X_LINK_ERROR', 'device error', 'Communication exception',
                    'Device not found', 'Connection refused', 'USB', 'disconnected'
                ])

                if is_fatal or self._consecutive_errors >= self._max_consecutive_errors:
                    print(f"[CameraBroadcaster] FATAL camera error detected: {e}")
                    print(f"[CameraBroadcaster] Consecutive errors: {self._consecutive_errors}")
                    self._camera_error = True
                    self._running = False  # Stop the loop - camera needs restart
                    break
                else:
                    print(f"[CameraBroadcaster] Error in capture loop ({self._consecutive_errors}/{self._max_consecutive_errors}): {e}")
                    time.sleep(0.1)  # Back off on error

        # Report statistics on exit
        elapsed = time.time() - self._start_time
        if elapsed > 0:
            avg_fps = self._frame_count / elapsed
            status = "FATAL ERROR" if self._camera_error else "Stopped"
            print(f"[CameraBroadcaster] {status}. {self._frame_count} frames "
                  f"in {elapsed:.1f}s ({avg_fps:.1f} avg FPS)")

    # Theme colors for keypoint visualization (RGB)
    # Purple/blue gradient to match UI theme
    THEME_PURPLE = (139, 92, 246)      # Primary purple (#8B5CF6)
    THEME_BLUE = (59, 130, 246)        # Blue accent (#3B82F6)
    THEME_PINK = (236, 72, 153)        # Pink accent (#EC4899)
    THEME_PURPLE_LIGHT = (167, 139, 250)  # Light purple (#A78BFA)

    def _draw_keypoints_only(self, frame_rgb: np.ndarray, body) -> np.ndarray:
        """
        Draw minimal keypoint overlay on frame (always shown throughout interaction).

        Uses purple/blue theme colors to match the UI design.
        Only draws keypoint dots without full skeleton connections.

        Args:
            frame_rgb: RGB frame array (H, W, 3)
            body: BlazePose body object with landmarks

        Returns:
            Frame with keypoint overlay drawn (modifies in place for performance)
        """
        if body is None or not hasattr(body, 'landmarks'):
            return frame_rgb

        h, w = frame_rgb.shape[:2]
        landmarks = body.landmarks

        # Key body landmarks to always show (subset for cleaner look)
        # Face: 0 (nose), Shoulders: 11, 12, Elbows: 13, 14, Wrists: 15, 16
        # Hips: 23, 24, Knees: 25, 26, Ankles: 27, 28
        key_landmarks = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

        # Draw keypoints with purple/blue theme
        for i, lm in enumerate(landmarks):
            try:
                # Get visibility
                vis = lm[3] if len(lm) > 3 else (lm.visibility if hasattr(lm, 'visibility') else 1.0)

                if vis > 0.5:
                    # Get pixel coordinates
                    if hasattr(lm, 'x'):
                        pt = (int(lm.x * w), int(lm.y * h))
                    else:
                        pt = (int(lm[0] * w), int(lm[1] * h))

                    # Use different sizes/colors for key landmarks vs secondary
                    if i in key_landmarks:
                        # Key landmarks: larger purple dots with glow effect
                        # Outer glow (semi-transparent effect via multiple circles)
                        cv2.circle(frame_rgb, pt, 8, self.THEME_PURPLE_LIGHT, 1, cv2.LINE_AA)
                        cv2.circle(frame_rgb, pt, 5, self.THEME_PURPLE, -1, cv2.LINE_AA)
                        cv2.circle(frame_rgb, pt, 2, (255, 255, 255), -1, cv2.LINE_AA)  # White center
                    else:
                        # Secondary landmarks: smaller blue dots
                        cv2.circle(frame_rgb, pt, 3, self.THEME_BLUE, -1, cv2.LINE_AA)
            except (IndexError, TypeError):
                continue

        return frame_rgb

    def _draw_skeleton(self, frame_rgb: np.ndarray, body) -> np.ndarray:
        """
        Draw full BlazePose skeleton overlay on frame for user feedback.

        Renders keypoints as circles and connections as lines, giving the user
        visual feedback that their body is being tracked. Uses purple/blue
        theme colors to match the UI design.

        Args:
            frame_rgb: RGB frame array (H, W, 3)
            body: BlazePose body object with landmarks

        Returns:
            Frame with skeleton overlay drawn (copy of original)
        """
        if body is None or not hasattr(body, 'landmarks'):
            return frame_rgb

        # Work on a copy to avoid modifying the original
        frame_with_skeleton = frame_rgb.copy()
        h, w = frame_rgb.shape[:2]

        # BlazePose landmarks have x, y as normalized coords [0-1]
        landmarks = body.landmarks

        # Theme colors (purple/blue gradient)
        connection_color = self.THEME_BLUE       # Blue for connections
        keypoint_color = self.THEME_PURPLE       # Purple for keypoints
        keypoint_highlight = self.THEME_PINK     # Pink for key joints
        keypoint_outline = (255, 255, 255)       # White outline

        # Key joints get highlighted (shoulders, elbows, wrists, hips, knees, ankles)
        key_joints = {11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28}

        # Draw connections (lines) first so keypoints are on top
        for start_idx, end_idx in self.POSE_CONNECTIONS:
            try:
                start = landmarks[start_idx]
                end = landmarks[end_idx]

                # Check visibility (landmarks have visibility attribute)
                start_vis = start[3] if len(start) > 3 else (start.visibility if hasattr(start, 'visibility') else 1.0)
                end_vis = end[3] if len(end) > 3 else (end.visibility if hasattr(end, 'visibility') else 1.0)

                if start_vis > 0.5 and end_vis > 0.5:
                    # Get pixel coordinates
                    if hasattr(start, 'x'):
                        pt1 = (int(start.x * w), int(start.y * h))
                        pt2 = (int(end.x * w), int(end.y * h))
                    else:
                        pt1 = (int(start[0] * w), int(start[1] * h))
                        pt2 = (int(end[0] * w), int(end[1] * h))

                    # Draw connection line with slight glow effect
                    cv2.line(frame_with_skeleton, pt1, pt2, self.THEME_PURPLE_LIGHT, 4, cv2.LINE_AA)
                    cv2.line(frame_with_skeleton, pt1, pt2, connection_color, 2, cv2.LINE_AA)
            except (IndexError, TypeError):
                continue

        # Draw keypoints (circles)
        for i, lm in enumerate(landmarks):
            try:
                # Get visibility
                vis = lm[3] if len(lm) > 3 else (lm.visibility if hasattr(lm, 'visibility') else 1.0)

                if vis > 0.5:
                    # Get pixel coordinates
                    if hasattr(lm, 'x'):
                        pt = (int(lm.x * w), int(lm.y * h))
                    else:
                        pt = (int(lm[0] * w), int(lm[1] * h))

                    # Key joints get highlighted with pink, others get purple
                    color = keypoint_highlight if i in key_joints else keypoint_color

                    # Draw with glow effect: outer ring, fill, center dot
                    cv2.circle(frame_with_skeleton, pt, 8, self.THEME_PURPLE_LIGHT, 1, cv2.LINE_AA)
                    cv2.circle(frame_with_skeleton, pt, 6, keypoint_outline, -1, cv2.LINE_AA)
                    cv2.circle(frame_with_skeleton, pt, 4, color, -1, cv2.LINE_AA)
            except (IndexError, TypeError):
                continue

        return frame_with_skeleton

    def _emit_frame(self, frame_rgb: np.ndarray, body):
        """
        Send frame to WebSocket server.

        Sends the ORIGINAL frame without keypoints baked in.
        Keypoints are rendered browser-side on a canvas overlay for proper z-indexing.

        Args:
            frame_rgb: RGB frame array
            body: BlazePose body object (for landmark extraction)
        """
        if self.ws_server is None:
            return

        # Always send original frame - keypoints are rendered in browser
        frame_to_send = frame_rgb

        # Extract landmarks from body object
        landmarks_world = None
        landmarks_2d = None
        calibration = None
        bone_rotations = None

        # Visibility array (passed separately to avoid np.hstack overhead)
        visibility = None

        if body:
            # Extract 2D pixel landmarks for browser-side keypoint rendering
            if hasattr(body, 'landmarks') and body.landmarks is not None:
                landmarks_2d = body.landmarks  # (33, 3) array with [x, y, z] in pixels
                # Get visibility separately (no array concatenation)
                if hasattr(body, 'visibility') and body.visibility is not None:
                    visibility = body.visibility  # (33,) array

            # Extract world landmarks for calibration
            if hasattr(body, 'landmarks_world'):
                landmarks_world = body.landmarks_world

                # Compute mesh calibration transform if calibrator is set
                if self.mesh_calibrator:
                    try:
                        calibration = self.mesh_calibrator.compute_transform(body)
                    except Exception as e:
                        pass  # Silently ignore calibration errors

                # Compute bone rotations for skeletal animation
                if self.bone_rotation_calculator:
                    try:
                        bone_rotations = self.bone_rotation_calculator.compute_bone_rotations(body)
                    except Exception as e:
                        pass  # Silently ignore bone rotation errors

        # Emit via WebSocket server (thread-safe, uses queue)
        self.ws_server.emit_frame(frame_to_send, landmarks_world, calibration, bone_rotations,
                                  landmarks_2d=landmarks_2d, visibility=visibility)

    def get_latest_frame(self, copy: bool = False) -> Optional[FrameData]:
        """
        Get the most recent frame (thread-safe, non-blocking).

        This is the main method for the pipeline to get camera frames without
        blocking. The pipeline can call this during any operation to get the
        latest available frame.

        Args:
            copy: If True, return a deep copy of the frame data.
                  Use this if you need to modify the frame or keep it long-term.

        Returns:
            FrameData with frame_rgb, body, and timestamp, or None if no frame yet.
        """
        with self._lock:
            if self._latest_frame is None:
                return None
            if copy:
                return self._latest_frame.copy()
            return self._latest_frame

    def wait_for_frame(self, timeout: float = 5.0) -> Optional[FrameData]:
        """
        Wait for a frame to become available.

        Useful during startup to ensure the camera is producing frames.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            FrameData or None if timeout exceeded
        """
        start = time.time()
        while time.time() - start < timeout:
            frame = self.get_latest_frame()
            if frame is not None:
                return frame
            time.sleep(0.05)
        return None

    def get_stats(self) -> dict:
        """
        Get broadcaster statistics.

        Returns:
            Dictionary with frame_count, elapsed_time, and avg_fps
        """
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            'frame_count': self._frame_count,
            'elapsed_time': elapsed,
            'avg_fps': self._frame_count / elapsed if elapsed > 0 else 0,
            'running': self._running
        }

    def stop(self):
        """Stop the capture loop."""
        print("[CameraBroadcaster] Stop requested")
        self._running = False

    def pause(self):
        """Pause frame capture (camera stays initialized but stops streaming)."""
        self._paused = True
        print("[CameraBroadcaster] Paused")

    def resume(self):
        """Resume frame capture."""
        self._paused = False
        print("[CameraBroadcaster] Resumed")

    @property
    def is_running(self) -> bool:
        """Check if broadcaster is currently running."""
        return self._running

    @property
    def has_fatal_error(self) -> bool:
        """Check if a fatal camera error occurred."""
        return self._camera_error

    @property
    def is_healthy(self) -> bool:
        """
        Check if camera is healthy and producing frames.

        Returns False if:
        - Not running
        - Fatal error occurred
        - No frames for more than 5 seconds
        """
        if not self._running or self._camera_error:
            return False
        if self._last_successful_frame == 0:
            return True  # Just started, no frames yet
        return (time.time() - self._last_successful_frame) < 5.0
