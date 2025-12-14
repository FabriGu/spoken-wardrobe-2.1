#!/usr/bin/env python3
"""
Speech-to-Clothing Pipeline with Rodin API (Direct)

Integrated pipeline that:
1. Calibrates microphone for ambient noise
2. Listens for user speech about dream dress
3. Transcribes with Whisper
4. Captures body frame with BodyPix segmentation
5. Generates clothing with ComfyUI (2D)
6. Generates 3D mesh with Rodin API (direct, no ComfyUI)
7. Saves all outputs (images, masks, GLB mesh)

Usage:
    # Set API key first
    export RODIN_API_KEY="your_api_key_here"

    # Run pipeline
    python src/modules/speech_to_clothing_with_rodin_api.py [--viewer] [--skip-3d]

Options:
    --viewer    Show OpenCV debug windows (for debugging only)
    --skip-3d   Skip 3D mesh generation (2D only)
"""

import sys
from pathlib import Path
import time
import json
import cv2
import numpy as np
import pyaudio
import threading
import queue
from PIL import Image
import argparse
import requests
import os
import asyncio

# Add paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Add BlazePose path for OAK-D Pro
blazepose_path = project_root / "external" / "depthai_blazepose"
sys.path.insert(0, str(blazepose_path))

# Import existing modules
from modules.speechRecognition import SpeechRecognizer
from modules.comfyui_client import ComfyUIClient
from modules.prompt_enhancer import PromptEnhancer

# Import UI modules (optional - gracefully handle if not available)
try:
    from ui.websocket_server import PipelineWebSocketServer, run_server_in_thread
    from ui.state_manager import StateManager
    from ui.mesh_calibrator import MeshCalibrator
    from ui.camera_broadcaster import CameraBroadcaster
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    MeshCalibrator = None
    CameraBroadcaster = None
    print("Note: WebSocket UI not available. Run without --ui flag.")

# Import BodyPix
from tf_bodypix.api import download_model, load_model, BodyPixModelPaths

# Import OAK-D Pro camera
from BlazeposeDepthaiEdge import BlazeposeDepthai


class BodyPartSelector:
    """Selects body parts for dress"""

    DRESS_PARTS = [
        'torso_front', 'torso_back',
        'left_upper_arm_front', 'left_upper_arm_back',
        'left_lower_arm_front', 'left_lower_arm_back',
        'right_upper_arm_front', 'right_upper_arm_back',
        'right_lower_arm_front', 'right_lower_arm_back',
        'left_upper_leg_front', 'left_upper_leg_back',
        'right_upper_leg_front', 'right_upper_leg_back',
    ]


