#!/usr/bin/env python3
"""
Speech-to-2D Clothing Generation Pipeline (Simplified for Playtest)

A streamlined pipeline focused on the 2D clothing generation experience:
1. Listens for creative speech description
2. Captures body frame with BodyPix segmentation
3. Generates imaginative 2D clothing with ComfyUI
4. Shows dramatic reveal sequence (10s full image, 8s cropped clothing)
5. Optionally generates 3D mesh and uploads to Firebase cloud

This version removes virtual try-on complexity for a polished playtest experience.

Usage:
    export RODIN_API_KEY="your_api_key_here"  # Optional for 3D
    python src/modules/speech_to_2d_generation.py [--skip-3d]
    Open: http://localhost:8080
"""

import sys
from pathlib import Path
import time
import json
import cv2
import numpy as np
import pyaudio
import threading
import base64
import io
from PIL import Image
import argparse
import os

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

# Import UI modules
try:
    from ui.websocket_server import PipelineWebSocketServer, run_server_in_thread
    from ui.state_manager import StateManager
    from ui.camera_broadcaster import CameraBroadcaster
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    print("Error: WebSocket UI not available. This pipeline requires the UI.")
    sys.exit(1)

# Import BodyPix
from tf_bodypix.api import download_model, load_model, BodyPixModelPaths

# Import OAK-D Pro camera
from BlazeposeDepthaiEdge import BlazeposeDepthai


# ============================================================================
# CONFIGURATION - Timing and messaging for playtest experience
# ============================================================================

# Reveal timing (in seconds)
REVEAL_FULL_DURATION = 10      # Show full image with body
REVEAL_CLOTHING_DURATION = 8    # Show cropped clothing only

# Recording duration
RECORDING_DURATION = 10.0       # Fixed 10-second recording

# Creative messaging for UI
UI_MESSAGES = {
    'IDLE': {
        'title': 'DREAM WARDROBE',
        'subtitle': 'What impossible garment lives in your imagination?'
    },
    'LISTENING': {
        'prompt': 'Describe something that could never exist in a store...'
    },
    'RECORDING': {
        'title': 'CAPTURING YOUR VISION',
        'subtitle': "We're listening to your wildest fashion fantasy..."
    },
    'TRANSCRIBING': {
        'title': 'WEAVING IMAGINATION',
        'subtitle': 'Translating your dream into threads...'
    },
    'A_POSE': {
        'title': 'STRIKE A POSE',
        'subtitle': 'Stand with arms slightly out, like a fashion model'
    },
    'CAPTURING': {
        'title': 'CAPTURING',
        'subtitle': 'Hold still...'
    },
    'GENERATING_2D': {
        'title': 'MANIFESTING YOUR VISION',
        'subtitle': 'Your impossible garment is taking shape...'
    },
    'REVEAL_FULL': {
        'title': 'BEHOLD YOUR CREATION',
        'subtitle': ''
    },
    'REVEAL_CLOTHING': {
        'title': 'YOUR DESIGN',
        'subtitle': ''
    },
    'GENERATING_3D': {
        'title': 'BRINGING IT TO LIFE',
        'subtitle': 'Transforming your creation into 3D...'
    },
    'COMPLETE': {
        'title': 'CREATION COMPLETE',
        'subtitle': 'Your design joins the gallery of dreams'
    }
}


class BodyPartSelector:
    """Selects body parts for dress segmentation"""

    DRESS_PARTS = [
        'torso_front', 'torso_back',
        'left_upper_arm_front', 'left_upper_arm_back',
        'left_lower_arm_front', 'left_lower_arm_back',
        'right_upper_arm_front', 'right_upper_arm_back',
        'right_lower_arm_front', 'right_lower_arm_back',
        'left_upper_leg_front', 'left_upper_leg_back',
        'right_upper_leg_front', 'right_upper_leg_back',
    ]


