#!/usr/bin/env python3
"""
Warp Test 0 - Isolated Mesh Loading + Calibration + Try-On Test

This test file uses a pre-existing GLB mesh to debug the mesh loading,
calibration, and warping/try-on flow without running the full pipeline.

Usage:
    python warp_test_0.py

    Then open http://localhost:8080 in browser

This test:
1. Starts HTTP server for static files
2. Starts WebSocket server for real-time communication
3. Initializes OAK-D Pro camera with BlazePose
4. Loads pre-existing mesh: comfyui_generated_mesh/1765596014/clothing_mesh.glb
5. Runs calibration phase (3 seconds)
6. Runs try-on phase (30 seconds) with real-time mesh tracking

Same logic as the main pipeline - fixes can be transferred back.
"""

import sys
from pathlib import Path
import time
import threading
import cv2

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Add BlazePose path for OAK-D Pro
blazepose_path = project_root / "external" / "depthai_blazepose"
sys.path.insert(0, str(blazepose_path))

# Import UI modules
from src.ui.websocket_server import PipelineWebSocketServer, run_server_in_thread
from src.ui.state_manager import StateManager
from src.ui.mesh_calibrator import MeshCalibrator
from src.ui.camera_broadcaster import CameraBroadcaster

# Import OAK-D Pro camera
from BlazeposeDepthaiEdge import BlazeposeDepthai