class SpeechToClothingPipeline:
    """Main pipeline orchestrator with direct Rodin API integration"""

    def __init__(self, comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199", show_viewer=False, enable_3d=True, rodin_api_key=None, enable_ui=False):
        """Initialize pipeline components"""

        print("\n" + "="*70)
        print("Speech-to-Clothing Pipeline with Rodin API (Direct)")
        print("="*70)

        # Configuration
        self.comfyui_url = comfyui_url
        self.workflow_path_2d = "workflows/sdxl_inpainting_api.json"
        self.show_viewer = show_viewer
        self.enable_3d = enable_3d

        # Rodin API configuration
        self.rodin_api_key = rodin_api_key or os.environ.get('RODIN_API_KEY')
        self.rodin_base_url = "https://api.hyper3d.com/api/v2"

        if self.enable_3d and not self.rodin_api_key:
            print("\n⚠️  WARNING: RODIN_API_KEY not set!")
            print("   3D generation will fail without API key.")
            print("   Set it with: export RODIN_API_KEY='your_key'")
            print("   Get key from: https://hyperhuman.deemos.com/")

        # Components (lazy loaded)
        self.speech_recognizer = None
        self.comfyui_client = None
        self.bodypix_model = None
        self.prompt_enhancer = None

        # OAK-D Pro Camera
        self.tracker = None
        self.renderer = None

        # State
        self.current_state = "CALIBRATING"
        self.ambient_noise_level = 0
        self.volume_threshold = 0
        self.transcribed_text = ""
        self.generated_image = None

        # Audio recording
        self.audio_chunks = []
        self.recording_duration = 10.0
        self.recording_start_time = None
        self.mic_index = None

        # WebSocket UI integration
        self.enable_ui = enable_ui and UI_AVAILABLE
        self.ws_server = None
        self.state_manager = None
        self.mesh_calibrator = None
        self.camera_broadcaster = None
        self.http_server_thread = None

        if self.enable_ui:
            self._init_ui()

        print("✓ Pipeline initialized")
        if self.enable_3d:
            print("✓ 3D mesh generation enabled (Rodin API Direct)")
            if self.rodin_api_key:
                print(f"✓ API key configured: {self.rodin_api_key[:8]}...{self.rodin_api_key[-4:]}")
        else:
            print("⚠ 3D mesh generation disabled")
        print("="*70 + "\n")

    def _init_ui(self):
        """Initialize WebSocket UI server and HTTP server in background threads"""
        print("\n🌐 Starting UI servers...")

        # Start WebSocket server
        self.ws_server = run_server_in_thread(host='localhost', port=8765)
        self.state_manager = StateManager(self.ws_server)
        self.mesh_calibrator = MeshCalibrator() if MeshCalibrator else None

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
        # This prevents ERR_CONNECTION_REFUSED when browser makes multiple requests
        class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        def serve():
            self._http_server = ThreadingHTTPServer(("", port), QuietHandler)
            self._http_server.serve_forever()

        self._http_server = None
        self.http_server_thread = threading.Thread(target=serve, daemon=True)
        self.http_server_thread.start()

    def cleanup(self):
        """Clean up all resources before exit to prevent mutex errors"""
        print("\n🧹 Cleaning up resources...")

        # Stop camera broadcaster first (it's sending frames)
        if self.camera_broadcaster:
            try:
                self.camera_broadcaster.stop()
                print("  ✓ Camera broadcaster stopped")
            except Exception as e:
                print(f"  ⚠ Camera broadcaster cleanup error: {e}")

        # Stop the OAK-D camera/tracker
        if self.tracker:
            try:
                # BlazePose tracker cleanup
                if hasattr(self.tracker, 'device'):
                    self.tracker.device.close()
                self.tracker = None
                print("  ✓ OAK-D camera closed")
            except Exception as e:
                print(f"  ⚠ Camera cleanup error: {e}")

        # Stop WebSocket server
        if self.ws_server:
            try:
                self.ws_server.stop()
                print("  ✓ WebSocket server stopped")
            except Exception as e:
                print(f"  ⚠ WebSocket cleanup error: {e}")

        # Stop HTTP server
        if hasattr(self, '_http_server') and self._http_server:
            try:
                self._http_server.shutdown()
                print("  ✓ HTTP server stopped")
            except Exception as e:
                print(f"  ⚠ HTTP server cleanup error: {e}")

        # Close any OpenCV windows
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        # Give threads time to finish
        time.sleep(0.5)
        print("  ✓ Cleanup complete")

    def _emit_state(self, state, **data):
        """Emit state change to UI (if enabled)"""
        if self.state_manager:
            self.state_manager.transition(state, **data)

    def _emit_frame(self, frame_rgb, body=None):
        """Emit camera frame to UI (if enabled)"""
        if self.ws_server and hasattr(frame_rgb, 'shape'):
            landmarks = None
            calibration = None

            if body and hasattr(body, 'landmarks_world'):
                landmarks = body.landmarks_world

                # Compute calibration transform from body landmarks
                if self.mesh_calibrator:
                    calibration = self.mesh_calibrator.compute_transform(body)

            self.ws_server.emit_frame(frame_rgb, landmarks, calibration)

    def _emit_audio_level(self, level):
        """Emit audio level to UI (if enabled)"""
        if self.ws_server:
            normalized_level = min(1.0, level / max(1, self.volume_threshold * 2))
            self.ws_server.emit_audio_level(normalized_level, 0.5)

    def find_microphone_by_name(self, target_name="MacBook Pro Microphone"):
        """Find microphone device index by name"""
        audio = pyaudio.PyAudio()

        print("\n🎤 Available audio input devices:")
        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                device_name = device_info['name']
                print(f"  {i}: {device_name}")

                if target_name in device_name:
                    audio.terminate()
                    print(f"\n✓ Found '{target_name}' at index {i}")
                    return i

        audio.terminate()
        print(f"\n⚠ Could not find '{target_name}', using default device")
        return None

    def calibrate_microphone(self, duration=3.0):
        """Calibrate microphone by recording ambient noise"""
        print(f"\n🎤 Calibrating microphone ({duration}s)...")
        print("   Please stay quiet...")

        mic_index = self.find_microphone_by_name("MacBook Pro Microphone")
        if mic_index is None:
            print("⚠ Using default microphone")

        audio = pyaudio.PyAudio()

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
                input_device_index=mic_index
            )

            print(f"✓ Opened microphone (device {mic_index})")
            self.mic_index = mic_index

            volume_samples = []
            start_time = time.time()

            while (time.time() - start_time) < duration:
                try:
                    audio_data = stream.read(1024, exception_on_overflow=False)
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    audio_float = audio_array.astype(np.float32)
                    volume = np.sqrt(np.mean(audio_float**2))
                    volume_samples.append(volume)
                except Exception as e:
                    print(f"   Error reading audio: {e}")
                    continue

            self.ambient_noise_level = np.mean(volume_samples)
            self.volume_threshold = self.ambient_noise_level * 2.5

            if self.volume_threshold < 50:
                print(f"   ⚠ Calculated threshold {self.volume_threshold:.0f} is very low")
                print(f"   Setting minimum threshold of 50")
                self.volume_threshold = 50

            stream.stop_stream()
            stream.close()

            print(f"\n✓ Calibration complete!")
            print(f"   Ambient noise: {self.ambient_noise_level:.0f}")
            print(f"   Speech threshold: {self.volume_threshold:.0f}")

            return self.ambient_noise_level

        except Exception as e:
            print(f"✗ Calibration failed: {e}")
            import traceback
            traceback.print_exc()
            self.volume_threshold = 500
            self.mic_index = None
            return 0

        finally:
            audio.terminate()

    def initialize_camera(self):
        """Initialize OAK-D Pro camera with BlazePose"""
        print("\n📷 Initializing OAK-D Pro camera...")

        self.tracker = BlazeposeDepthai(
            input_src='rgb',
            lm_model='lite',
            xyz=True,
            smoothing=True,
            internal_fps=30,
            internal_frame_height=640,
            stats=False,
            trace=False
        )

        if self.show_viewer:
            from BlazeposeRenderer import BlazeposeRenderer
            self.renderer = BlazeposeRenderer(self.tracker, show_3d=None, output=None)

        print("✓ OAK-D Pro initialized")

        # Start camera broadcaster for continuous streaming (if UI enabled)
        if self.enable_ui and CameraBroadcaster:
            print("📹 Starting camera broadcaster...")
            self.camera_broadcaster = CameraBroadcaster(
                tracker=self.tracker,
                ws_server=self.ws_server,
                target_fps=30
            )
            # Attach mesh calibrator for transform computation
            if self.mesh_calibrator:
                self.camera_broadcaster.mesh_calibrator = self.mesh_calibrator
            self.camera_broadcaster.start()

            # Wait for first frame
            first_frame = self.camera_broadcaster.wait_for_frame(timeout=5.0)
            if first_frame:
                print("✓ Camera broadcaster started - streaming to UI")
            else:
                print("⚠ Camera broadcaster started but no frames yet")

    def is_body_detected(self, body):
        """Check if a body is detected by BlazePose"""
        if body and hasattr(body, 'landmarks_world'):
            return True
        return False

    def get_frame(self):
        """
        Get a frame from camera (non-blocking if broadcaster is running).

        When broadcaster is active, returns the latest frame without blocking.
        When broadcaster is not active, calls tracker.next_frame() directly (blocking).

        Returns:
            (frame, body) tuple, or (None, None) if no frame available
        """
        if self.camera_broadcaster and self.camera_broadcaster.is_running:
            # Non-blocking: get latest frame from broadcaster
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data:
                # Convert RGB back to BGR for consistency with tracker
                frame_bgr = cv2.cvtColor(frame_data.frame_rgb, cv2.COLOR_RGB2BGR)
                return frame_bgr, frame_data.body
            return None, None
        else:
            # Blocking: direct tracker call (fallback)
            return self.tracker.next_frame()

    def record_speech_with_live_transcription(self):
        """
        Record speech for fixed duration with periodic live transcription.

        Every 2 seconds, transcribes accumulated audio and emits partial results
        to the UI for real-time feedback.
        """
        print(f"\n🎙️  Recording for {self.recording_duration} seconds with live transcription...")

        audio = pyaudio.PyAudio()
        transcription_interval = 2.0  # Transcribe every 2 seconds

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
                input_device_index=self.mic_index
            )

            audio_chunks = []
            self.recording_start_time = time.time()
            last_transcription_time = self.recording_start_time
            partial_transcription = ""

            # Ensure Whisper model is loaded before recording loop
            if not self.speech_recognizer:
                print("   Loading Whisper model for live transcription...")
                self.speech_recognizer = SpeechRecognizer(modelSize="base")
                self.speech_recognizer.loadWhisperModel()

            while (time.time() - self.recording_start_time) < self.recording_duration:
                try:
                    audio_data = stream.read(1024, exception_on_overflow=False)
                    audio_chunks.append(audio_data)

                    elapsed = time.time() - self.recording_start_time
                    remaining = self.recording_duration - elapsed

                    # Emit audio level for waveform
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    level = np.sqrt(np.mean(audio_array**2))
                    self._emit_audio_level(level)

                    # Periodic live transcription (every 2 seconds)
                    if (time.time() - last_transcription_time) >= transcription_interval:
                        if len(audio_chunks) > 0:
                            # Transcribe accumulated audio
                            accumulated_audio = b''.join(audio_chunks)
                            partial_transcription = self._quick_transcribe(accumulated_audio)

                            if partial_transcription and self.ws_server:
                                self.ws_server.emit_transcription(partial_transcription, is_final=False)
                                print(f"   Partial: \"{partial_transcription}\"")

                            last_transcription_time = time.time()

                except Exception as e:
                    continue

            stream.stop_stream()
            stream.close()

            print(f"✓ Recording complete ({len(audio_chunks)} chunks)")
            return b''.join(audio_chunks)

        except Exception as e:
            print(f"✗ Recording failed: {e}")
            return None

        finally:
            audio.terminate()

    def _quick_transcribe(self, audio_data):
        """
        Quick transcription of audio data for live feedback.

        Uses the already-loaded Whisper model to transcribe without
        reloading. Returns empty string on error.
        """
        if not self.speech_recognizer:
            return ""

        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0

            inputs = self.speech_recognizer.processor(
                audio_float,
                sampling_rate=16000,
                return_tensors="pt"
            )
            inputs = inputs.input_features.to(self.speech_recognizer.device)

            import torch
            with torch.no_grad():
                predicted_ids = self.speech_recognizer.model.generate(inputs, max_new_tokens=128)

            transcription = self.speech_recognizer.processor.batch_decode(
                predicted_ids,
                skip_special_tokens=True
            )[0].strip()

            return transcription

        except Exception as e:
            return ""

    def record_speech_fixed_duration(self):
        """Record speech for exactly 10 seconds once triggered (legacy, non-live version)"""
        # Use the new live transcription version
        return self.record_speech_with_live_transcription()

    def transcribe_with_whisper(self, audio_data):
        """Transcribe audio using Whisper"""
        if not self.speech_recognizer:
            print("\n📝 Loading Whisper model...")
            self.speech_recognizer = SpeechRecognizer(modelSize="base")
            self.speech_recognizer.loadWhisperModel()

        print("\n📝 Transcribing with Whisper...")

        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0

            inputs = self.speech_recognizer.processor(
                audio_float,
                sampling_rate=16000,
                return_tensors="pt"
            )

            inputs = inputs.input_features.to(self.speech_recognizer.device)

            with np.errstate(all='ignore'):
                import torch
                with torch.no_grad():
                    predicted_ids = self.speech_recognizer.model.generate(inputs)

            transcription = self.speech_recognizer.processor.batch_decode(
                predicted_ids,
                skip_special_tokens=True
            )[0].strip()

            print("="*70)
            print(f"✅ Transcription: '{transcription}'")
            print("="*70)

            return transcription

        except Exception as e:
            print(f"\n✗ Transcription failed: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def capture_frame_with_bodypix(self, clean_frame):
        """Generate dress mask with BodyPix from clean frame"""
        print("\n📸 Processing captured frame with BodyPix...")

        if not self.bodypix_model:
            print("🎭 Loading BodyPix model...")
            self.bodypix_model = load_model(download_model(
                BodyPixModelPaths.MOBILENET_FLOAT_75_STRIDE_16
            ))
            print("✓ BodyPix loaded")

        print("🎭 Running BodyPix segmentation...")
        start_time = time.time()

        frame_rgb = cv2.cvtColor(clean_frame, cv2.COLOR_BGR2RGB)
        result = self.bodypix_model.predict_single(frame_rgb)

        person_mask = result.get_mask(threshold=0.75)
        dress_parts = BodyPartSelector.DRESS_PARTS
        body_part_mask = result.get_part_mask(person_mask, part_names=dress_parts)

        if hasattr(body_part_mask, 'numpy'):
            body_part_mask = body_part_mask.numpy()
        body_part_mask = np.squeeze(body_part_mask)

        mask = (body_part_mask > 0).astype(np.uint8) * 255

        elapsed = time.time() - start_time
        print(f"✓ BodyPix complete in {elapsed:.2f}s")

        return frame_rgb, mask

    def segment_body_parts(self, frame_rgb):
        """
        Segment body parts from an RGB frame using BodyPix.

        This is a simpler version of capture_frame_with_bodypix() that
        takes an already-RGB frame and returns only the mask.

        Args:
            frame_rgb: RGB frame (numpy array, H x W x 3)

        Returns:
            mask: Binary mask (numpy array, H x W) where 255=body parts
        """
        if not self.bodypix_model:
            print("🎭 Loading BodyPix model...")
            self.bodypix_model = load_model(download_model(
                BodyPixModelPaths.MOBILENET_FLOAT_75_STRIDE_16
            ))
            print("✓ BodyPix loaded")

        start_time = time.time()

        result = self.bodypix_model.predict_single(frame_rgb)

        person_mask = result.get_mask(threshold=0.75)
        dress_parts = BodyPartSelector.DRESS_PARTS
        body_part_mask = result.get_part_mask(person_mask, part_names=dress_parts)

        if hasattr(body_part_mask, 'numpy'):
            body_part_mask = body_part_mask.numpy()
        body_part_mask = np.squeeze(body_part_mask)

        mask = (body_part_mask > 0).astype(np.uint8) * 255

        elapsed = time.time() - start_time
        print(f"✓ BodyPix segmentation complete in {elapsed:.2f}s")

        return mask

    def generate_clothing_with_comfyui(self, frame, mask, prompt):
        """Generate clothing image using ComfyUI"""
        if not self.comfyui_client:
            print("\n🌐 Initializing ComfyUI client...")
            self.comfyui_client = ComfyUIClient(self.comfyui_url)

        # Initialize prompt enhancer if not already done
        if not self.prompt_enhancer:
            print("🎨 Initializing AI prompt enhancer...")
            self.prompt_enhancer = PromptEnhancer(use_llm=True)

        print(f"\n🎨 Generating 2D clothing with ComfyUI...")
        print(f"   Original prompt: '{prompt}'")

        # Enhance the prompt for more creative, non-sexualized results
        enhanced_prompt = self.prompt_enhancer.enhance(prompt)
        print(f"   Enhanced prompt: '{enhanced_prompt}'")

        seed = 100
        steps = 35
        cfg = 9.5

        # Build final prompt with enhanced version + quality modifiers
        final_prompt = f"{enhanced_prompt}, detailed fabric texture, studio lighting, high quality, photorealistic, fashion photography"

        # Comprehensive negative prompt to avoid sexualized/low-quality outputs
        negative_prompt = (
            "sexy, seductive, revealing, provocative, nsfw, nude, naked, "
            "cleavage, skin, exposed body, tight clothing, form-fitting, "
            "low quality, blurry, distorted, deformed, ugly, bad anatomy, "
            "watermark, text, amateur, simple, plain, boring, generic, "
            "cartoon, anime, illustration, drawing, sketch, painting"
        )

        try:
            result = self.comfyui_client.generate_inpainting(
                image=frame,
                mask=mask,
                prompt=final_prompt,
                negative_prompt=negative_prompt,
                workflow_path=self.workflow_path_2d,
                seed=seed,
                steps=steps,
                cfg=cfg
            )

            return result

        except Exception as e:
            print(f"✗ Generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _crop_clothing_with_mask(self, result_image, mask):
        """
        Crop clothing from 2D generated image using BodyPix mask.

        The BodyPix mask indicates body parts that should have clothing.
        This function extracts ONLY those regions from the generated image,
        creating an image with transparent background elsewhere.

        This is CRITICAL for Rodin API - we want to generate a 3D mesh of
        just the clothing, not the entire body.

        Args:
            result_image: PIL Image - 2D generated image with clothing on body
            mask: numpy array - BodyPix mask where 255=clothing regions, 0=background

        Returns:
            PIL Image (RGBA) with clothing on transparent background
        """
        print("\n✂️  Cropping clothing from generated image...")

        # Convert PIL Image to numpy array
        result_array = np.array(result_image)

        # Ensure mask matches image dimensions
        if mask.shape[:2] != result_array.shape[:2]:
            print(f"   Resizing mask from {mask.shape[:2]} to {result_array.shape[:2]}")
            mask = cv2.resize(mask, (result_array.shape[1], result_array.shape[0]),
                            interpolation=cv2.INTER_NEAREST)

        # Apply morphological operations to clean up the mask
        # Dilate slightly to ensure we capture edge pixels of clothing
        kernel = np.ones((5, 5), np.uint8)
        mask_dilated = cv2.dilate(mask, kernel, iterations=2)

        # Optional: Gaussian blur the mask edges for smoother cropping
        mask_blurred = cv2.GaussianBlur(mask_dilated.astype(np.float32), (7, 7), 0)
        mask_normalized = (mask_blurred / 255.0).clip(0, 1)

        # Create RGBA output (add alpha channel)
        if result_array.shape[2] == 3:
            # Add alpha channel
            rgba_array = np.zeros((result_array.shape[0], result_array.shape[1], 4), dtype=np.uint8)
            rgba_array[:, :, :3] = result_array
        else:
            rgba_array = result_array.copy()

        # Set alpha channel based on mask
        # Where mask > 0, alpha = 255 (opaque)
        # Where mask = 0, alpha = 0 (transparent)
        rgba_array[:, :, 3] = (mask_normalized * 255).astype(np.uint8)

        # Convert back to PIL Image
        cropped_image = Image.fromarray(rgba_array, mode='RGBA')

        # Calculate crop bounds (optional: tightly crop to content)
        # Find bounding box of non-transparent pixels
        alpha = rgba_array[:, :, 3]
        rows = np.any(alpha > 0, axis=1)
        cols = np.any(alpha > 0, axis=0)

        if rows.any() and cols.any():
            row_min, row_max = np.where(rows)[0][[0, -1]]
            col_min, col_max = np.where(cols)[0][[0, -1]]

            # Add padding (10% on each side)
            height, width = alpha.shape
            pad_h = int((row_max - row_min) * 0.1)
            pad_w = int((col_max - col_min) * 0.1)

            row_min = max(0, row_min - pad_h)
            row_max = min(height, row_max + pad_h)
            col_min = max(0, col_min - pad_w)
            col_max = min(width, col_max + pad_w)

            # Crop to bounding box
            cropped_image = cropped_image.crop((col_min, row_min, col_max, row_max))
            print(f"   Cropped to bounding box: {col_max - col_min}x{row_max - row_min}")

        # Log stats
        visible_pixels = np.sum(alpha > 0)
        total_pixels = alpha.size
        coverage = visible_pixels / total_pixels * 100
        print(f"   ✓ Clothing extracted ({coverage:.1f}% coverage, {visible_pixels} pixels)")

        return cropped_image

    def submit_rodin_task(self, image_path):
        """
        Submit task to Rodin API (Regular tier).

        Args:
            image_path: Path to input image

        Returns:
            (task_uuid, subscription_key) tuple, or (None, None) if failed
        """
        url = f"{self.rodin_base_url}/rodin"

        try:
            # Read the image file
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()

            # Prepare multipart form data
            files = {
                'images': (os.path.basename(str(image_path)), image_data, 'image/png')
            }

            # Set tier to Regular with low-poly settings
            data = {
                'tier': 'Regular',
                'quality_override': '5000',      # ~5000 faces (low-poly)
                'material': 'PBR',               # Include texture files
                'mesh_mode': 'Raw',              # Triangular faces (simpler)
                'mesh_simplify': 'true',         # Simplify mesh
                'geometry_file_format': 'glb'   # GLB format
            }

            # Prepare headers
            headers = {
                'Authorization': f'Bearer {self.rodin_api_key}',
            }

            print(f"   Submitting to Rodin API...")
            response = requests.post(url, files=files, data=data, headers=headers, timeout=30)

            # Accept both 200 (OK) and 201 (Created) as success
            if response.status_code not in [200, 201]:
                print(f"   ✗ API error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return None, None

            result = response.json()

            # Check for errors
            if result.get('error'):
                print(f"   ✗ API error: {result['error']}")
                return None, None

            task_uuid = result.get('uuid')
            subscription_key = result.get('jobs', {}).get('subscription_key')

            if not task_uuid or not subscription_key:
                print(f"   ✗ Invalid response format")
                print(f"   Response: {result}")
                return None, None

            print(f"   ✓ Task submitted: {task_uuid}")
            return task_uuid, subscription_key

        except requests.exceptions.Timeout:
            print(f"   ✗ Request timed out")
            return None, None
        except Exception as e:
            print(f"   ✗ Submission failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def check_rodin_status(self, subscription_key):
        """
        Check status of Rodin task.

        Args:
            subscription_key: Subscription key from submit response

        Returns:
            List of job statuses, or None if failed
        """
        url = f"{self.rodin_base_url}/status"

        headers = {
            'Authorization': f'Bearer {self.rodin_api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'subscription_key': subscription_key
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)

            # Accept both 200 (OK) and 201 (Created) as success
            if response.status_code not in [200, 201]:
                print(f"   ✗ Status check error: HTTP {response.status_code}")
                return None

            result = response.json()
            return result.get('jobs', [])

        except Exception as e:
            print(f"   ✗ Status check failed: {e}")
            return None

    def download_rodin_results(self, task_uuid, output_dir):
        """
        Download results from completed Rodin task.

        Args:
            task_uuid: Task UUID from submit response
            output_dir: Directory to save files

        Returns:
            Path to downloaded GLB file, or None if failed
        """
        url = f"{self.rodin_base_url}/download"

        headers = {
            'Authorization': f'Bearer {self.rodin_api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'task_uuid': task_uuid
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)

            # Accept both 200 (OK) and 201 (Created) as success
            if response.status_code not in [200, 201]:
                print(f"   ✗ Download request error: HTTP {response.status_code}")
                return None

            result = response.json()
            download_list = result.get('list', [])

            if not download_list:
                print(f"   ✗ No files available for download")
                return None

            # Download each file
            glb_path = None
            for item in download_list:
                file_url = item.get('url')
                file_name = item.get('name')

                if not file_url or not file_name:
                    continue

                print(f"   Downloading: {file_name}")

                # Download file
                file_response = requests.get(file_url, timeout=60)

                if file_response.status_code == 200:
                    dest_path = Path(output_dir) / file_name
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(dest_path, 'wb') as f:
                        f.write(file_response.content)

                    print(f"   ✓ Saved: {dest_path} ({len(file_response.content)/1024:.1f} KB)")

                    # Track GLB file
                    if file_name.endswith('.glb'):
                        glb_path = dest_path
                else:
                    print(f"   ✗ Download failed: HTTP {file_response.status_code}")

            return glb_path

        except Exception as e:
            print(f"   ✗ Download failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_3d_mesh_with_rodin_api(self, image_path):
        """
        Generate 3D mesh using Rodin API directly (not via ComfyUI).

        Args:
            image_path: Path to 2D clothing image

        Returns:
            Path to GLB file, or None if failed
        """
        print(f"\n🎲 Generating 3D mesh with Rodin API (Direct)...")
        print(f"   Input: {image_path}")
        print(f"   Tier: Regular")
        print(f"   This may take 60-90 seconds...")

        # Send initial progress update
        self._emit_3d_progress(0, "Initializing 3D generation...")

        if not self.rodin_api_key:
            print("✗ RODIN_API_KEY not set!")
            self._emit_3d_progress(0, "Error: API key not configured")
            return None

        # Step 1: Submit task
        self._emit_3d_progress(5, "Submitting to Rodin API...")
        try:
            task_uuid, subscription_key = self.submit_rodin_task(image_path)
        except Exception as e:
            print(f"✗ Exception submitting task: {e}")
            self._emit_3d_progress(0, f"Submit error: {str(e)[:50]}")
            return None

        if not task_uuid or not subscription_key:
            print("✗ Failed to submit task")
            self._emit_3d_progress(0, "Failed to submit task")
            return None

        self._emit_3d_progress(10, "Task submitted, generating mesh...")

        # Step 2: Poll status until done
        print(f"   ⏳ Waiting for generation...")
        start_time = time.time()
        poll_interval = 5  # seconds
        max_wait = 300  # 5 minutes

        status_list = []
        poll_count = 0
        while (time.time() - start_time) < max_wait:
            time.sleep(poll_interval)
            poll_count += 1

            try:
                status_list = self.check_rodin_status(subscription_key)
            except Exception as e:
                print(f"   ⚠ Status check exception: {e}")
                self._emit_3d_progress(10 + poll_count, f"Checking status... (retry)")
                continue

            if not status_list:
                print(f"   ⚠ Status check failed, retrying...")
                self._emit_3d_progress(10 + poll_count, "Checking status... (retry)")
                continue

            # Calculate progress based on elapsed time (assume 90s total)
            elapsed = time.time() - start_time
            progress = min(85, 10 + int((elapsed / 90) * 75))

            # Print status
            all_done = True
            status_msg = "Generating..."
            for job in status_list:
                job_status = job.get('status', 'Unknown')
                job_uuid = job.get('uuid', '')[:8]
                print(f"   Job {job_uuid}: {job_status}")
                status_msg = f"Status: {job_status}"

                if job_status not in ['Done', 'Failed']:
                    all_done = False

            self._emit_3d_progress(progress, status_msg)

            # Check if all done
            if all_done:
                # Check if any failed
                if any(job.get('status') == 'Failed' for job in status_list):
                    print("✗ Generation failed")
                    self._emit_3d_progress(0, "Generation failed on server")
                    return None

                # All done successfully
                elapsed = time.time() - start_time
                print(f"✓ Generation complete in {elapsed:.1f}s")
                self._emit_3d_progress(90, "Generation complete!")
                break
        else:
            # Timeout
            print(f"✗ Generation timed out after {max_wait}s")
            self._emit_3d_progress(0, f"Timeout after {max_wait}s")
            return None

        # Step 3: Download results
        print(f"   📥 Downloading mesh...")
        self._emit_3d_progress(92, "Downloading mesh...")
        temp_dir = Path("/tmp") / f"rodin_output_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            glb_path = self.download_rodin_results(task_uuid, temp_dir)
        except Exception as e:
            print(f"✗ Download exception: {e}")
            self._emit_3d_progress(0, f"Download error: {str(e)[:50]}")
            return None

        if glb_path and glb_path.exists():
            print(f"✓ Mesh downloaded: {glb_path}")
            self._emit_3d_progress(100, "Mesh ready!")
            return glb_path
        else:
            print("✗ Failed to download mesh")
            self._emit_3d_progress(0, "Failed to download mesh")
            return None

    def _emit_3d_progress(self, percent, message):
        """Emit 3D generation progress to the UI."""
        if self.ws_server:
            self.ws_server.emit_generation_progress('3d', percent, message)

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

        # Reset mesh calibrator to clear previous offset (prevents sudden jumps)
        if self.mesh_calibrator:
            self.mesh_calibrator.reset()
            print("   ✓ Calibrator reset")

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
            # Frontend receives frames and updates mesh transform

            current_time = time.time()
            remaining = duration - (current_time - start_time)

            # Log progress every 5 seconds
            if current_time - last_log_time >= 5:
                print(f"   Try-on: {int(remaining)}s remaining...")
                last_log_time = current_time

            time.sleep(0.1)  # Small sleep to not busy-wait

        print("   ✓ Try-on phase complete")

        # Disable skeleton for next cycle (clean frames for next A-pose capture)
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = False

    def capture_clean_frame_for_bodypix(self):
        """
        Capture frame WITHOUT skeleton overlay for BodyPix processing.

        Temporarily disables skeleton drawing to get a clean frame
        suitable for Stable Diffusion inpainting.

        Returns:
            Tuple of (frame_rgb, body) or (None, None) if unavailable
        """
        if not self.camera_broadcaster:
            return None, None

        # Temporarily disable skeleton
        prev_state = self.camera_broadcaster.draw_skeleton
        self.camera_broadcaster.draw_skeleton = False

        # Wait for next clean frame
        time.sleep(0.05)

        frame_data = self.camera_broadcaster.get_latest_frame()

        # Restore previous state
        self.camera_broadcaster.draw_skeleton = prev_state

        if frame_data:
            return frame_data.frame_rgb, frame_data.body

        return None, None

    def save_generated_outputs(self, frame_rgb, mask, generated_image, transcription, settings, mesh_path=None):
        """
        Save all outputs to organized folders.

        Args:
            frame_rgb: Original RGB frame
            mask: Body part mask
            generated_image: PIL Image result (2D)
            transcription: Prompt text
            settings: Dict with seed, steps, cfg
            mesh_path: Path to GLB mesh file (optional)
        """
        timestamp = int(time.time())
        output_dir = Path("comfyui_generated_mesh") / str(timestamp)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 Saving to: {output_dir}")

        # Save original frame
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(output_dir / "original_frame.png"), frame_bgr)
        print(f"  ✓ original_frame.png")

        # Save mask
        cv2.imwrite(str(output_dir / "mask.png"), mask)
        print(f"  ✓ mask.png")

        # Save generated 2D clothing
        generated_image.save(str(output_dir / "generated_clothing.png"))
        print(f"  ✓ generated_clothing.png")

        # Save GLB mesh
        if mesh_path and mesh_path.exists():
            import shutil
            glb_dest = output_dir / "clothing_mesh.glb"
            shutil.copy(mesh_path, glb_dest)
            print(f"  ✓ clothing_mesh.glb ({mesh_path.stat().st_size / 1024:.1f} KB)")

        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "transcription": transcription,
            "settings_2d": settings,
            "has_3d_mesh": mesh_path is not None,
            "3d_generation_method": "rodin_api_direct"
        }
        with open(output_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ metadata.json")

        print(f"\n✅ All files saved to: {output_dir}")

        return output_dir

    def send_update(self, data):
        """Send update to viewer"""
        if data["type"] == "recording_progress":
            print(f"   Recording... {data['remaining']:.1f}s remaining", end='\r')

    def run(self):
        """Main pipeline execution - loops continuously for installation mode."""

        print("\n" + "="*70)
        print("Starting Pipeline (Installation Mode)")
        print("="*70)
        print("   Press Ctrl+C to exit\n")

        # Emit initial state to UI
        self._emit_state('IDLE', title='SPOKEN WARDROBE')

        # Step 1-8: Same as original (calibrate, detect body, record, transcribe, capture, generate 2D)
        self.current_state = "CALIBRATING"
        self.calibrate_microphone(duration=3.0)

        self.initialize_camera()

        self.current_state = "WAITING_FOR_BODY"
        self._emit_state('IDLE', title='SPOKEN WARDROBE', subtitle='Step in front of the camera')
        print("\n👤 Waiting for body detection...")
        print("   Stand in front of OAK-D camera...")

        body_detected = False
        while not body_detected:
            frame, body = self.get_frame()
            if frame is None:
                time.sleep(0.05)  # Brief sleep if no frame yet
                continue

            body_detected = self.is_body_detected(body)

            if self.show_viewer:
                display_frame = self.renderer.draw(frame, body) if self.renderer else frame
                cv2.imshow("Speech to Clothing", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nExiting...")
                    if self.show_viewer:
                        cv2.destroyAllWindows()
                    return

        print("✓ Body detected!")

        self.current_state = "WAITING_FOR_SPEECH"
        self._emit_state('LISTENING', prompt='Describe your clothing idea')
        print("\n🎤 Listening for speech...")
        print("   Say: 'Describe your dream dress using your imagination'")
        print(f"   Speak when volume > {self.volume_threshold:.0f}")

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            input_device_index=self.mic_index
        )

        speech_detected = False
        while not speech_detected:
            try:
                audio_data = stream.read(1024, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_float = audio_array.astype(np.float32)
                volume = np.sqrt(np.mean(audio_float**2))

                if volume > self.volume_threshold:
                    print(f"\n✓ Speech detected! (volume: {volume:.0f})")
                    speech_detected = True
                    break

                if self.show_viewer:
                    frame, body = self.get_frame()
                    if frame is not None:
                        display_frame = self.renderer.draw(frame, body) if self.renderer else frame
                        cv2.putText(display_frame, f"Volume: {volume:.0f} / {self.volume_threshold:.0f}",
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.imshow("Speech to Clothing", display_frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            stream.stop_stream()
                            stream.close()
                            audio.terminate()
                            cv2.destroyAllWindows()
                            return

            except Exception as e:
                continue

        stream.stop_stream()
        stream.close()
        audio.terminate()

        self.current_state = "RECORDING"
        self._emit_state('RECORDING', duration=self.recording_duration)
        audio_data = self.record_speech_fixed_duration()

        if not audio_data:
            print("✗ Recording failed, exiting")
            self._emit_state('ERROR', error_message='Recording failed')
            return

        self._emit_state('TRANSCRIBING')
        self.transcribed_text = self.transcribe_with_whisper(audio_data)

        # Emit transcription to UI
        if self.ws_server and self.transcribed_text:
            self.ws_server.emit_transcription(self.transcribed_text, is_final=True)

        if not self.transcribed_text:
            print("✗ Transcription failed, using default prompt")
            self.transcribed_text = "elegant dress with floral patterns"

        self.current_state = "WAITING_FOR_POSE"
        self._emit_state('A_POSE', countdown=3)
        print("\n🤸 Please stand in A-pose...")
        print("   3 second countdown starting...")

        clean_frame = None
        captured_body = None
        for i in range(3, 0, -1):
            print(f"   {i}...")

            frame, body = self.get_frame()
            if frame is not None:
                clean_frame = frame.copy()
                captured_body = body

                # Stream frame to UI during countdown (broadcaster handles this automatically)
                # But still validate A-pose and provide feedback
                if self.enable_ui and not self.camera_broadcaster:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self._emit_frame(frame_rgb, body)

                # Validate A-pose and provide feedback
                if self.mesh_calibrator and body:
                    pose_status = self.mesh_calibrator.validate_a_pose(body)
                    print(f"   A-pose: {pose_status['message']}")

                if self.show_viewer:
                    display_frame = frame.copy()
                    cv2.putText(display_frame, f"A-POSE: {i}", (display_frame.shape[1]//2 - 100, display_frame.shape[0]//2),
                               cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 255), 5)
                    cv2.imshow("Speech to Clothing", display_frame)
                    cv2.waitKey(1)

            time.sleep(1)

        if clean_frame is None:
            frame, body = self.get_frame()
            if frame is not None:
                clean_frame = frame.copy()
                captured_body = body

        if clean_frame is None:
            print("✗ Frame capture failed, exiting")
            return

        # Calibrate mesh offset from captured A-pose
        if self.mesh_calibrator and captured_body:
            self.mesh_calibrator.calibrate_offset(captured_body)
            print("✓ Mesh calibration offset set")

        print("\n📸 Frame captured!")
        self._emit_state('CAPTURING')
        frame_rgb, mask = self.capture_frame_with_bodypix(clean_frame)

        if frame_rgb is None or mask is None:
            print("✗ BodyPix processing failed, exiting")
            self._emit_state('ERROR', error_message='Body segmentation failed')
            return

        self.current_state = "GENERATING"
        self._emit_state('GENERATING_2D')
        result_image = self.generate_clothing_with_comfyui(frame_rgb, mask, self.transcribed_text)

        if not result_image:
            print("\n✗ 2D generation failed")
            self._emit_state('ERROR', error_message='2D generation failed')
            return

        # Emit preview state and image
        self._emit_state('PREVIEW')
        texture_b64 = None  # Store for later use with mesh
        if self.ws_server:
            # Save temp image and send to UI
            import io
            buffer = io.BytesIO()
            result_image.save(buffer, format='PNG')
            import base64
            texture_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.ws_server._message_queue.put({'type': 'preview_image', 'image': texture_b64})

            # Also send the mask for the cropped preview (Stage 2)
            mask_pil = Image.fromarray(mask)
            mask_buffer = io.BytesIO()
            mask_pil.save(mask_buffer, format='PNG')
            mask_b64 = base64.b64encode(mask_buffer.getvalue()).decode('utf-8')
            self.ws_server._message_queue.put({'type': 'preview_mask', 'mask': mask_b64})

        # Wait for preview to be shown (12 seconds: 10s Stage 1 + 2s Stage 2)
        # This allows the frontend's preview sequence to complete
        print("\n📸 Showing preview (12 seconds)...")
        time.sleep(12)

        # Step 9: Generate 3D mesh with Rodin API (Direct)
        mesh_path = None
        if self.enable_3d:
            self._emit_state('GENERATING_3D')

            # CRITICAL: Crop the clothing from the 2D image using the BodyPix mask
            # This ensures we send ONLY the clothing to Rodin, not the entire body
            cropped_clothing = self._crop_clothing_with_mask(result_image, mask)

            # Save temporary 2D image for Rodin input
            temp_2d_path = Path(f"/tmp/clothing_2d_{int(time.time())}.png")
            cropped_clothing.save(temp_2d_path)

            try:
                mesh_path = self.generate_3d_mesh_with_rodin_api(temp_2d_path)
            except Exception as e:
                print(f"✗ 3D generation exception: {e}")
                import traceback
                traceback.print_exc()
                mesh_path = None

            # Cleanup temp file
            if temp_2d_path.exists():
                temp_2d_path.unlink()

            # Emit mesh ready to UI (include 2D texture as fallback)
            if mesh_path and self.ws_server:
                print("   📤 Sending mesh to browser...")
                self.ws_server.emit_mesh_ready(str(mesh_path), texture_b64)
                # Give browser time to receive and load the large GLB file
                time.sleep(4)  # Increased from 2s for large meshes
                print("   ✓ Mesh sent to browser")

                # === CALIBRATING PHASE (3s countdown, user aligns with mesh) ===
                self._run_calibration_phase(duration=3)

                # === TRY_ON PHASE (30s interactive, mesh follows body) ===
                self._run_tryon_phase(duration=30)

            elif self.ws_server:
                # 3D generation failed - notify UI and show error briefly
                print("⚠️  3D generation failed, showing error state...")
                self._emit_state('ERROR', error_message='3D mesh generation failed. Showing 2D preview only.')
                time.sleep(3)  # Show error for 3 seconds

        # Step 10: Save all outputs
        self.current_state = "DONE"
        print("\n" + "="*70)
        print("✅ Generation Complete!")
        print("="*70)
        print(f"   Prompt: '{self.transcribed_text}'")
        if mesh_path:
            print(f"   3D Mesh: ✓ Generated")
        else:
            print(f"   3D Mesh: ✗ Skipped or failed")

        settings = {
            "seed": 100,
            "steps": 35,
            "cfg": 9.5
        }
        output_dir = self.save_generated_outputs(frame_rgb, mask, result_image, self.transcribed_text, settings, mesh_path)

        print(f"\n✅ Session complete! Outputs saved to: {output_dir}")

        # === INSTALLATION MODE: Loop back for next user ===
        print("\n" + "="*70)
        print("🔄 Ready for next user!")
        print("="*70 + "\n")

        # Reset to IDLE state for next user
        self._emit_state('IDLE', title='SPOKEN WARDROBE',
                        subtitle='Step in front of the camera to begin')

        # Brief pause before next session
        time.sleep(2)

        # Loop back to body detection (recursively call run)
        # This creates an infinite loop that only exits on Ctrl+C
        self.run_session_loop()

    def run_session_loop(self):
        """Continue the installation loop - wait for next user."""
        # This method continues from after initialization
        # to avoid re-initializing camera and microphone

        self.current_state = "WAITING_FOR_BODY"
        self._emit_state('IDLE', title='SPOKEN WARDROBE', subtitle='Step in front of the camera')
        print("\n👤 Waiting for next user...")
        print("   Stand in front of OAK-D camera...")

        body_detected = False
        while not body_detected:
            frame, body = self.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            body_detected = self.is_body_detected(body)

            if self.show_viewer:
                display_frame = self.renderer.draw(frame, body) if self.renderer else frame
                cv2.imshow("Speech to Clothing", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nExiting...")
                    self.cleanup()
                    return

        print("✓ Body detected!")

        # Now run the rest of the session (speech → generation → try-on)
        self._run_session_after_body_detected()

    def _run_session_after_body_detected(self):
        """Run pipeline session after body is detected (speech → generation → try-on)."""

        self.current_state = "WAITING_FOR_SPEECH"
        self._emit_state('LISTENING', prompt='Describe your clothing idea')
        print("\n🎤 Listening for speech...")
        print(f"   Speak when volume > {self.volume_threshold:.0f}")

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            input_device_index=self.mic_index
        )

        speech_detected = False
        while not speech_detected:
            try:
                audio_data = stream.read(1024, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_float = audio_array.astype(np.float32)
                volume = np.sqrt(np.mean(audio_float**2))

                if volume > self.volume_threshold:
                    print(f"\n✓ Speech detected! (volume: {volume:.0f})")
                    speech_detected = True
                    break

            except Exception as e:
                print(f"Audio error: {e}")
                time.sleep(0.1)

        # Recording phase
        self.current_state = "RECORDING"
        self._emit_state('RECORDING')
        print("\n🎙️ Recording for 10 seconds...")

        self.audio_chunks = []
        start_time = time.time()

        while time.time() - start_time < self.recording_duration:
            try:
                audio_data = stream.read(1024, exception_on_overflow=False)
                self.audio_chunks.append(audio_data)
                remaining = self.recording_duration - (time.time() - start_time)
                print(f"   Recording... {remaining:.1f}s remaining", end='\r')
            except Exception as e:
                print(f"Recording error: {e}")

        stream.stop_stream()
        stream.close()
        audio.terminate()
        print("\n✓ Recording complete!")

        # Transcription
        self.current_state = "TRANSCRIBING"
        self._emit_state('TRANSCRIBING')
        print("\n📝 Transcribing with Whisper...")

        audio_data = b''.join(self.audio_chunks)
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        result = self.speech_recognizer.model.transcribe(audio_array, language='en')
        self.transcribed_text = result['text'].strip()
        print(f"   Transcription: '{self.transcribed_text}'")

        if self.ws_server:
            self.ws_server.emit_transcription(self.transcribed_text, is_final=True)

        # A-pose capture
        self.current_state = "A_POSE"
        self._emit_state('A_POSE')
        print("\n🧍 Strike an A-Pose!")

        # Disable skeleton for clean capture
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = False

        for i in range(3, 0, -1):
            print(f"   Capturing in {i}...")
            time.sleep(1)

        # Capture clean frame
        frame_rgb, body = None, None
        if self.camera_broadcaster:
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data:
                frame_rgb = frame_data.frame_rgb
                body = frame_data.body
        else:
            frame, body = self.get_frame()
            if frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if frame_rgb is None:
            print("✗ Failed to capture frame")
            self._emit_state('ERROR', error_message='Failed to capture frame')
            time.sleep(3)
            self.run_session_loop()
            return

        # Flash effect
        self._emit_state('CAPTURING')
        print("✓ Frame captured!")

        # BodyPix segmentation
        print("\n🎭 Running BodyPix segmentation...")
        mask = self.segment_body_parts(frame_rgb)

        if mask is None or mask.sum() == 0:
            print("✗ BodyPix segmentation failed")
            self._emit_state('ERROR', error_message='Body segmentation failed')
            time.sleep(3)
            self.run_session_loop()
            return

        # 2D Generation
        self.current_state = "GENERATING"
        self._emit_state('GENERATING_2D')
        result_image = self.generate_clothing_with_comfyui(frame_rgb, mask, self.transcribed_text)

        if not result_image:
            print("\n✗ 2D generation failed")
            self._emit_state('ERROR', error_message='2D generation failed')
            time.sleep(3)
            self.run_session_loop()
            return

        # Preview
        self._emit_state('PREVIEW')
        texture_b64 = None
        if self.ws_server:
            import io
            buffer = io.BytesIO()
            result_image.save(buffer, format='PNG')
            import base64
            texture_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.ws_server._message_queue.put({'type': 'preview_image', 'image': texture_b64})

            mask_pil = Image.fromarray(mask)
            mask_buffer = io.BytesIO()
            mask_pil.save(mask_buffer, format='PNG')
            mask_b64 = base64.b64encode(mask_buffer.getvalue()).decode('utf-8')
            self.ws_server._message_queue.put({'type': 'preview_mask', 'mask': mask_b64})

        print("\n📸 Showing preview (12 seconds)...")
        time.sleep(12)

        # 3D Generation
        mesh_path = None
        if self.enable_3d:
            self._emit_state('GENERATING_3D')

            # CRITICAL: Crop the clothing from the 2D image using the BodyPix mask
            # This ensures we send ONLY the clothing to Rodin, not the entire body
            cropped_clothing = self._crop_clothing_with_mask(result_image, mask)

            temp_2d_path = Path(f"/tmp/clothing_2d_{int(time.time())}.png")
            cropped_clothing.save(temp_2d_path)

            try:
                mesh_path = self.generate_3d_mesh_with_rodin_api(temp_2d_path)
            except Exception as e:
                print(f"✗ 3D generation exception: {e}")
                mesh_path = None

            if temp_2d_path.exists():
                temp_2d_path.unlink()

            if mesh_path and self.ws_server:
                self.ws_server.emit_mesh_ready(str(mesh_path), texture_b64)
                self._run_calibration_phase(duration=3)
                self._run_tryon_phase(duration=30)
            elif self.ws_server:
                print("⚠️  3D generation failed, showing error state...")
                self._emit_state('ERROR', error_message='3D mesh generation failed.')
                time.sleep(3)

        # Save outputs
        self.current_state = "DONE"
        print("\n" + "="*70)
        print("✅ Generation Complete!")
        print("="*70)

        settings = {"seed": 100, "steps": 35, "cfg": 9.5}
        output_dir = self.save_generated_outputs(frame_rgb, mask, result_image, self.transcribed_text, settings, mesh_path)

        print(f"\n✅ Session complete! Outputs saved to: {output_dir}")

        # Loop back for next user
        print("\n" + "="*70)
        print("🔄 Ready for next user!")
        print("="*70 + "\n")

        self._emit_state('IDLE', title='SPOKEN WARDROBE',
                        subtitle='Step in front of the camera to begin')
        time.sleep(2)
        self.run_session_loop()


def main():
    """Entry point"""

    parser = argparse.ArgumentParser(description="Speech-to-Clothing Pipeline with Rodin API (Direct)")
    parser.add_argument('--viewer', action='store_true',
                       help='Show OpenCV debug windows')
    parser.add_argument('--skip-3d', action='store_true',
                       help='Skip 3D mesh generation (2D only)')
    parser.add_argument('--api-key', type=str,
                       help='Rodin API key (or set RODIN_API_KEY env var)')
    parser.add_argument('--ui', action='store_true',
                       help='Enable WebSocket UI (open browser to http://localhost:8080)')
    args = parser.parse_args()

    if args.viewer:
        print("\n🖼️  VIEWER MODE - OpenCV windows will be shown")
    else:
        print("\n🎥 HEADLESS MODE - Output via console")

    # Check for API key
    api_key = args.api_key or os.environ.get('RODIN_API_KEY')
    if not args.skip_3d and not api_key:
        print("\n⚠️  WARNING: No Rodin API key provided!")
        print("   Set with: export RODIN_API_KEY='your_key_here'")
        print("   Or use: --api-key 'your_key_here'")
        print("   Get key from: https://hyperhuman.deemos.com/")
        print("\n   3D generation will be skipped.")
        print("   Use --skip-3d flag to suppress this warning.\n")
        time.sleep(3)

    pipeline = None
    try:
        pipeline = SpeechToClothingPipeline(
            comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
            show_viewer=args.viewer,
            enable_3d=not args.skip_3d,
            rodin_api_key=api_key,
            enable_ui=args.ui
        )
        pipeline.run()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if pipeline:
            pipeline.cleanup()
    except Exception as e:
        print(f"\n✗ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        if pipeline:
            pipeline.cleanup()


if __name__ == "__main__":
    main()
