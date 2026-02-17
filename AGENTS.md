# Spoken Wardrobe - Agent Guide

This file provides comprehensive guidance for AI coding agents working on the Spoken Wardrobe project.

## Project Overview

**Spoken Wardrobe** is an AI-powered speech-to-clothing pipeline that generates 3D clothing meshes from voice descriptions. It's an interactive installation that combines computer vision, speech recognition, and generative AI.

### Pipeline Flow

1. **Microphone Calibration** (3s) - Measures ambient noise to set volume threshold
2. **Camera Initialization** - Connects to OAK-D Pro camera with BlazePose
3. **Body Detection** - Waits for user to appear in camera frame
4. **Speech Detection** - Listens for volume spike above threshold
5. **Recording** (10s fixed) - Records audio once speech detected
6. **Transcription** - Whisper base model transcribes audio to text
7. **A-pose Capture** - 3-second countdown for user to strike A-pose
8. **BodyPix Segmentation** - Segments body parts from captured frame
9. **2D Generation** (30-60s) - ComfyUI server generates clothing via SDXL inpainting
10. **3D Generation** (60-90s) - Rodin API converts 2D image to 3D GLB mesh
11. **Save Outputs** - All results saved to timestamped folder

### Hardware Requirements

- **Microphone** (PyAudio compatible)
- **OAK-D Pro Camera** (for BlazePose depth tracking)
- **GPU** (recommended): Apple Silicon M1/M2/M3 (MPS) or NVIDIA GPU with CUDA 11.8+

### External Services

- **ComfyUI Server**: Remote Stable Diffusion generation (default: NYU network)
- **Rodin API**: 3D mesh generation from 2D images (requires API key)

## Technology Stack

### Core Technologies

| Category | Technology | Version |
|----------|------------|---------|
| Language | Python | 3.11.x (REQUIRED) |
| AI/ML Framework | PyTorch | 2.1.0 |
| AI/ML Framework | TensorFlow | 2.15.0 |
| Speech Recognition | OpenAI Whisper | via transformers 4.35.2 |
| Body Segmentation | TensorFlow BodyPix | 0.1.0 |
| Pose Tracking | MediaPipe + OAK-D | 0.10.8 |
| Camera Interface | DepthAI | 2.24.0.0 |
| Frontend | Three.js | 0.160.0 (CDN) |

### Python Dependencies

**Core (Cross-Platform):**
- numpy==1.24.3 (pinned for compatibility)
- opencv-python-headless==4.8.1.78
- mediapipe==0.10.8
- pillow==10.1.0
- pyaudio==0.2.14
- requests==2.31.0
- websockets>=12.0
- aiohttp>=3.9.0

**Mac-Specific:**
- torch==2.1.0 (with MPS support)
- tensorflow-macos==2.15.0
- tensorflow-metal==1.1.0
- tf-bodypix==0.1.0
- depthai==2.24.0.0

**PC-Specific:**
- PyTorch with CUDA (install via PyTorch website)
- tensorflow==2.15.0

### Frontend Stack

- **Three.js** - 3D mesh rendering and scene management
- **WebSocket** - Real-time communication with Python backend
- **ES6 Modules** - Modern JavaScript module system
- **CSS3** - Animations and styling

## Project Structure

```
spoken-wardrobe-minimal/
│
├── src/
│   ├── modules/
│   │   ├── speechRecognition.py           # Whisper speech-to-text
│   │   ├── comfyui_client.py              # ComfyUI REST API client
│   │   ├── speech_to_clothing_with_rodin_api.py  # Main pipeline orchestrator
│   │   ├── prompt_enhancer.py             # LLM/rule-based prompt enhancement
│   │   └── speech_to_2d_generation.py     # 2D-only pipeline variant
│   │
│   ├── ui/
│   │   ├── websocket_server.py            # WebSocket server for UI communication
│   │   ├── state_manager.py               # Pipeline state machine
│   │   ├── mesh_calibrator.py             # BlazePose-based mesh positioning
│   │   ├── camera_broadcaster.py          # Continuous camera streaming thread
│   │   └── bone_rotation_calculator.py    # Skeletal animation calculations
│   │
│   ├── utils/
│   │   └── firebase_storage.py            # Cloud storage for gallery (optional)
│   │
│   └── pose/
│       └── mediapipe_pose.py              # MediaPipe pose utilities
│
├── static/                                 # Frontend assets
│   ├── index.html                         # Main UI page
│   ├── css/style.css                      # Dark theme styling
│   └── js/
│       ├── app.js                         # Main application entry
│       ├── websocket.js                   # WebSocket client
│       ├── state_manager.js               # Frontend state machine
│       ├── three_scene.js                 # Three.js scene setup
│       ├── keypoint_renderer.js           # BlazePose keypoint overlay
│       └── mesh_loading_animation.js      # 3D loading animation
│
├── workflows/
│   └── sdxl_inpainting_api.json           # ComfyUI workflow configuration
│
├── external/
│   └── depthai_blazepose/                 # OAK-D BlazePose (clone separately)
│       ├── BlazeposeDepthaiEdge.py
│       └── BlazeposeRenderer.py
│
├── comfyui_generated_mesh/                # Output directory (created at runtime)
│
├── requirements-core.txt                  # Cross-platform dependencies
├── requirements-mac.txt                   # Mac-specific dependencies
├── requirements-pc.txt                    # PC-specific dependencies
├── setup_mac.sh                           # Automated Mac setup script
└── verify_setup.py                        # Installation verification
```

