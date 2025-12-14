"""
WebSocket Server for Pipeline-UI Communication

This module provides real-time communication between the Python pipeline
and the Three.js browser frontend. It streams camera frames, audio levels,
pipeline state changes, and mesh data to connected clients.

Architecture:
    [Pipeline] -> [PipelineWebSocketServer] -> [Browser UI (Three.js)]

Message Types (Pipeline -> UI):
    - state_change: Pipeline state transitions (IDLE, LISTENING, A_POSE, etc.)
    - frame: Camera frame as JPEG base64 with optional landmarks/calibration
    - audio_level: Current audio level and threshold for visualization
    - transcription: Transcribed text from Whisper
    - generation_progress: Progress updates during 2D/3D generation
    - mesh_ready: GLB mesh data as base64 when 3D generation completes

Message Types (UI -> Pipeline):
    - user_action: User commands (restart, skip_3d, etc.)

Usage:
    server = PipelineWebSocketServer(host='localhost', port=8765)

    # In a daemon thread:
    asyncio.run(server.start())

    # From pipeline (sync context):
    server.emit_state_change('LISTENING', {'prompt': 'Describe your clothing...'})
    server.emit_frame(frame_rgb, landmarks, calibration)
"""

import asyncio
import json
import base64
import threading
import queue
from typing import Set, Dict, Any, Optional
import cv2

try:
    import websockets
except ImportError:
    raise ImportError("websockets package required. Install with: pip install websockets>=12.0")