class WarpTest:
    """Minimal test for mesh loading, calibration, and try-on"""

    # Pre-existing mesh path
    MESH_PATH = project_root / "comfyui_generated_mesh" / "1765596014" / "clothing_mesh.glb"

    def __init__(self):
        print("\n" + "=" * 70)
        print("WARP TEST 0 - Mesh Loading + Calibration + Try-On")
        print("=" * 70)

        # Verify mesh exists
        if not self.MESH_PATH.exists():
            raise FileNotFoundError(f"Mesh not found: {self.MESH_PATH}")
        print(f"✓ Using mesh: {self.MESH_PATH}")

        # Components
        self.ws_server = None
        self.state_manager = None
        self.mesh_calibrator = None
        self.camera_broadcaster = None
        self.tracker = None
        self._http_server = None

        # Initialize servers
        self._init_servers()

        print("=" * 70 + "\n")

    def _init_servers(self):
        """Initialize WebSocket and HTTP servers"""
        print("\n🌐 Starting servers...")

        # Start WebSocket server
        self.ws_server = run_server_in_thread(host='localhost', port=8765)
        self.state_manager = StateManager(self.ws_server)
        self.mesh_calibrator = MeshCalibrator()

        # Start HTTP server for static files
        self._start_http_server(port=8080)

        print("✓ WebSocket server started on ws://localhost:8765")
        print("✓ HTTP server started on http://localhost:8080")
        print("   Open http://localhost:8080 in browser for UI")

    def _start_http_server(self, port=8080):
        """Start HTTP server for static files in background thread"""
        import http.server
        import socketserver

        static_dir = project_root / "static"

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(static_dir), **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress access logs

        # Use ThreadingTCPServer for concurrent request handling
        class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        def serve():
            self._http_server = ThreadingHTTPServer(("", port), QuietHandler)
            self._http_server.serve_forever()

        self._http_server = None
        http_thread = threading.Thread(target=serve, daemon=True)
        http_thread.start()

    def _emit_state(self, state, **data):
        """Emit state change to WebSocket clients"""
        if self.ws_server:
            self.ws_server.emit_state_change(state, data)

    def _init_camera(self):
        """Initialize OAK-D Pro camera with BlazePose"""
        print("\n📷 Initializing OAK-D Pro camera with BlazePose...")

        try:
            self.tracker = BlazeposeDepthai(
                input_src="rgb",
                internal_fps=30,
                xyz=True,  # Enable 3D coordinates for skeletal animation
                internal_frame_height=640
            )
            print("✓ OAK-D Pro camera initialized")

            # Start camera broadcaster for continuous frame streaming
            self.camera_broadcaster = CameraBroadcaster(
                self.tracker,
                self.ws_server,
                target_fps=30
            )
            # Attach mesh calibrator for transform computation
            self.camera_broadcaster.mesh_calibrator = self.mesh_calibrator
            self.camera_broadcaster.start()

            # Wait for first frame
            print("   Waiting for camera frames...")
            frame_data = self.camera_broadcaster.wait_for_frame(timeout=5.0)
            if frame_data:
                print(f"   ✓ Camera streaming ({frame_data.frame_rgb.shape})")
            else:
                print("   ⚠ Camera timeout - check USB connection")

        except Exception as e:
            print(f"✗ Camera initialization failed: {e}")
            raise

    def _wait_for_body(self, timeout=30):
        """Wait for a body to be detected"""
        print("\n👤 Waiting for body detection...")
        self._emit_state('IDLE', title='WARP TEST',
                        subtitle='Step in front of the camera')

        start_time = time.time()
        while time.time() - start_time < timeout:
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data and frame_data.body:
                print("✓ Body detected!")
                return True
            time.sleep(0.1)

        print("⚠ Body detection timeout")
        return False

    def _load_and_emit_mesh(self):
        """Load the pre-existing mesh and emit to browser"""
        print(f"\n📦 Loading mesh: {self.MESH_PATH}")

        # Get texture from cropped clothing if exists (for fallback texture)
        texture_b64 = None
        cropped_path = self.MESH_PATH.parent / "generated_clothing.png"
        if cropped_path.exists():
            import base64
            with open(cropped_path, 'rb') as f:
                texture_b64 = base64.b64encode(f.read()).decode('utf-8')
            print(f"   ✓ Fallback texture loaded: {cropped_path}")

        # Emit mesh to browser via WebSocket
        # This is EXACTLY how the main pipeline does it (line 1746)
        self.ws_server.emit_mesh_ready(str(self.MESH_PATH), texture_b64)
        print("✓ Mesh emitted to WebSocket")

        # Give browser time to load the mesh
        time.sleep(2)

    def _run_calibration_phase(self, duration=3):
        """
        Run the calibration countdown phase.

        User aligns with the mesh in A-pose for 1:1 scale reference.
        After countdown, captures calibration frame and sets mesh_calibrator offset.

        Args:
            duration: Countdown duration in seconds (default: 3)
        """
        print("\n🎯 CALIBRATING PHASE")
        print("   Align yourself with the mesh in A-pose...")

        # Enable skeleton drawing for user feedback
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = True

        # Emit calibrating state with countdown
        self._emit_state('CALIBRATING', countdown=duration)

        # Countdown loop - keep streaming frames
        for remaining in range(duration, 0, -1):
            print(f"   Calibrating in {remaining}...")
            time.sleep(1)

        # Capture calibration frame at end
        if self.camera_broadcaster:
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data and frame_data.body and self.mesh_calibrator:
                # Set calibration offset - mesh will track relative to this pose
                self.mesh_calibrator.calibrate_offset(frame_data.body)
                print("   ✓ Calibration captured")
            else:
                print("   ⚠ Could not capture calibration (no body detected)")

    def _run_tryon_phase(self, duration=30):
        """
        Run the interactive try-on phase.

        User moves around, mesh follows their body in real-time via
        MeshCalibrator transforms sent with each frame.

        Args:
            duration: Try-on duration in seconds (default: 30)
        """
        print("\n👗 TRY_ON PHASE")
        print(f"   Move around to see your clothing ({duration}s)...")

        # Emit try-on state
        self._emit_state('TRY_ON', duration=duration)

        # Keep skeleton drawing enabled for user feedback
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = True

        start_time = time.time()
        last_log_time = start_time

        while time.time() - start_time < duration:
            # CameraBroadcaster is already streaming frames with:
            # - Skeleton overlay (draw_skeleton=True)
            # - Calibration data (mesh_calibrator attached)
            # - Bone rotations for skeletal animation
            # Frontend receives frames and updates mesh transform

            current_time = time.time()
            remaining = duration - (current_time - start_time)

            # Log progress every 5 seconds
            if current_time - last_log_time >= 5:
                print(f"   Try-on: {int(remaining)}s remaining...")
                last_log_time = current_time

            time.sleep(0.1)  # Small sleep to not busy-wait

        print("   ✓ Try-on phase complete")

        # Disable skeleton for next cycle
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = False

    def run(self):
        """Run the test"""
        try:
            # Initialize camera
            self._init_camera()

            # Wait for user to appear
            if not self._wait_for_body():
                print("✗ No body detected, exiting")
                return

            # Show generating state briefly (simulating mesh generation)
            print("\n⏳ Simulating mesh generation (already done)...")
            self._emit_state('GENERATING_3D')
            time.sleep(2)

            # Load and emit the pre-existing mesh
            self._load_and_emit_mesh()

            # Run calibration phase
            self._run_calibration_phase(duration=3)

            # Run try-on phase
            self._run_tryon_phase(duration=30)

            # Done
            print("\n" + "=" * 70)
            print("✅ Warp Test Complete!")
            print("=" * 70)

            self._emit_state('IDLE', title='TEST COMPLETE',
                            subtitle='Mesh loading and try-on test finished')

            # Keep running for additional tests
            print("\n🔄 Press Ctrl+C to exit, or test again by stepping back/forward\n")
            while True:
                if self._wait_for_body(timeout=10):
                    # Run another cycle
                    self._load_and_emit_mesh()
                    self._run_calibration_phase(duration=3)
                    self._run_tryon_phase(duration=30)
                    self._emit_state('IDLE', title='READY',
                                    subtitle='Step in front of camera to try again')
                else:
                    print("   Waiting for body...")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        print("\n🧹 Cleaning up...")

        if self.camera_broadcaster:
            self.camera_broadcaster.stop()
            self.camera_broadcaster.join(timeout=2.0)

        if self.tracker:
            self.tracker.exit()

        if self._http_server:
            self._http_server.shutdown()

        print("✓ Cleanup complete")


if __name__ == "__main__":
    test = WarpTest()
    test.run()