## Build and Setup Commands

### Automated Setup (Mac)

```bash
./setup_mac.sh
```

This script will:
1. Check Python 3.11.x
2. Install portaudio via Homebrew
3. Create virtual environment
4. Install all dependencies
5. Apply tfjs-graph-converter patch
6. Clone depthai_blazepose (if requested)
7. Verify installation

### Manual Setup

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements-core.txt
pip install -r requirements-mac.txt  # or requirements-pc.txt

# Apply critical patch (Mac/Linux)
sed -i '' 's/np\.bool$/np.bool_/g' venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py

# Setup external dependencies
cd external
git clone https://github.com/geaxgx/depthai_blazepose.git
cd ..
```

### Verification

```bash
python verify_setup.py
```

## Run Commands

### Full Pipeline

```bash
# Set API key first
export RODIN_API_KEY="your_api_key_here"

# Run pipeline
python src/modules/speech_to_clothing_with_rodin_api.py

# With browser UI
python src/modules/speech_to_clothing_with_rodin_api.py --ui

# With debug viewer (OpenCV windows)
python src/modules/speech_to_clothing_with_rodin_api.py --viewer

# Skip 3D generation (2D only, no API credits used)
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d
```

### Test UI Only (Development)

```bash
python test_ui_server.py
# Then open http://localhost:8080 in browser
```

## Code Organization

### Module Responsibilities

#### `speechRecognition.py`
- Audio capture and transcription
- Device detection (MPS/CUDA/CPU)
- Fixed 10-second recording duration
- 16kHz mono audio (Whisper's preferred format)

**Key Class:** `SpeechRecognizer`

#### `comfyui_client.py`
- REST API client for remote ComfyUI server
- Image upload (multipart/form-data)
- Workflow template loading with variable substitution
- Prompt queueing and polling for completion

**Key Class:** `ComfyUIClient`

#### `speech_to_clothing_with_rodin_api.py`
- Main pipeline orchestrator
- Rodin API integration (direct HTTP requests)
- State machine for pipeline stages
- WebSocket UI integration (optional, `--ui` flag)
- Output saving with metadata

**Key Classes:**
- `BodyPartSelector` - Defines BodyPix parts for clothing mask
- `SpeechToClothingPipeline` - Main orchestrator

#### `prompt_enhancer.py`
- Transforms simple descriptions into creative prompts
- OpenAI API integration (optional)
- Rule-based fallback enhancement
- Content filtering (blocks sexualized terms)

#### `websocket_server.py`
- Async WebSocket server (runs in daemon thread)
- Broadcasts state changes, camera frames (30 FPS), audio levels, mesh data
- Thread-safe message queue for sync pipeline → async WebSocket

**Key Class:** `PipelineWebSocketServer`

#### `state_manager.py`
- Pipeline state machine with UI sync
- Tracks transition history for debugging

**States:** IDLE, LISTENING, RECORDING, TRANSCRIBING, A_POSE, CAPTURING, GENERATING_2D, GENERATING_3D, PREVIEW, CALIBRATING, TRY_ON, ERROR

**Key Class:** `StateManager`

#### `mesh_calibrator.py`
- Computes mesh position/scale/rotation from body landmarks
- Uses shoulders (11, 12) and hips (23, 24) for body center and scale
- A-pose validation
- Exponential smoothing for jitter reduction

**Key Class:** `MeshCalibrator`

#### `camera_broadcaster.py`
- Continuous camera streaming in background thread
- Non-blocking frame access for pipeline
- Skeleton/keypoint overlay rendering
- Fatal error detection and recovery signaling

**Key Class:** `CameraBroadcaster`

## Development Conventions

### Code Style

- **Python**: Follow PEP 8
- **JavaScript**: ES6+ features, 2-space indentation
- **Comments**: Use docstrings for Python classes/functions
- **Type Hints**: Use where appropriate for clarity

### Key Configuration Points

**Microphone device** - `speech_to_clothing_with_rodin_api.py:302`
```python
mic_index = self.find_microphone_by_name("MacBook Pro Microphone")
```

**Volume threshold** - `speech_to_clothing_with_rodin_api.py:336`
```python
self.volume_threshold = self.ambient_noise_level * 2.5
```

**Stable Diffusion settings** - `speech_to_clothing_with_rodin_api.py:679-681`
```python
seed = 100          # Random seed
steps = 35          # Inference steps (20-50 range)
cfg = 9.5           # Guidance scale (7-12 range)
```

**Rodin API quality** - `speech_to_clothing_with_rodin_api.py:824-830`
```python
'tier': 'Regular',
'quality_override': '5000',      # Poly count (5000-10000)
'material': 'PBR',               # PBR or Basic
'mesh_mode': 'Raw',              # Raw or Quad
'mesh_simplify': 'true',
```

**ComfyUI server URL** - `speech_to_clothing_with_rodin_api.py` (main block)
```python
pipeline = SpeechToClothingPipeline(
    comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
    ...
)
```

### Body Part Selection

`BodyPartSelector.DRESS_PARTS` defines which BodyPix body parts are included:
- Torso (front/back)
- Both arms (upper/lower, front/back)
- Upper legs (front/back)

### NumPy Compatibility

**CRITICAL**: Maintain NumPy 1.24.3 - Do not upgrade to 2.x (breaks TensorFlow/BodyPix compatibility)

## Testing Instructions

### Quick Test (No API Key)

```bash
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d
```

Tests microphone, camera, speech recognition, BodyPix, and ComfyUI integration without consuming Rodin API credits.

### Verification Script

```bash
python verify_setup.py
```

Checks all imports and dependencies without running full pipeline.

### Test Individual Components

```bash
# Test speech recognition only
python src/modules/speechRecognition.py

