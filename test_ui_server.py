#!/usr/bin/env python3
"""
Test UI Server for Spoken Wardrobe

This script starts the WebSocket server and serves the static files,
allowing you to test the UI without running the full pipeline.

Usage:
    python test_ui_server.py

Then open http://localhost:8080 in your browser.

The server will cycle through pipeline states automatically for testing.
"""

import asyncio
import threading
import time
import http.server
import socketserver
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.websocket_server import PipelineWebSocketServer
from src.ui.state_manager import StateManager


class TestPipeline:
    """Simulates the pipeline for UI testing."""

    def __init__(self, ws_server: PipelineWebSocketServer):
        self.ws_server = ws_server
        self.state_manager = StateManager(ws_server)
        self.running = False

    def run_demo_sequence(self):
        """Run through a demo sequence of states."""
        self.running = True

        # Wait for connection
        print("[TestPipeline] Waiting for browser connection...")
        time.sleep(2)

        states = [
            ('IDLE', {'title': 'SPOKEN WARDROBE'}, 3),
            ('LISTENING', {'prompt': 'Describe your clothing idea'}, 3),
            ('RECORDING', {'duration': 5}, 5),  # Shortened to 5s for testing, duration matches state time
            ('TRANSCRIBING', {}, 2),
            ('A_POSE', {'countdown': 3}, 3),  # Duration matches countdown
            ('CAPTURING', {}, 1),
            ('GENERATING_2D', {}, 5),
            ('PREVIEW', {}, 12),  # Enough time to see both stages (10s for transition + 2s extra)
            ('GENERATING_3D', {}, 5),
            ('CALIBRATING', {'countdown': 3}, 3),  # Duration matches countdown
            ('TRY_ON', {}, 8),  # Enough time to see animation (4s) + corner state (4s)
        ]

        while self.running:
            for state, data, duration in states:
                if not self.running:
                    break

                print(f"[TestPipeline] Transitioning to {state}")
                self.state_manager.transition(state, **data)

                # Simulate progress for generation states
                if state == 'GENERATING_2D':
                    for i in range(0, 101, 20):
                        self.ws_server.emit_generation_progress('2d', i, f"Step {i//20}")
                        time.sleep(duration / 5)
                    # Send preview image and mask at end of 2D generation
                    base_path = os.path.dirname(os.path.abspath(__file__))
                    preview_path = os.path.join(base_path, 'static/assets/preview_full.png')
                    mask_path = os.path.join(base_path, 'static/assets/preview_mask.png')
                    if os.path.exists(preview_path):
                        self.ws_server.emit_preview_image(preview_path)
                    if os.path.exists(mask_path):
                        self.ws_server.emit_preview_mask(mask_path)
                elif state == 'GENERATING_3D':
                    for i in range(0, 101, 20):
                        self.ws_server.emit_generation_progress('3d', i, f"Building...")
                        time.sleep(duration / 5)
                    # Send mesh_ready event with a test GLB file
                    base_path = os.path.dirname(os.path.abspath(__file__))
                    mesh_path = os.path.join(base_path, 'static/assets/example_mesh.glb')
                    if os.path.exists(mesh_path):
                        print(f"[TestPipeline] Sending mesh_ready with {mesh_path}")
                        self.ws_server.emit_mesh_ready(mesh_path)
                    else:
                        print(f"[TestPipeline] WARNING: No mesh file found at {mesh_path}")
                elif state == 'LISTENING':
                    # Simulate audio levels for listening state
                    for _ in range(int(duration * 10)):
                        import random
                        level = random.uniform(0.1, 0.8)
                        self.ws_server.emit_audio_level(level, 0.3)
                        time.sleep(0.1)
                elif state == 'RECORDING':
                    # Simulate audio levels and progressive transcription
                    import random
                    transcription_phrases = [
                        "I want",
                        "I want a",
                        "I want a beautiful",
                        "I want a beautiful blue",
                        "I want a beautiful blue dress",
                        "I want a beautiful blue dress with",
                        "I want a beautiful blue dress with flowing",
                        "I want a beautiful blue dress with flowing fabric"
                    ]
                    phrase_interval = duration / len(transcription_phrases)
                    phrase_idx = 0
                    elapsed = 0

                    while elapsed < duration:
                        level = random.uniform(0.1, 0.8)
                        self.ws_server.emit_audio_level(level, 0.3)

                        # Send progressive transcription
                        if phrase_idx < len(transcription_phrases) and elapsed >= phrase_idx * phrase_interval:
                            is_final = phrase_idx == len(transcription_phrases) - 1
                            self.ws_server.emit_transcription(transcription_phrases[phrase_idx], is_final)
                            phrase_idx += 1

                        time.sleep(0.1)
                        elapsed += 0.1
                else:
                    time.sleep(duration)

            print("[TestPipeline] Demo complete, restarting...")

    def stop(self):
        self.running = False


def serve_static_files(port=8080):
    """Serve static files on HTTP."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.chdir(static_dir)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"[HTTP] Serving static files at http://localhost:{port}")
        httpd.serve_forever()


def run_websocket_server(ws_server):
    """Run WebSocket server in its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_server.start())


def main():
    print("=" * 50)
    print("Spoken Wardrobe - UI Test Server")
    print("=" * 50)

    # Create WebSocket server
    ws_server = PipelineWebSocketServer(host='localhost', port=8765)

    # Start WebSocket server in background thread
    ws_thread = threading.Thread(target=run_websocket_server, args=(ws_server,), daemon=True)
    ws_thread.start()
    print("[WebSocket] Server started on ws://localhost:8765")

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=serve_static_files, args=(8080,), daemon=True)
    http_thread.start()

    # Give servers time to start
    time.sleep(1)

    print("\n" + "=" * 50)
    print("Open http://localhost:8080 in your browser")
    print("Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    # Create and run test pipeline
    test_pipeline = TestPipeline(ws_server)

    try:
        test_pipeline.run_demo_sequence()
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        test_pipeline.stop()


if __name__ == '__main__':
    main()