class PipelineWebSocketServer:
    """
    Async WebSocket server for streaming pipeline data to browser UI.

    Designed to run in a daemon thread while the main pipeline runs synchronously.
    Uses a thread-safe queue for cross-thread communication.

    Attributes:
        host: Server hostname (default: localhost)
        port: Server port (default: 8765)
        clients: Set of connected WebSocket clients
        current_state: Current pipeline state name
        state_data: Additional data for current state
    """

    # Pipeline states matching the state machine
    STATES = [
        'IDLE',           # Welcome screen, waiting for user
        'LISTENING',      # Listening for speech
        'RECORDING',      # Recording audio (10s)
        'TRANSCRIBING',   # Whisper processing
        'A_POSE',         # Waiting for A-pose
        'CAPTURING',      # Capturing body frame
        'GENERATING_2D',  # ComfyUI/SD generation
        'GENERATING_3D',  # Rodin API generation
        'PREVIEW',        # Showing 2D preview
        'CALIBRATING',    # Mesh calibration
        'TRY_ON',         # 3D mesh overlay on camera
        'ERROR'           # Error state
    ]

    def __init__(self, host: str = 'localhost', port: int = 8765):
        """
        Initialize the WebSocket server.

        Args:
            host: Server hostname
            port: Server port
        """
        self.host = host
        self.port = port
        self.clients: Set = set()
        self.current_state = 'IDLE'
        self.state_data: Dict[str, Any] = {}

        # Thread-safe queue for sync->async communication
        self._message_queue: queue.Queue = queue.Queue()

        # Event loop reference (set when server starts)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Flag to track if server is running
        self._running = False

    async def handler(self, websocket):
        """
        Handle a single WebSocket client connection.

        Sends current state on connect and listens for client messages.

        Args:
            websocket: The connected WebSocket client
        """
        self.clients.add(websocket)
        print(f"[WebSocket] Client connected. Total clients: {len(self.clients)}")

        try:
            # Send current state on connect
            await websocket.send(json.dumps({
                'type': 'state_change',
                'state': self.current_state,
                'data': self.state_data
            }))

            # Listen for client messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_client_message(data, websocket)
                except json.JSONDecodeError:
                    print(f"[WebSocket] Invalid JSON received: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[WebSocket] Client disconnected. Total clients: {len(self.clients)}")

    async def _handle_client_message(self, data: dict, websocket):
        """
        Process messages received from UI clients.

        Args:
            data: Parsed JSON message
            websocket: The client that sent the message
        """
        msg_type = data.get('type')

        if msg_type == 'user_action':
            action = data.get('action')
            print(f"[WebSocket] User action: {action}")
            # Actions can be handled by the pipeline via a callback
            # For now, just log them

        elif msg_type == 'ping':
            await websocket.send(json.dumps({'type': 'pong'}))

    async def broadcast(self, message: dict):
        """
        Send a message to all connected clients.

        Args:
            message: Dictionary to send as JSON
        """
        if not self.clients:
            return

        msg_json = json.dumps(message)

        # Send to all clients, handling disconnections
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(msg_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)

        # Remove disconnected clients
        self.clients -= disconnected

    async def _process_queue(self):
        """
        Process messages from the sync queue and broadcast them.

        This runs as a background task, checking the queue periodically.
        """
        while self._running:
            try:
                # Non-blocking check with timeout
                try:
                    message = self._message_queue.get_nowait()
                    await self.broadcast(message)
                except queue.Empty:
                    pass

                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.005)  # 5ms = max 200 messages/sec

            except Exception as e:
                print(f"[WebSocket] Queue processing error: {e}")

    def emit_state_change(self, state: str, data: Optional[Dict[str, Any]] = None):
        """
        Emit a state change to all connected clients (thread-safe).

        Call this from the pipeline when transitioning between stages.

        Args:
            state: New state name (e.g., 'LISTENING', 'A_POSE')
            data: Optional state-specific data
        """
        self.current_state = state
        self.state_data = data or {}

        message = {
            'type': 'state_change',
            'state': state,
            'data': self.state_data
        }
        self._message_queue.put(message)

    def emit_frame(self, frame_rgb, landmarks=None, calibration=None,
                   bone_rotations=None, quality: int = 60, landmarks_2d=None, visibility=None):
        """
        Emit a camera frame to all connected clients (thread-safe).

        Compresses frame as JPEG and encodes as base64 for transmission.
        Target: 30 FPS with ~15-30KB per frame at 60% quality.

        Args:
            frame_rgb: RGB numpy array (H, W, 3)
            landmarks: Optional key landmarks (world coords) for mesh calibration
            calibration: Optional mesh calibration data
            bone_rotations: Optional dict of bone rotations for skeletal animation
                           Format: {'bone_name': {'x': float, 'y': float, 'z': float, 'w': float}}
            quality: JPEG quality (1-100, default 60 for 30 FPS streaming)
            landmarks_2d: Optional 2D pixel landmarks for browser-side keypoint rendering
                         Format: numpy array (33, 3) with [x, y, z] in pixels
            visibility: Optional visibility scores for landmarks (33,) array
        """
        # Encode frame as JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR),
                                  encode_params)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')

        message = {'type': 'frame', 'image': frame_b64}

        if landmarks is not None:
            message['landmarks'] = self._extract_key_landmarks(landmarks)
        if calibration is not None:
            message['calibration'] = calibration
        if bone_rotations is not None:
            message['bone_rotations'] = bone_rotations
        if landmarks_2d is not None:
            # Get frame dimensions for normalizing pixel coordinates to [0-1]
            frame_h, frame_w = frame_rgb.shape[:2]
            # Convert 2D landmarks to normalized [0-1] format for JSON serialization
            message['landmarks_2d'] = self._serialize_landmarks_2d(landmarks_2d, frame_w, frame_h, visibility)
            # Include frame aspect ratio for proper scaling with object-fit: cover
            message['frame_aspect'] = frame_w / frame_h if frame_h > 0 else 1.0

        self._message_queue.put(message)

    def emit_audio_level(self, level: float, threshold: float):
        """
        Emit audio level for waveform visualization (thread-safe).

        Args:
            level: Current audio level (0.0-1.0 normalized)
            threshold: Detection threshold for comparison
        """
        message = {
            'type': 'audio_level',
            'level': level,
            'threshold': threshold
        }
        self._message_queue.put(message)

    def emit_transcription(self, text: str, is_final: bool = True):
        """
        Emit transcribed text from Whisper (thread-safe).

        Args:
            text: Transcribed text
            is_final: Whether this is the final transcription
        """
        message = {
            'type': 'transcription',
            'text': text,
            'is_final': is_final
        }
        self._message_queue.put(message)

    def emit_generation_progress(self, stage: str, percent: float,
                                  message_text: str = ''):
        """
        Emit generation progress update (thread-safe).

        Args:
            stage: Current stage ('2d' or '3d')
            percent: Progress percentage (0-100)
            message_text: Optional status message
        """
        message = {
            'type': 'generation_progress',
            'stage': stage,
            'percent': percent,
            'message': message_text
        }
        self._message_queue.put(message)

    def emit_mesh_ready(self, glb_path: str, texture_b64: str = None):
        """
        Emit mesh data when 3D generation completes (thread-safe).

        Reads the GLB file and sends as base64. Optionally includes a
        texture image to apply if the mesh doesn't have its own texture.

        Args:
            glb_path: Path to the generated GLB file
            texture_b64: Optional base64-encoded texture image (PNG)
        """
        try:
            with open(glb_path, 'rb') as f:
                glb_data = f.read()
            glb_b64 = base64.b64encode(glb_data).decode('utf-8')

            message = {
                'type': 'mesh_ready',
                'glb': glb_b64,
                'size_kb': len(glb_data) / 1024
            }

            # Include texture if provided (for meshes without embedded textures)
            if texture_b64:
                message['texture'] = texture_b64

            print(f"[WebSocket] Queueing mesh_ready ({len(glb_data)/1024:.1f} KB)")
            self._message_queue.put(message)

        except Exception as e:
            print(f"[WebSocket] Error reading GLB file: {e}")

    def emit_preview_image(self, image_path: str):
        """
        Emit the generated 2D preview image (thread-safe).

        Args:
            image_path: Path to the generated image
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            message = {
                'type': 'preview_image',
                'image': image_b64
            }
            self._message_queue.put(message)

        except Exception as e:
            print(f"[WebSocket] Error reading preview image: {e}")

    def emit_preview_mask(self, mask_path: str):
        """
        Emit the mask image for clothing cropping (thread-safe).

        The mask is a white silhouette on black background, used to
        crop the preview image to show only the clothing area.

        Args:
            mask_path: Path to the mask image (PNG with white=clothing)
        """
        try:
            with open(mask_path, 'rb') as f:
                mask_data = f.read()
            mask_b64 = base64.b64encode(mask_data).decode('utf-8')

            message = {
                'type': 'preview_mask',
                'mask': mask_b64
            }
            self._message_queue.put(message)

        except Exception as e:
            print(f"[WebSocket] Error reading mask image: {e}")

    def _extract_key_landmarks(self, landmarks) -> dict:
        """
        Extract key landmarks for mesh overlay tracking.

        Extracts shoulder, hip, and nose landmarks for position/scale calculation.

        Args:
            landmarks: BlazePose landmarks_world array (33x3)

        Returns:
            Dictionary with key landmark positions
        """
        # BlazePose landmark indices
        NOSE = 0
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_HIP = 23
        RIGHT_HIP = 24

        try:
            return {
                'nose': landmarks[NOSE].tolist() if hasattr(landmarks[NOSE], 'tolist')
                        else list(landmarks[NOSE]),
                'left_shoulder': landmarks[LEFT_SHOULDER].tolist() if hasattr(landmarks[LEFT_SHOULDER], 'tolist')
                                 else list(landmarks[LEFT_SHOULDER]),
                'right_shoulder': landmarks[RIGHT_SHOULDER].tolist() if hasattr(landmarks[RIGHT_SHOULDER], 'tolist')
                                  else list(landmarks[RIGHT_SHOULDER]),
                'left_hip': landmarks[LEFT_HIP].tolist() if hasattr(landmarks[LEFT_HIP], 'tolist')
                            else list(landmarks[LEFT_HIP]),
                'right_hip': landmarks[RIGHT_HIP].tolist() if hasattr(landmarks[RIGHT_HIP], 'tolist')
                             else list(landmarks[RIGHT_HIP]),
            }
        except (IndexError, TypeError) as e:
            print(f"[WebSocket] Error extracting landmarks: {e}")
            return {}

    def _serialize_landmarks_2d(self, landmarks_2d, frame_w: int, frame_h: int, visibility=None) -> list:
        """
        Serialize 2D pixel landmarks for browser-side keypoint rendering.

        Uses vectorized numpy operations for performance (called 30x/second).

        Args:
            landmarks_2d: BlazePose landmarks array (33x3) with [x, y, z] in pixels
            frame_w: Width of the camera frame in pixels
            frame_h: Height of the camera frame in pixels
            visibility: Optional visibility array (33,) with scores 0-1

        Returns:
            List of landmark objects: [{x, y, visibility}, ...] with x,y normalized to [0-1]
        """
        try:
            import numpy as np

            # Vectorized normalization (fast - no Python loop)
            coords = np.asarray(landmarks_2d, dtype=np.float32)
            x_norm = coords[:, 0] / frame_w if frame_w > 0 else coords[:, 0] * 0
            y_norm = coords[:, 1] / frame_h if frame_h > 0 else coords[:, 1] * 0

            # Build result list (minimal per-item overhead)
            n = len(x_norm)
            if visibility is not None:
                vis = np.asarray(visibility, dtype=np.float32)
                return [{'x': float(x_norm[i]), 'y': float(y_norm[i]), 'visibility': float(vis[i])}
                        for i in range(n)]
            else:
                return [{'x': float(x_norm[i]), 'y': float(y_norm[i]), 'visibility': 1.0}
                        for i in range(n)]

        except Exception as e:
            print(f"[WebSocket] Error serializing 2D landmarks: {e}")
            return []

    async def start(self):
        """
        Start the WebSocket server.

        This is an async method that should be run in an event loop.
        It will block until the server is stopped.
        """
        self._running = True
        self._loop = asyncio.get_event_loop()

        # Start queue processor as background task
        queue_task = asyncio.create_task(self._process_queue())

        print(f"[WebSocket] Starting server on ws://{self.host}:{self.port}")

        # Configure server with ping/pong to keep connections alive
        async with websockets.serve(
            self.handler,
            self.host,
            self.port,
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=60,   # Wait up to 60s for pong (long for 3D generation)
            close_timeout=10,  # Timeout for close handshake
            max_size=50 * 1024 * 1024,  # 50MB max message size for GLB files
        ):
            print(f"[WebSocket] Server running. Open browser to connect.")
            try:
                await asyncio.Future()  # Run forever
            except asyncio.CancelledError:
                pass

        self._running = False
        queue_task.cancel()
        print("[WebSocket] Server stopped.")

    def stop(self):
        """
        Stop the server gracefully.
        """
        self._running = False


def run_server_in_thread(host: str = 'localhost', port: int = 8765) -> PipelineWebSocketServer:
    """
    Convenience function to start the WebSocket server in a daemon thread.

    Usage:
        server = run_server_in_thread()
        # ... run pipeline ...
        server.emit_state_change('LISTENING')
        server.emit_frame(frame_rgb)

    Args:
        host: Server hostname
        port: Server port

    Returns:
        PipelineWebSocketServer instance for emitting messages
    """
    server = PipelineWebSocketServer(host, port)

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.start())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Give server time to start
    import time
    time.sleep(0.1)

    return server
