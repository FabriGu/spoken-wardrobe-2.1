# File Structure

Complete file structure of the minimal repository:

```
spoken-wardrobe-minimal/
│
├── README.md                          # Main documentation
├── QUICKSTART.md                      # Quick start guide with examples
├── FILE_STRUCTURE.md                  # This file
├── .gitignore                         # Git ignore rules
│
├── setup_mac.sh                       # Automated setup script (Mac)
├── verify_setup.py                    # Installation verification script
│
├── requirements-core.txt              # Cross-platform dependencies
├── requirements-mac.txt               # Mac-specific dependencies (Apple Silicon)
├── requirements-pc.txt                # PC-specific dependencies (Windows + NVIDIA GPU)
│
├── src/
│   ├── __init__.py                    # Python package marker
│   └── modules/
│       ├── __init__.py                # Python package marker
│       ├── speechRecognition.py       # Whisper speech-to-text (296 lines)
│       ├── comfyui_client.py          # ComfyUI API client (546 lines)
│       └── speech_to_clothing_with_rodin_api.py  # Main pipeline (964 lines)
│
├── workflows/
│   └── sdxl_inpainting_api.json       # ComfyUI workflow configuration
│
├── external/
│   ├── README.md                      # External dependencies setup guide
│   └── depthai_blazepose/             # [TO BE CLONED] OAK-D BlazePose integration
│       ├── BlazeposeDepthaiEdge.py    # Main tracker class
│       └── BlazeposeRenderer.py        # Visualization renderer
│
└── venv/                              # [CREATED BY SETUP] Python virtual environment
```

## File Descriptions

### Documentation
- **README.md** - Complete setup guide, troubleshooting, usage instructions
- **QUICKSTART.md** - Step-by-step walkthrough with example session log
- **FILE_STRUCTURE.md** - This file, explaining the repository structure
- **.gitignore** - Prevents committing venv, outputs, API keys, etc.

### Setup & Verification
- **setup_mac.sh** - Automated setup script for Mac (installs deps, applies patches)
- **verify_setup.py** - Tests all imports and dependencies after installation

### Requirements Files
- **requirements-core.txt** - Core dependencies (numpy, opencv, mediapipe, pyaudio, etc.)
- **requirements-mac.txt** - Mac-specific (PyTorch MPS, TensorFlow-macos, BodyPix)
- **requirements-pc.txt** - PC-specific (PyTorch CUDA, TensorFlow GPU, BodyPix)

### Source Code

#### src/modules/speechRecognition.py (296 lines)
- Whisper-based speech-to-text transcription
- Microphone calibration for ambient noise
- Volume threshold detection
- 10-second fixed-duration recording
- Automatic transcription with OpenAI Whisper model

**Key Classes:**
- `SpeechRecognizer` - Main speech recognition class

**Dependencies:**
- pyaudio (microphone input)
- transformers (Whisper model)
- torch (inference)

#### src/modules/comfyui_client.py (546 lines)
- REST API client for remote ComfyUI server
- Handles image upload, workflow preparation, prompt queueing
- Polls for generation completion
- Downloads result images

**Key Classes:**
- `ComfyUIClient` - Main API client

**Dependencies:**
- requests (HTTP)
- PIL (image handling)
- numpy (array operations)

#### src/modules/speech_to_clothing_with_rodin_api.py (964 lines)
- **MAIN PIPELINE** - Orchestrates entire workflow
- Integrates all components (speech, camera, BodyPix, ComfyUI, Rodin)
- Handles calibration, recording, transcription, segmentation, generation
- Saves all outputs (images, masks, 3D mesh, metadata)

**Key Classes:**
- `BodyPartSelector` - Defines dress body parts for BodyPix
- `SpeechToClothingPipeline` - Main pipeline orchestrator

**Pipeline Steps:**
1. Microphone calibration (3s)
2. OAK-D camera initialization
3. Body detection (BlazePose)
4. Speech detection and recording (10s)
5. Whisper transcription
6. A-pose frame capture (3s countdown)
7. BodyPix segmentation
8. ComfyUI 2D generation (30-60s)
9. Rodin API 3D generation (60-90s)
10. Save all outputs

**Dependencies:**
- All of the above modules
- tf_bodypix (body segmentation)
- depthai (OAK-D camera)
- requests (Rodin API)

### Workflows