class SpeechTo2DPipeline:
    """
    Simplified pipeline for playtest - 2D focused with dramatic reveal.

    Removes virtual try-on complexity, focuses on:
    - Creative speech input
    - Dramatic 2D reveal (full image -> cropped clothing)
    - Optional 3D generation with cloud upload
    """

    def __init__(self, comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
                 enable_3d=True, rodin_api_key=None):
        """Initialize pipeline components"""

        print("\n" + "="*70)
        print("Dream Wardrobe - Playtest Edition")
        print("="*70)

        # Configuration
        self.comfyui_url = comfyui_url
        self.workflow_path_2d = "workflows/sdxl_inpainting_api.json"
        self.enable_3d = enable_3d

        # Rodin API configuration
        self.rodin_api_key = rodin_api_key or os.environ.get('RODIN_API_KEY')
        self.rodin_base_url = "https://api.hyper3d.com/api/v2"

        if self.enable_3d and not self.rodin_api_key:
            print("\n    3D generation disabled (no API key)")
            self.enable_3d = False

        # Components (lazy loaded)
        self.speech_recognizer = None
        self.comfyui_client = None
        self.bodypix_model = None
        self.prompt_enhancer = None

        # OAK-D Pro Camera
        self.tracker = None

        # State
        self.ambient_noise_level = 0
        self.volume_threshold = 0
        self.transcribed_text = ""
        self.mic_index = None

        # UI Components
        self.ws_server = None
        self.state_manager = None
        self.camera_broadcaster = None
        self._http_server = None

        # Firebase storage (optional - initialized when credentials available)
        self.cloud_storage = None
        self._init_firebase()

        # Initialize UI servers
        self._init_ui()

        print("    Pipeline initialized")
        print("="*70 + "\n")

    def _init_firebase(self):
        """Initialize Firebase storage if credentials available"""
        creds_path = project_root / "firebase-credentials.json"
        if creds_path.exists():
            try:
                # Import lazily to avoid errors if firebase-admin not installed
                from utils.firebase_storage import CloudStorage
                # Read bucket name from credentials or use default
                with open(creds_path) as f:
                    creds = json.load(f)
                    project_id = creds.get('project_id', 'spoken-wardrobe')
                bucket_name = f"{project_id}.firebasestorage.app"
                self.cloud_storage = CloudStorage(str(creds_path), bucket_name)
                print("    Firebase storage connected")
            except Exception as e:
                print(f"    Firebase not available: {e}")
                self.cloud_storage = None
        else:
            print("    Firebase credentials not found (local storage only)")

    def _init_ui(self):
        """Initialize WebSocket UI server and HTTP server"""
        print("\n    Starting UI servers...")

        # Start WebSocket server
        self.ws_server = run_server_in_thread(host='localhost', port=8765)
        self.state_manager = StateManager(self.ws_server)

        # Start HTTP server for static files
        self._start_http_server(port=8080)

        print("    WebSocket: ws://localhost:8765")
        print("    Browser UI: http://localhost:8080")

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

        class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        def serve():
            self._http_server = ThreadingHTTPServer(("", port), QuietHandler)
            self._http_server.serve_forever()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

    def cleanup(self):
        """Clean up all resources"""
        print("\n    Cleaning up...")

        if self.camera_broadcaster:
            try:
                self.camera_broadcaster.stop()
            except Exception:
                pass

        if self.tracker:
            try:
                if hasattr(self.tracker, 'device'):
                    self.tracker.device.close()
            except Exception:
                pass

        if self.ws_server:
            try:
                self.ws_server.stop()
            except Exception:
                pass

        if self._http_server:
            try:
                self._http_server.shutdown()
            except Exception:
                pass

        cv2.destroyAllWindows()
        time.sleep(0.3)
        print("    Cleanup complete")

    def _emit_state(self, state, **extra_data):
        """Emit state change to UI with creative messaging"""
        msg = UI_MESSAGES.get(state, {})
        data = {**msg, **extra_data}
        if self.state_manager:
            self.state_manager.transition(state, **data)

    def _emit_audio_level(self, level):
        """Emit audio level to UI"""
        if self.ws_server:
            normalized_level = min(1.0, level / max(1, self.volume_threshold * 2))
            self.ws_server.emit_audio_level(normalized_level, 0.5)

    def find_microphone_by_name(self, target_name="MacBook Pro Microphone"):
        """Find microphone device index by name"""
        audio = pyaudio.PyAudio()

        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                device_name = device_info['name']
                if target_name in device_name:
                    audio.terminate()
                    return i

        audio.terminate()
        return None

    def calibrate_microphone(self, duration=3.0):
        """Calibrate microphone for ambient noise"""
        print(f"\n    Calibrating microphone ({duration}s)...")

        self.mic_index = self.find_microphone_by_name("MacBook Pro Microphone")
        audio = pyaudio.PyAudio()

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
                input_device_index=self.mic_index
            )

            volume_samples = []
            start_time = time.time()

            while (time.time() - start_time) < duration:
                try:
                    audio_data = stream.read(1024, exception_on_overflow=False)
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    volume = np.sqrt(np.mean(audio_array**2))
                    volume_samples.append(volume)
                except Exception:
                    continue

            self.ambient_noise_level = np.mean(volume_samples)
            self.volume_threshold = max(50, self.ambient_noise_level * 2.5)

            stream.stop_stream()
            stream.close()

            print(f"    Ambient: {self.ambient_noise_level:.0f}, Threshold: {self.volume_threshold:.0f}")

        except Exception as e:
            print(f"    Calibration failed: {e}")
            self.volume_threshold = 500

        finally:
            audio.terminate()

    def initialize_camera(self):
        """Initialize OAK-D Pro camera with BlazePose"""
        print("\n    Initializing OAK-D Pro camera...")

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

        # Start camera broadcaster
        print("    Starting camera broadcaster...")
        self.camera_broadcaster = CameraBroadcaster(
            tracker=self.tracker,
            ws_server=self.ws_server,
            target_fps=30
        )
        self.camera_broadcaster.start()

        # Wait for first frame
        first_frame = self.camera_broadcaster.wait_for_frame(timeout=5.0)
        if first_frame:
            print("    Camera streaming")
        else:
            print("    Warning: No frames yet")

    def is_body_detected(self, body):
        """Check if a body is detected"""
        return body and hasattr(body, 'landmarks_world')

    def get_frame(self):
        """Get frame from camera broadcaster"""
        if self.camera_broadcaster and self.camera_broadcaster.is_running:
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data:
                frame_bgr = cv2.cvtColor(frame_data.frame_rgb, cv2.COLOR_RGB2BGR)
                return frame_bgr, frame_data.body
        return None, None

    def record_speech(self):
        """Record speech for fixed duration"""
        print(f"\n    Recording for {RECORDING_DURATION} seconds...")

        audio = pyaudio.PyAudio()

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
            start_time = time.time()

            # Ensure Whisper model is loaded
            if not self.speech_recognizer:
                self.speech_recognizer = SpeechRecognizer(modelSize="base")
                self.speech_recognizer.loadWhisperModel()

            while (time.time() - start_time) < RECORDING_DURATION:
                try:
                    audio_data = stream.read(1024, exception_on_overflow=False)
                    audio_chunks.append(audio_data)

                    # Emit audio level for waveform
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    level = np.sqrt(np.mean(audio_array**2))
                    self._emit_audio_level(level)

                except Exception:
                    continue

            stream.stop_stream()
            stream.close()

            return b''.join(audio_chunks)

        except Exception as e:
            print(f"    Recording failed: {e}")
            return None

        finally:
            audio.terminate()

    def transcribe_speech(self, audio_data):
        """Transcribe audio using Whisper"""
        if not self.speech_recognizer:
            self.speech_recognizer = SpeechRecognizer(modelSize="base")
            self.speech_recognizer.loadWhisperModel()

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
                predicted_ids = self.speech_recognizer.model.generate(inputs)

            transcription = self.speech_recognizer.processor.batch_decode(
                predicted_ids,
                skip_special_tokens=True
            )[0].strip()

            return transcription

        except Exception as e:
            print(f"    Transcription failed: {e}")
            return ""

    def segment_body_parts(self, frame_rgb):
        """Segment body parts using BodyPix"""
        if not self.bodypix_model:
            print("    Loading BodyPix...")
            self.bodypix_model = load_model(download_model(
                BodyPixModelPaths.MOBILENET_FLOAT_75_STRIDE_16
            ))

        result = self.bodypix_model.predict_single(frame_rgb)
        person_mask = result.get_mask(threshold=0.75)
        body_part_mask = result.get_part_mask(person_mask, part_names=BodyPartSelector.DRESS_PARTS)

        if hasattr(body_part_mask, 'numpy'):
            body_part_mask = body_part_mask.numpy()
        body_part_mask = np.squeeze(body_part_mask)

        return (body_part_mask > 0).astype(np.uint8) * 255

    def generate_clothing_2d(self, frame_rgb, mask, prompt):
        """Generate 2D clothing with enhanced prompt"""
        if not self.comfyui_client:
            self.comfyui_client = ComfyUIClient(self.comfyui_url)

        if not self.prompt_enhancer:
            self.prompt_enhancer = PromptEnhancer(use_llm=True)

        # Enhance the prompt for creative, avant-garde results
        enhanced_prompt = self.prompt_enhancer.enhance(prompt)
        print(f"    Original: '{prompt}'")
        print(f"    Enhanced: '{enhanced_prompt}'")

        # Build final prompt with quality modifiers
        final_prompt = (
            f"{enhanced_prompt}, haute couture fashion photography, "
            "editorial style, dramatic lighting, high fashion, "
            "detailed fabric texture, professional fashion shoot, 8k quality"
        )

        # Negative prompt for clean results
        negative_prompt = (
            "sexy, seductive, revealing, provocative, nsfw, nude, naked, "
            "cleavage, skin, exposed body, tight clothing, form-fitting, "
            "low quality, blurry, distorted, deformed, ugly, bad anatomy, "
            "watermark, text, amateur, simple, plain, boring, generic"
        )

        try:
            result = self.comfyui_client.generate_inpainting(
                image=frame_rgb,
                mask=mask,
                prompt=final_prompt,
                negative_prompt=negative_prompt,
                workflow_path=self.workflow_path_2d,
                seed=100,
                steps=35,
                cfg=9.5
            )
            return result

        except Exception as e:
            print(f"    Generation failed: {e}")
            return None

    def crop_clothing_with_mask(self, result_image, mask):
        """Crop clothing from image using mask (transparent background)"""
        result_array = np.array(result_image)

        # Resize mask if needed
        if mask.shape[:2] != result_array.shape[:2]:
            mask = cv2.resize(mask, (result_array.shape[1], result_array.shape[0]),
                            interpolation=cv2.INTER_NEAREST)

        # Dilate and blur mask for smooth edges
        kernel = np.ones((5, 5), np.uint8)
        mask_dilated = cv2.dilate(mask, kernel, iterations=2)
        mask_blurred = cv2.GaussianBlur(mask_dilated.astype(np.float32), (7, 7), 0)
        mask_normalized = (mask_blurred / 255.0).clip(0, 1)

        # Create RGBA output
        if result_array.shape[2] == 3:
            rgba_array = np.zeros((result_array.shape[0], result_array.shape[1], 4), dtype=np.uint8)
            rgba_array[:, :, :3] = result_array
        else:
            rgba_array = result_array.copy()

        rgba_array[:, :, 3] = (mask_normalized * 255).astype(np.uint8)

        # Find bounding box and crop
        alpha = rgba_array[:, :, 3]
        rows = np.any(alpha > 0, axis=1)
        cols = np.any(alpha > 0, axis=0)

        if rows.any() and cols.any():
            row_min, row_max = np.where(rows)[0][[0, -1]]
            col_min, col_max = np.where(cols)[0][[0, -1]]

            # Add padding
            height, width = alpha.shape
            pad_h = int((row_max - row_min) * 0.1)
            pad_w = int((col_max - col_min) * 0.1)

            row_min = max(0, row_min - pad_h)
            row_max = min(height, row_max + pad_h)
            col_min = max(0, col_min - pad_w)
            col_max = min(width, col_max + pad_w)

            cropped_image = Image.fromarray(rgba_array, mode='RGBA')
            cropped_image = cropped_image.crop((col_min, row_min, col_max, row_max))
            return cropped_image

        return Image.fromarray(rgba_array, mode='RGBA')

    def run_reveal_sequence(self, result_image, mask):
        """
        Run dramatic reveal sequence:
        1. REVEAL_FULL: Show full image (10 seconds)
        2. REVEAL_CLOTHING: Show cropped clothing only (8 seconds)
        """
        print(f"\n    Reveal sequence: {REVEAL_FULL_DURATION}s full + {REVEAL_CLOTHING_DURATION}s cropped")

        # Convert image to base64
        buffer = io.BytesIO()
        result_image.save(buffer, format='PNG')
        image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Convert mask to base64
        mask_pil = Image.fromarray(mask)
        mask_buffer = io.BytesIO()
        mask_pil.save(mask_buffer, format='PNG')
        mask_b64 = base64.b64encode(mask_buffer.getvalue()).decode('utf-8')

        # Stage 1: REVEAL_FULL - Show full image with body
        self._emit_state('REVEAL_FULL', duration=REVEAL_FULL_DURATION)
        if self.ws_server:
            self.ws_server._message_queue.put({'type': 'preview_image', 'image': image_b64})
        print(f"    Stage 1: Full reveal ({REVEAL_FULL_DURATION}s)")
        time.sleep(REVEAL_FULL_DURATION)

        # Stage 2: REVEAL_CLOTHING - Show cropped clothing only
        self._emit_state('REVEAL_CLOTHING', duration=REVEAL_CLOTHING_DURATION)
        if self.ws_server:
            self.ws_server._message_queue.put({'type': 'preview_mask', 'mask': mask_b64})
        print(f"    Stage 2: Clothing reveal ({REVEAL_CLOTHING_DURATION}s)")
        time.sleep(REVEAL_CLOTHING_DURATION)

        return image_b64

    def generate_3d_mesh(self, image_path):
        """Generate 3D mesh using Rodin API"""
        import requests

        print("\n    Generating 3D mesh (60-90s)...")

        if not self.rodin_api_key:
            return None

        # Submit task
        url = f"{self.rodin_base_url}/rodin"

        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()

            files = {'images': (os.path.basename(str(image_path)), image_data, 'image/png')}
            data = {
                'tier': 'Regular',
                'quality_override': '5000',
                'material': 'PBR',
                'mesh_mode': 'Raw',
                'mesh_simplify': 'true',
                'geometry_file_format': 'glb'
            }
            headers = {'Authorization': f'Bearer {self.rodin_api_key}'}

            response = requests.post(url, files=files, data=data, headers=headers, timeout=30)

            if response.status_code not in [200, 201]:
                print(f"    API error: {response.status_code}")
                return None

            result = response.json()
            task_uuid = result.get('uuid')
            subscription_key = result.get('jobs', {}).get('subscription_key')

            if not task_uuid or not subscription_key:
                return None

            # Poll for completion
            print("    Waiting for generation...")
            start_time = time.time()

            while (time.time() - start_time) < 300:
                time.sleep(5)

                status_response = requests.post(
                    f"{self.rodin_base_url}/status",
                    headers={**headers, 'Content-Type': 'application/json'},
                    json={'subscription_key': subscription_key},
                    timeout=10
                )

                if status_response.status_code not in [200, 201]:
                    continue

                jobs = status_response.json().get('jobs', [])
                if all(j.get('status') == 'Done' for j in jobs):
                    break
                if any(j.get('status') == 'Failed' for j in jobs):
                    print("    Generation failed")
                    return None

            # Download result
            download_response = requests.post(
                f"{self.rodin_base_url}/download",
                headers={**headers, 'Content-Type': 'application/json'},
                json={'task_uuid': task_uuid},
                timeout=30
            )

            if download_response.status_code not in [200, 201]:
                return None

            download_list = download_response.json().get('list', [])

            for item in download_list:
                if item.get('name', '').endswith('.glb'):
                    glb_response = requests.get(item['url'], timeout=60)
                    if glb_response.status_code == 200:
                        output_path = Path(f"/tmp/mesh_{int(time.time())}.glb")
                        with open(output_path, 'wb') as f:
                            f.write(glb_response.content)
                        print(f"    Mesh downloaded: {output_path}")
                        return output_path

            return None

        except Exception as e:
            print(f"    3D generation error: {e}")
            return None

    def save_outputs(self, frame_rgb, mask, result_image, transcription, mesh_path=None):
        """Save all outputs to organized folder"""
        timestamp = int(time.time())
        output_dir = Path("comfyui_generated_mesh") / str(timestamp)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save files
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(output_dir / "original_frame.png"), frame_bgr)
        cv2.imwrite(str(output_dir / "mask.png"), mask)
        result_image.save(str(output_dir / "generated_clothing.png"))

        if mesh_path and mesh_path.exists():
            import shutil
            shutil.copy(mesh_path, output_dir / "clothing_mesh.glb")

        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "transcription": transcription,
            "has_3d_mesh": mesh_path is not None
        }
        with open(output_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        # Upload to Firebase if available
        if self.cloud_storage and mesh_path and mesh_path.exists():
            try:
                cloud_url = self.cloud_storage.upload_glb(
                    str(mesh_path),
                    {'prompt': transcription, 'timestamp': timestamp}
                )
                print(f"    Uploaded to cloud: {cloud_url}")
            except Exception as e:
                print(f"    Cloud upload failed: {e}")

        return output_dir

    def run_session(self):
        """Run a single session: speech -> generate -> reveal -> save"""

        # Wait for body
        self._emit_state('IDLE')
        print("\n    Waiting for person...")

        while True:
            frame, body = self.get_frame()
            if frame is not None and self.is_body_detected(body):
                break
            time.sleep(0.05)

        print("    Body detected!")

        # Wait for speech
        self._emit_state('LISTENING')
        print(f"\n    Listening for speech (threshold: {self.volume_threshold:.0f})")

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            input_device_index=self.mic_index
        )

        while True:
            try:
                audio_data = stream.read(1024, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                volume = np.sqrt(np.mean(audio_array**2))

                if volume > self.volume_threshold:
                    print(f"    Speech detected! (volume: {volume:.0f})")
                    break
            except Exception:
                continue

        stream.stop_stream()
        stream.close()
        audio.terminate()

        # Record
        self._emit_state('RECORDING', duration=RECORDING_DURATION)
        audio_data = self.record_speech()

        if not audio_data:
            self._emit_state('ERROR', error_message='Recording failed')
            return False

        # Transcribe
        self._emit_state('TRANSCRIBING')
        self.transcribed_text = self.transcribe_speech(audio_data)

        if self.ws_server and self.transcribed_text:
            self.ws_server.emit_transcription(self.transcribed_text, is_final=True)

        if not self.transcribed_text:
            self.transcribed_text = "a beautiful flowing gown"

        print(f"\n    Transcription: '{self.transcribed_text}'")

        # A-pose capture
        self._emit_state('A_POSE', countdown=3)
        print("\n    A-pose countdown...")

        # Disable skeleton for clean capture
        if self.camera_broadcaster:
            self.camera_broadcaster.draw_skeleton = False

        for i in range(3, 0, -1):
            print(f"    {i}...")
            time.sleep(1)

        # Capture frame
        frame_rgb = None
        if self.camera_broadcaster:
            frame_data = self.camera_broadcaster.get_latest_frame()
            if frame_data:
                frame_rgb = frame_data.frame_rgb

        if frame_rgb is None:
            self._emit_state('ERROR', error_message='Capture failed')
            return False

        self._emit_state('CAPTURING')
        print("    Frame captured!")

        # Segment body
        print("    Running BodyPix segmentation...")
        mask = self.segment_body_parts(frame_rgb)

        if mask is None or mask.sum() == 0:
            self._emit_state('ERROR', error_message='Segmentation failed')
            return False

        # Generate 2D clothing
        self._emit_state('GENERATING_2D')
        result_image = self.generate_clothing_2d(frame_rgb, mask, self.transcribed_text)

        if not result_image:
            self._emit_state('ERROR', error_message='Generation failed')
            return False

        # Dramatic reveal sequence
        self.run_reveal_sequence(result_image, mask)

        # Optional 3D generation
        mesh_path = None
        if self.enable_3d:
            self._emit_state('GENERATING_3D')

            # Crop clothing for 3D
            cropped = self.crop_clothing_with_mask(result_image, mask)
            temp_path = Path(f"/tmp/clothing_2d_{int(time.time())}.png")
            cropped.save(temp_path)

            mesh_path = self.generate_3d_mesh(temp_path)

            if temp_path.exists():
                temp_path.unlink()

        # Complete
        self._emit_state('COMPLETE')
        print("\n" + "="*70)
        print("    Creation complete!")
        print("="*70)

        # Save outputs
        output_dir = self.save_outputs(frame_rgb, mask, result_image, self.transcribed_text, mesh_path)
        print(f"    Saved to: {output_dir}")

        time.sleep(5)  # Show completion screen
        return True

    def run(self):
        """Main loop - runs continuously for installation mode"""

        print("\n" + "="*70)
        print("Starting Dream Wardrobe (Installation Mode)")
        print("="*70)
        print("   Press Ctrl+C to exit\n")

        # Initialize
        self.calibrate_microphone(duration=3.0)
        self.initialize_camera()

        # Main loop
        while True:
            try:
                self.run_session()
                print("\n    Ready for next user!\n")
                time.sleep(2)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n    Session error: {e}")
                self._emit_state('ERROR', error_message=str(e)[:50])
                time.sleep(3)


def main():
    """Entry point"""

    parser = argparse.ArgumentParser(description="Dream Wardrobe - Playtest Edition")
    parser.add_argument('--skip-3d', action='store_true',
                       help='Skip 3D mesh generation')
    parser.add_argument('--api-key', type=str,
                       help='Rodin API key (or set RODIN_API_KEY env var)')
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('RODIN_API_KEY')

    pipeline = None
    try:
        pipeline = SpeechTo2DPipeline(
            comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
            enable_3d=not args.skip_3d,
            rodin_api_key=api_key
        )
        pipeline.run()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if pipeline:
            pipeline.cleanup()
    except Exception as e:
        print(f"\nPipeline error: {e}")
        import traceback
        traceback.print_exc()
        if pipeline:
            pipeline.cleanup()


if __name__ == "__main__":
    main()