# Test ComfyUI client only
python src/modules/comfyui_client.py

# Test prompt enhancer only
python src/modules/prompt_enhancer.py
```

## Security Considerations

### API Keys

- **RODIN_API_KEY**: Set via environment variable, never commit to repo
- **OPENAI_API_KEY**: Optional, for LLM prompt enhancement
- **Firebase Credentials**: Store as `firebase-credentials.json` (already in .gitignore)

### Network Security

- ComfyUI server is on NYU network (may require VPN)
- Rodin API uses HTTPS
- WebSocket server runs on localhost only

### File Security

- Output directory `comfyui_generated_mesh/` contains generated content
- External dependencies in `external/` are git-cloned

## Common Issues & Solutions

### "Cannot connect to ComfyUI server"
- Check network: `curl http://itp-ml.itp.tsoa.nyu.edu:9199/system_stats`
- May require NYU VPN
- Or configure own ComfyUI server and update URL

### "RODIN_API_KEY not set"
- Set environment variable: `export RODIN_API_KEY="sk-..."`
- Or pass via CLI: `--api-key "sk-..."`

### "Cannot import BlazeposeDepthaiEdge"
- Clone repository: `cd external && git clone https://github.com/geaxgx/depthai_blazepose.git`
- Verify: `ls external/depthai_blazepose/BlazeposeDepthaiEdge.py`

### "OAK-D camera not detected"
- Ensure OAK-D Pro is connected via USB 3.0
- Try different USB port
- Check device appears: `lsusb | grep Movidius` (Linux) or System Report (Mac)

### "tfjs_graph_converter error: np.bool"
- Apply patch: `sed -i '' 's/np\.bool$/np.bool_/g' venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py`
- Or manually edit util.py line 30: change `return np.bool` to `return np.bool_`

### "Speech not detected"
- Speak louder or closer to microphone
- Check system microphone permissions
- Lower threshold multiplier (line 336)

## Platform-Specific Notes

### Mac (Apple Silicon)

- Uses MPS (Metal Performance Shaders) for GPU acceleration
- PyAudio requires system dependency: `brew install portaudio`
- TensorFlow requires special packages: `tensorflow-macos` + `tensorflow-metal`
- NumPy compatibility: tfjs-graph-converter requires manual patch

### PC (Windows + NVIDIA)

- Uses CUDA for GPU acceleration
- Requires CUDA 11.8+ and compatible cuDNN
- Use regular `tensorflow` package (not tensorflow-macos)
- Different PyAudio installation on Windows (may need unofficial wheel)

## Output Structure

All pipeline runs save to: `comfyui_generated_mesh/[unix_timestamp]/`

**Output files:**
- `original_frame.png` - Captured body frame (RGB)
- `mask.png` - BodyPix segmentation mask (grayscale)
- `generated_clothing.png` - 2D clothing from Stable Diffusion
- `clothing_mesh.glb` - 3D mesh from Rodin API
- `metadata.json` - Generation parameters (prompt, seed, steps, cfg, timestamps)

## Code Modification Guidelines

1. **Maintain NumPy 1.24.3** - Do not upgrade to 2.x
2. **Workflow changes require server sync** - If modifying `sdxl_inpainting_api.json`, ensure ComfyUI server has matching checkpoint and node configuration
3. **State transitions are sequential** - Pipeline stages depend on previous stages completing
4. **Fixed recording duration** - Whisper works best with consistent audio lengths
5. **BodyPix requires RGB** - Always convert BGR to RGB before BodyPix inference
6. **Rodin API is rate-limited** - Free tier has daily limits; consider caching or --skip-3d during development