#### workflows/sdxl_inpainting_api.json (126 lines)
- ComfyUI workflow template for SDXL inpainting
- Defines nodes for: LoadImage, CLIPTextEncode, KSampler, VAEDecode, SaveImage
- Uses template variables: {PROMPT}, {NEGATIVE_PROMPT}, {INPUT_IMAGE}, {SEED}, {STEPS}, {CFG}
- Loads checkpoint: "512-inpainting-ema.safetensors"

### External Dependencies

#### external/depthai_blazepose/
- **NOT INCLUDED** - Must be cloned separately (see external/README.md)
- Provides OAK-D Pro camera integration with BlazePose pose estimation
- Required files:
  - `BlazeposeDepthaiEdge.py` - Main tracker class (camera interface, pose detection)
  - `BlazeposeRenderer.py` - Visualization renderer (draw skeleton, landmarks)

**Source:** https://github.com/geaxgx/depthai_blazepose (or extract from depthai-experiments)

## Total Line Counts

- **Python source code:** ~1,806 lines
- **JSON configuration:** ~126 lines
- **Documentation:** ~600+ lines (READMEs, guides)

## Disk Space

- **Source code + config:** ~50-100 KB
- **Python dependencies (after install):** ~5 GB
  - PyTorch: ~2 GB
  - TensorFlow: ~1.5 GB
  - Other packages: ~1.5 GB
- **AI models (downloaded at runtime):**
  - Whisper base: ~140 MB
  - BodyPix: ~50 MB
  - Stable Diffusion (on remote server): N/A
  - Rodin API (cloud): N/A
- **Output files (per generation):** ~2-5 MB
  - Original frame: ~1 MB
  - Mask: ~10 KB
  - Generated clothing: ~1 MB
  - 3D mesh (GLB): ~1-3 MB
  - Metadata: ~1 KB

## What's NOT Included (vs Original Repo)

These are intentionally excluded from the minimal setup:

- ❌ `tests/` - 40+ test files for cage deformation, skinning, etc.
- ❌ `docs/` - 45+ documentation markdown files
- ❌ `external/TripoSR/` - Alternative 3D generation method (not needed with Rodin API)
- ❌ `external/VIBE/`, `external/EasyMocap/` - Legacy motion capture systems
- ❌ `251025_data_verification/` - Cage verification tools
- ❌ `calibration_data/` - Old calibration files
- ❌ `generated_images/`, `generated_meshes/` - Example outputs
- ❌ All cage/skinning deformation code (not needed for static mesh generation)

**Size reduction:** ~45 MB of source code → ~50 KB (99% reduction)

## Output Directory (Created at Runtime)

```
comfyui_generated_mesh/
└── [timestamp]/                       # e.g., 1699999999/
    ├── original_frame.png             # Captured body frame
    ├── mask.png                       # BodyPix segmentation mask
    ├── generated_clothing.png         # 2D clothing from ComfyUI
    ├── clothing_mesh.glb              # 3D mesh from Rodin API
    └── metadata.json                  # Generation settings
```

Each run creates a new timestamped folder with all outputs.

## Modifying the Pipeline

### Change ComfyUI Server
Edit `speech_to_clothing_with_rodin_api.py` line 947:
```python
comfyui_url="http://your-server:port",
```

### Change Stable Diffusion Settings
Edit `speech_to_clothing_with_rodin_api.py` lines 380-394:
```python
seed = 100          # Random seed (change for variations)
steps = 35          # Inference steps (20-50, higher = better quality)
cfg = 9.5           # Guidance scale (7-12, higher = stricter prompt adherence)
```

### Change Rodin API Settings
Edit `speech_to_clothing_with_rodin_api.py` lines 428-434:
```python
'quality_override': '5000',      # Poly count: 5000 (low) to 10000 (high)
'material': 'PBR',               # PBR or Basic
'mesh_mode': 'Raw',              # Raw (triangles) or Quad
'mesh_simplify': 'true',         # Simplify mesh: true/false
```

### Use Different Microphone
Edit `speech_to_clothing_with_rodin_api.py` line 160:
```python
mic_index = self.find_microphone_by_name("Your Microphone Name")
```

### Adjust Volume Threshold
Edit `speech_to_clothing_with_rodin_api.py` line 194:
```python
self.volume_threshold = self.ambient_noise_level * 2.5  # Change 2.5 to lower (more sensitive) or higher (less sensitive)
```
