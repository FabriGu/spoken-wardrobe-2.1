"""
Pose detection module using MediaPipe Tasks API.

Provides RGB-only pose detection as a replacement for OAK-D BlazePose,
eliminating the need for a depth camera.
"""

from .mediapipe_pose import MediaPipePoseTracker, PoseBody

__all__ = ['MediaPipePoseTracker', 'PoseBody']
