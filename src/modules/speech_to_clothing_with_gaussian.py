#!/usr/bin/env python3
"""
Speech-to-Clothing Pipeline with Gaussian Splats

Integrated pipeline that:
1. Calibrates microphone for ambient noise
2. Listens for user speech about dream dress
3. Transcribes with Whisper
4. Captures body frame with BodyPix segmentation
5. Generates clothing with ComfyUI (2D)
6. Extracts clothing using mask (clothing_only.png)
7. Generates Gaussian Splat from clothing (local, fast)
8. Saves all outputs (images, masks, PLY splat)

This is an alternative to speech_to_clothing_with_rodin_api.py that uses
local Gaussian splat generation instead of the Rodin cloud API.

Advantages:
- Fast: ~1 second vs 60-90 seconds for Rodin API
- Local: No API key or internet required for 3D
- Real-time: Splats can be animated with body tracking

Usage:
    python src/modules/speech_to_clothing_with_gaussian.py [--viewer] [--skip-3d]

Options:
    --viewer    Show OpenCV debug windows (for debugging only)
    --skip-3d   Skip 3D splat generation (2D only)
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
import os
import asyncio

# Add paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Add BlazePose path for OAK-D Pro
blazepose_path = project_root / "external" / "depthai_blazepose"
sys.path.insert(0, str(blazepose_path))

# Add gaussian_test path for splat generation
gaussian_test_path = project_root / "gaussian_test"
sys.path.insert(0, str(gaussian_test_path))

# Import existing modules
from modules.speechRecognition import SpeechRecognizer
from modules.comfyui_client import ComfyUIClient
from modules.prompt_enhancer import PromptEnhancer

# Import UI modules (optional)
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

# Import Gaussian splat generator
from generate_splat import GaussianSplatGenerator


def extract_clothing_from_inpaint(
    generated_path: str,
    mask_path: str,
    output_path: str
) -> str:
    """
    Extract clothing from inpainted image using mask.

    The inpainted image contains full scene (body + clothing).
    The mask shows which region was inpainted (the clothing area).
    This function extracts just the clothing on transparent background.

    Args:
        generated_path: Path to generated_clothing.png
        mask_path: Path to mask.png
        output_path: Where to save clothing_only.png

    Returns:
        Path to extracted clothing image
    """
    # Load images
    generated = cv2.imread(generated_path, cv2.IMREAD_COLOR)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    if generated is None:
        raise FileNotFoundError(f"Could not load: {generated_path}")
    if mask is None:
        raise FileNotFoundError(f"Could not load: {mask_path}")

    # Verify dimensions match
    if generated.shape[:2] != mask.shape[:2]:
        raise ValueError(
            f"Dimension mismatch: generated {generated.shape[:2]} vs mask {mask.shape[:2]}"
        )

    # Convert BGR to RGB
    rgb = cv2.cvtColor(generated, cv2.COLOR_BGR2RGB)

    # Create RGBA image with mask as alpha
    rgba = np.zeros((rgb.shape[0], rgb.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = mask  # Alpha channel from mask

    # Save with transparency (OpenCV needs BGRA)
    bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    cv2.imwrite(output_path, bgra)

    return output_path


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


class SpeechToClothingGaussianPipeline:
    """Main pipeline orchestrator with Gaussian Splat integration"""

    def __init__(
        self,
        comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
        show_viewer=False,
        enable_3d=True,
        enable_ui=False
    ):
        """Initialize pipeline components"""

        print("\n" + "=" * 70)
        print("Speech-to-Clothing Pipeline with Gaussian Splats")
        print("=" * 70)

        # Configuration
        self.comfyui_url = comfyui_url
        self.show_viewer = show_viewer
        self.enable_3d = enable_3d
        self.enable_ui = enable_ui
        self.current_state = "IDLE"

        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.audio_format = pyaudio.paInt16
        self.chunk_size = 1024
        self.recording_duration = 10.0

        # Initialize components
        print("\n📦 Initializing components...")

        # Speech recognizer
        self.speech_recognizer = SpeechRecognizer()
        print("  ✓ Speech recognizer")

        # BodyPix for segmentation
        print("  - Loading BodyPix model...")
        bodypix_model = download_model(BodyPixModelPaths.MOBILENET_FLOAT_50_STRIDE_16)
        self.bodypix = load_model(bodypix_model)
        print("  ✓ BodyPix model loaded")

        # ComfyUI client for 2D generation
        self.comfyui = ComfyUIClient(comfyui_url)
        print(f"  ✓ ComfyUI client ({comfyui_url})")

        # Gaussian splat generator (lazy init to speed up startup)
        self.splat_generator = None
        if enable_3d:
            print("  - Gaussian splat generator will be initialized on first use")

        # Prompt enhancer
        self.prompt_enhancer = PromptEnhancer()
        print("  ✓ Prompt enhancer")

        # Camera (initialized later)
        self.camera = None
        self.renderer = None
        self.body_processor = None

        # Volume threshold
        self.volume_threshold = 500
        self.ambient_noise_level = 0

        # UI components
        self.ws_server = None
        self.state_manager = None
        self.mesh_calibrator = None
        self.camera_broadcaster = None

        print("\n✅ Pipeline ready!")
        print("=" * 70)

    def _init_splat_generator(self):
        """Initialize Gaussian splat generator on first use"""
        if self.splat_generator is None:
            print("\n🔧 Initializing Gaussian splat generator...")
            self.splat_generator = GaussianSplatGenerator(use_depth=True)
            print("  ✓ Splat generator ready")

    def generate_gaussian_splat(self, clothing_image_path: str) -> dict:
        """
        Generate Gaussian splat from clothing image.

        Args:
            clothing_image_path: Path to clothing_only.png (transparent background)

        Returns:
            dict with 'success', 'output' (PLY path), 'timings', 'stats'
        """
        self._init_splat_generator()

        print(f"\n🎯 Generating Gaussian splat from: {Path(clothing_image_path).name}")
        start_time = time.time()

        result = self.splat_generator.generate(clothing_image_path)

        elapsed = time.time() - start_time

        if result['success']:
            print(f"  ✓ Generated {result['stats']['num_splats']:,} splats in {elapsed:.1f}s")
            print(f"  ✓ Output: {result['output']}")
        else:
            print(f"  ✗ Generation failed: {result['errors']}")

        return result

    def save_outputs(
        self,
        frame_rgb,
        mask,
        generated_image,
        splat_path,
        transcription,
        settings,
        timestamp
    ):
        """
        Save all pipeline outputs.

        Saves:
        - original_frame.png
        - mask.png
        - generated_clothing.png
        - clothing_only.png (NEW: extracted clothing with transparency)
        - clothing_splat.ply (NEW: Gaussian splat)
        - metadata.json
        """
        output_dir = project_root / "comfyui_generated_mesh" / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 Saving to: {output_dir}")

        # Save original frame
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(output_dir / "original_frame.png"), frame_bgr)
        print(f"  ✓ original_frame.png")

        # Save mask
        cv2.imwrite(str(output_dir / "mask.png"), mask)
        print(f"  ✓ mask.png")

        # Save generated 2D clothing (full inpainted image)
        generated_path = str(output_dir / "generated_clothing.png")
        generated_image.save(generated_path)
        print(f"  ✓ generated_clothing.png")

        # Extract clothing only (NEW)
        clothing_only_path = str(output_dir / "clothing_only.png")
        mask_path = str(output_dir / "mask.png")
        try:
            extract_clothing_from_inpaint(generated_path, mask_path, clothing_only_path)
            print(f"  ✓ clothing_only.png (extracted)")
        except Exception as e:
            print(f"  ✗ clothing_only.png failed: {e}")
            clothing_only_path = None

        # Copy splat if exists (NEW)
        if splat_path and Path(splat_path).exists():
            import shutil
            ply_dest = output_dir / "clothing_splat.ply"
            shutil.copy(splat_path, ply_dest)
            print(f"  ✓ clothing_splat.ply ({Path(splat_path).stat().st_size / 1024:.1f} KB)")

        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "transcription": transcription,
            "settings_2d": settings,
            "has_3d_splat": splat_path is not None,
            "3d_generation_method": "gaussian_splat_local"
        }
        with open(output_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ metadata.json")

        print(f"\n✅ All files saved to: {output_dir}")

        return output_dir

    # =========================================================================
    # The following methods are copied from speech_to_clothing_with_rodin_api.py
    # They handle microphone calibration, camera, body detection, etc.
    # =========================================================================

    def find_microphone_by_name(self, name_substring):
        """Find microphone device index by name"""
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if name_substring.lower() in info['name'].lower() and info['maxInputChannels'] > 0:
                p.terminate()
                return i
        p.terminate()
        return None

    def calibrate_microphone(self, duration=3.0):
        """Calibrate microphone for ambient noise"""
        print(f"\n🎤 Calibrating microphone ({duration}s)...")
        print("   Please remain quiet...")

        mic_index = self.find_microphone_by_name("MacBook Pro Microphone")
        if mic_index is None:
            print("   Using default microphone")
            mic_index = None

        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=self.chunk_size
        )

        max_volumes = []
        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio).mean()
                max_volumes.append(volume)
            except Exception as e:
                pass

        stream.stop_stream()
        stream.close()
        p.terminate()

        self.ambient_noise_level = np.mean(max_volumes) if max_volumes else 100
        self.volume_threshold = self.ambient_noise_level * 2.5

        print(f"   Ambient noise: {self.ambient_noise_level:.0f}")
        print(f"   Volume threshold: {self.volume_threshold:.0f}")
        print("   ✓ Calibration complete")

    def initialize_camera(self):
        """Initialize OAK-D Pro camera with BlazePose"""
        print("\n📷 Initializing OAK-D Pro camera...")

        try:
            self.camera = BlazeposeDepthai(
                input_src="rgb",
                internal_fps=30,
                internal_frame_height=720
            )
            self.renderer = self.camera.renderer if hasattr(self.camera, 'renderer') else None
            print("  ✓ OAK-D Pro initialized")
        except Exception as e:
            print(f"  ✗ Camera initialization failed: {e}")
            raise

    def get_frame(self):
        """Get frame from camera"""
        if self.camera is None:
            return None, None

        frame, body = self.camera.next_frame()
        return frame, body

    def is_body_detected(self, body):
        """Check if body is detected"""
        if body is None:
            return False
        return body.landmarks is not None and len(body.landmarks) > 0

    def get_body_segmentation(self, frame_rgb):
        """Segment body using BodyPix"""
        result = self.bodypix.predict_single(frame_rgb)

        # Create mask for dress parts
        mask = np.zeros(frame_rgb.shape[:2], dtype=np.uint8)
        for part_name in BodyPartSelector.DRESS_PARTS:
            part_mask = result.get_mask(threshold=0.5).numpy()
            colored_mask = result.get_colored_part_mask(
                result.get_part_mask(threshold=0.5),
                part_colors=None
            )
            part_indices = result.get_part_mask(threshold=0.5).numpy()
            # Add part to mask
            part_id = getattr(result, f'{part_name}_id', None)
            if part_id is not None:
                mask[part_indices == part_id] = 255

        # Fallback: use general body mask if no parts detected
        if mask.max() == 0:
            mask = (result.get_mask(threshold=0.5).numpy() * 255).astype(np.uint8)

        return mask

    def listen_for_speech(self):
        """Listen for speech and record"""
        print("\n🎙️ Listening for speech...")
        print(f"   Speak above volume threshold ({self.volume_threshold:.0f})")

        mic_index = self.find_microphone_by_name("MacBook Pro Microphone")

        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=self.chunk_size
        )

        # Wait for speech
        while True:
            data = stream.read(self.chunk_size, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio).mean()

            if volume > self.volume_threshold:
                print(f"\n   Speech detected! (volume: {volume:.0f})")
                break

        # Record
        print(f"   Recording for {self.recording_duration}s...")
        frames = []
        start_time = time.time()

        while time.time() - start_time < self.recording_duration:
            data = stream.read(self.chunk_size, exception_on_overflow=False)
            frames.append(data)
            remaining = self.recording_duration - (time.time() - start_time)
            print(f"   Recording... {remaining:.1f}s remaining", end='\r')

        print("\n   ✓ Recording complete")

        stream.stop_stream()
        stream.close()
        p.terminate()

        return b''.join(frames)

    def transcribe_audio(self, audio_data):
        """Transcribe audio using Whisper"""
        print("\n📝 Transcribing...")

        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        result = self.speech_recognizer.model.transcribe(
            audio_np,
            language="en",
            fp16=False
        )

        transcription = result['text'].strip()
        print(f"   \"{transcription}\"")

        return transcription

    def run(self):
        """Main pipeline execution"""

        print("\n" + "=" * 70)
        print("Starting Gaussian Splat Pipeline")
        print("=" * 70)
        print("   Press Ctrl+C to exit\n")

        # Initialize
        self.calibrate_microphone(duration=3.0)
        self.initialize_camera()

        print("\n👤 Waiting for body detection...")
        print("   Stand in front of OAK-D camera...")

        body_detected = False
        while not body_detected:
            frame, body = self.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            body_detected = self.is_body_detected(body)

            if self.show_viewer:
                cv2.imshow("Gaussian Pipeline", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    return

        print("   ✓ Body detected!")

        # Main loop
        while True:
            try:
                # Listen for speech
                audio_data = self.listen_for_speech()

                # Transcribe
                transcription = self.transcribe_audio(audio_data)

                if not transcription or len(transcription) < 3:
                    print("   No valid transcription, try again...")
                    continue

                # Enhance prompt
                enhanced_prompt = self.prompt_enhancer.enhance(transcription)
                print(f"\n🎨 Enhanced prompt: {enhanced_prompt}")

                # Capture A-pose frame
                print("\n📸 Please strike an A-pose...")
                time.sleep(3.0)
                frame, body = self.get_frame()

                if frame is None:
                    print("   ✗ Failed to capture frame")
                    continue

                # Convert to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Segment body
                print("\n🔍 Segmenting body...")
                mask = self.get_body_segmentation(frame_rgb)

                # Generate 2D clothing
                print("\n🖼️ Generating 2D clothing...")
                timestamp = str(int(time.time()))
                settings = {
                    "seed": 100,
                    "steps": 35,
                    "cfg": 9.5,
                    "denoise": 0.85
                }

                try:
                    # Upload to ComfyUI
                    pil_frame = Image.fromarray(frame_rgb)
                    pil_mask = Image.fromarray(mask)

                    frame_name = self.comfyui.upload_image(pil_frame, "input_frame.png")
                    mask_name = self.comfyui.upload_image(pil_mask, "input_mask.png")

                    # Generate
                    result_images = self.comfyui.generate_inpaint(
                        frame_name,
                        mask_name,
                        enhanced_prompt,
                        **settings
                    )

                    if not result_images:
                        print("   ✗ 2D generation failed")
                        continue

                    generated_image = result_images[0]
                    print("   ✓ 2D clothing generated")

                except Exception as e:
                    print(f"   ✗ 2D generation error: {e}")
                    continue

                # Generate 3D Gaussian splat
                splat_path = None
                if self.enable_3d:
                    # First save the 2D outputs
                    temp_dir = project_root / "comfyui_generated_mesh" / timestamp
                    temp_dir.mkdir(parents=True, exist_ok=True)

                    generated_path = str(temp_dir / "generated_clothing.png")
                    mask_path = str(temp_dir / "mask.png")
                    clothing_only_path = str(temp_dir / "clothing_only.png")

                    generated_image.save(generated_path)
                    cv2.imwrite(mask_path, mask)

                    # Extract clothing
                    print("\n✂️ Extracting clothing...")
                    try:
                        extract_clothing_from_inpaint(generated_path, mask_path, clothing_only_path)
                        print("   ✓ Clothing extracted")

                        # Generate splat
                        splat_result = self.generate_gaussian_splat(clothing_only_path)
                        if splat_result['success']:
                            splat_path = splat_result['output']

                    except Exception as e:
                        print(f"   ✗ Extraction/splat error: {e}")

                # Save all outputs
                self.save_outputs(
                    frame_rgb,
                    mask,
                    generated_image,
                    splat_path,
                    transcription,
                    settings,
                    timestamp
                )

                print("\n" + "=" * 70)
                print("✨ Generation complete! Ready for next input...")
                print("=" * 70)

            except KeyboardInterrupt:
                print("\n\n👋 Exiting...")
                break

        if self.show_viewer:
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='Speech-to-Clothing Pipeline with Gaussian Splats'
    )
    parser.add_argument(
        '--viewer',
        action='store_true',
        help='Show OpenCV debug viewer'
    )
    parser.add_argument(
        '--skip-3d',
        action='store_true',
        help='Skip Gaussian splat generation (2D only)'
    )
    parser.add_argument(
        '--comfyui-url',
        default='http://itp-ml.itp.tsoa.nyu.edu:9199',
        help='ComfyUI server URL'
    )

    args = parser.parse_args()

    pipeline = SpeechToClothingGaussianPipeline(
        comfyui_url=args.comfyui_url,
        show_viewer=args.viewer,
        enable_3d=not args.skip_3d
    )

    pipeline.run()


if __name__ == '__main__':
    main()
