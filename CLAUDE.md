# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spoken Wardrobe is a speech-to-clothing pipeline that generates 3D clothing meshes from voice descriptions. The pipeline integrates:
- Speech recognition (OpenAI Whisper)
- Body tracking (OAK-D Pro camera + BlazePose)
- Body segmentation (TensorFlow BodyPix)
- 2D clothing generation (Stable Diffusion via remote ComfyUI server)
- 3D mesh generation (Rodin API)

## Development Commands

### Setup

**Mac (Automated):**
```bash
./setup_mac.sh
```

**Manual setup:**
```bash
python3.11 -m venv venv
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

pip install --upgrade pip setuptools wheel
pip install -r requirements-core.txt
pip install -r requirements-mac.txt  # or requirements-pc.txt

# Apply critical patch for tfjs-graph-converter (Mac):
sed -i '' 's/np\.bool$/np.bool_/g' venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py

# Setup external dependencies:
cd external
git clone https://github.com/geaxgx/depthai_blazepose.git
cd ..
```

### Run Pipeline

```bash
# Set API key
export RODIN_API_KEY="your_api_key_here"

# Run full pipeline
python src/modules/speech_to_clothing_with_rodin_api.py

# Run with debug viewer
python src/modules/speech_to_clothing_with_rodin_api.py --viewer

# Run with browser UI (Three.js)
python src/modules/speech_to_clothing_with_rodin_api.py --ui
# Then open http://localhost:8080 in browser

# Skip 3D generation (2D only)
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d
```

### Test UI Only (Development)

```bash
# Test UI without camera/pipeline (cycles through states)
python test_ui_server.py
# Then open http://localhost:8080 in browser
```

### Verify Installation

```bash
python verify_setup.py
```

## Architecture

### Pipeline Flow

The main orchestrator is `SpeechToClothingPipeline` in `speech_to_clothing_with_rodin_api.py`. The pipeline executes these steps sequentially:

1. **Microphone Calibration** (3s): Measures ambient noise to set volume threshold
2. **Camera Initialization**: Connects to OAK-D Pro camera with BlazePose
3. **Body Detection**: Waits for user to appear in camera frame (BlazePose detection)
4. **Speech Detection**: Listens for volume spike above threshold
5. **Recording** (10s fixed): Records audio once speech detected
6. **Transcription**: Whisper base model transcribes audio to text
7. **A-pose Capture**: 3-second countdown for user to strike A-pose
8. **BodyPix Segmentation**: Segments body parts (torso, arms, upper legs) from frame
9. **2D Generation** (30-60s): ComfyUI server generates clothing via SDXL inpainting
10. **3D Generation** (60-90s): Rodin API converts 2D image to 3D GLB mesh
11. **Save Outputs**: All results saved to timestamped folder

### Module Responsibilities

**`speechRecognition.py`** - Audio capture and transcription
- `SpeechRecognizer`: Manages PyAudio streams, Whisper model loading
- Device detection (MPS for Mac, CUDA for NVIDIA, CPU fallback)
- Fixed 10-second recording duration after speech trigger
- 16kHz mono audio (Whisper's preferred format)

**`comfyui_client.py`** - Remote Stable Diffusion generation
- `ComfyUIClient`: REST API client for remote ComfyUI server
- Image upload (multipart/form-data)
- Workflow template loading from JSON with variable substitution
- Prompt queueing and polling for completion
- Result image download

**`speech_to_clothing_with_rodin_api.py`** - Main pipeline orchestrator
- `BodyPartSelector`: Defines which BodyPix parts to segment (dress coverage)
- `SpeechToClothingPipeline`: Orchestrates entire workflow
- Rodin API integration (direct HTTP requests, not via ComfyUI)
- State machine for pipeline stages
- WebSocket UI integration (optional, enabled with `--ui` flag)
- Output saving with metadata

### UI Module (`src/ui/`)

**`websocket_server.py`** - WebSocket server for pipeline-UI communication
- `PipelineWebSocketServer`: Async WebSocket server (runs in daemon thread)
- `run_server_in_thread()`: Helper to start server in background
- Broadcasts state changes, camera frames (30 FPS), audio levels, and mesh data
- Thread-safe message queue for sync pipeline → async WebSocket

**`state_manager.py`** - Pipeline state machine with UI sync
- `StateManager`: Manages state transitions and emits to WebSocket
- States: IDLE, LISTENING, RECORDING, TRANSCRIBING, A_POSE, CAPTURING, GENERATING_2D, GENERATING_3D, PREVIEW, CALIBRATING, TRY_ON, ERROR
- Tracks transition history for debugging

**`mesh_calibrator.py`** - BlazePose-based mesh positioning
- `MeshCalibrator`: Computes mesh position/scale/rotation from body landmarks
- Uses shoulders (11, 12) and hips (23, 24) for body center and scale
- `validate_a_pose()`: Checks if user has arms extended correctly
- `calibrate_offset()`: Sets reference position during A-pose capture
- Exponential smoothing for jitter reduction

### Frontend (`static/`)

**`index.html`** - Main HTML with Three.js imports
- All UI state screens as div elements (hidden/shown via CSS)
- Three.js canvas for 3D mesh rendering

**`css/style.css`** - Dark theme styling
- Purple/pink gradient accents matching mockups
- CSS animations for countdowns, waveforms, progress rings

**`js/app.js`** - Main application entry
- Initializes WebSocket client, state manager, Three.js scene
- Connects WebSocket handlers to UI updates

**`js/websocket.js`** - WebSocket client
- Handles connection, reconnection, heartbeat
- Dispatches messages to appropriate handlers

**`js/state_manager.js`** - Frontend state machine
- Shows/hides state screens
- Updates waveforms, progress rings, countdowns

**`js/three_scene.js`** - Three.js scene setup
- Loads GLB mesh from base64
- Updates mesh transform from calibration data
- Smooth interpolation using lerp

### External Dependencies

**BlazePose (external/depthai_blazepose/)** - Not included in repo
- Must be cloned separately: `git clone https://github.com/geaxgx/depthai_blazepose.git`
- Provides `BlazeposeDepthai` for OAK-D camera + pose tracking
- Provides `BlazeposeRenderer` for optional debug visualization

**ComfyUI Server** - Remote service
- Default: `http://itp-ml.itp.tsoa.nyu.edu:9199` (NYU network)
- Uses workflow: `workflows/sdxl_inpainting_api.json`
- Checkpoint: `512-inpainting-ema.safetensors` (must exist on server)

**Rodin API** - Cloud service
- Endpoint: `https://api.hyper3d.com/api/v2/rodin`
- Requires API key: `RODIN_API_KEY` environment variable
- Get key from: https://hyperhuman.deemos.com/
- Tier: "Regular" with ~5000 faces (configurable in code)

### Key Configuration Points

**Microphone device** - `speech_to_clothing_with_rodin_api.py:160`
```python
mic_index = self.find_microphone_by_name("MacBook Pro Microphone")
```
Change device name or set to `None` for system default.

**Volume threshold** - `speech_to_clothing_with_rodin_api.py:194`
```python
self.volume_threshold = self.ambient_noise_level * 2.5
```
Lower multiplier = more sensitive, higher = less sensitive.

**Stable Diffusion settings** - `speech_to_clothing_with_rodin_api.py:380-393`
```python
seed = 100          # Random seed (change for variations)
steps = 35          # Inference steps (20-50 range)
cfg = 9.5           # Guidance scale (7-12 range)
```

**Rodin API quality** - `speech_to_clothing_with_rodin_api.py:428-434`
```python
'tier': 'Regular',
'quality_override': '5000',      # Poly count (5000-10000)
'material': 'PBR',               # PBR or Basic
'mesh_mode': 'Raw',              # Raw (triangles) or Quad
'mesh_simplify': 'true',         # Simplify mesh: true/false
```

**ComfyUI server URL** - `speech_to_clothing_with_rodin_api.py:947` (main block)
```python
pipeline = SpeechToClothingPipeline(
    comfyui_url="http://itp-ml.itp.tsoa.nyu.edu:9199",
    ...
)
```

### Body Part Selection

`BodyPartSelector.DRESS_PARTS` defines which BodyPix body parts are included in the clothing mask:
- Torso (front/back)
- Both arms (upper/lower, front/back)
- Upper legs (front/back)

Does NOT include: lower legs, feet, hands, face. To change coverage area, modify the `DRESS_PARTS` list.

## Platform-Specific Notes

### Mac (Apple Silicon)

- Uses MPS (Metal Performance Shaders) for GPU acceleration
- PyAudio requires system dependency: `brew install portaudio`
- TensorFlow requires special packages: `tensorflow-macos` + `tensorflow-metal`
- NumPy compatibility: tfjs-graph-converter requires manual patch (change `np.bool` to `np.bool_` in util.py)

### PC (Windows + NVIDIA)

- Uses CUDA for GPU acceleration
- Requires CUDA 11.8+ and compatible cuDNN
- Use regular `tensorflow` package (not tensorflow-macos)
- Different PyAudio installation on Windows (may need unofficial wheel)

### Python Version

- **Python 3.11.x REQUIRED** - Not 3.12+ (incompatible with some dependencies)
- Virtual environment strongly recommended

## Output Structure

All pipeline runs save to: `comfyui_generated_mesh/[unix_timestamp]/`

**Output files:**
- `original_frame.png` - Captured body frame (RGB)
- `mask.png` - BodyPix segmentation mask (grayscale)
- `generated_clothing.png` - 2D clothing from Stable Diffusion
- `clothing_mesh.glb` - 3D mesh from Rodin API
- `metadata.json` - Generation parameters (prompt, seed, steps, cfg, timestamps)

## Common Issues & Solutions

**"Cannot connect to ComfyUI server"**
- Check network: `curl http://itp-ml.itp.tsoa.nyu.edu:9199/system_stats`
- May require NYU VPN
- Or configure own ComfyUI server and update URL

**"RODIN_API_KEY not set"**
- Set environment variable: `export RODIN_API_KEY="sk-..."`
- Or pass via CLI: `--api-key "sk-..."`

**"Cannot import BlazeposeDepthaiEdge"**
- Clone repository: `cd external && git clone https://github.com/geaxgx/depthai_blazepose.git`
- Verify: `ls external/depthai_blazepose/BlazeposeDepthaiEdge.py`

**"OAK-D camera not detected"**
- Ensure OAK-D Pro is connected via USB 3.0
- Try different USB port
- Check device appears: `lsusb | grep Movidius` (Linux) or System Report (Mac)

**"tfjs_graph_converter error: np.bool"**
- Apply patch: `sed -i '' 's/np\.bool$/np.bool_/g' venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py`
- Or manually edit util.py line 30: change `return np.bool` to `return np.bool_`

**"Speech not detected"**
- Speak louder or closer to microphone
- Check system microphone permissions
- Lower threshold multiplier (line 194)

## Code Modification Guidelines

When modifying this codebase:

1. **Maintain NumPy 1.24.3** - Do not upgrade to 2.x (breaks TensorFlow/BodyPix compatibility)
2. **Workflow changes require server sync** - If modifying `sdxl_inpainting_api.json`, ensure ComfyUI server has matching checkpoint and node configuration
3. **State transitions are sequential** - Pipeline stages depend on previous stages completing; do not parallelize
4. **Fixed recording duration** - Whisper works best with consistent audio lengths; avoid variable-length recording
5. **BodyPix requires RGB** - Always convert BGR to RGB before BodyPix inference
6. **Rodin API is rate-limited** - Free tier has daily limits; consider caching or --skip-3d during development

## Testing the Pipeline

**Quick test (no API key needed):**
```bash
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d
```
Tests microphone, camera, speech recognition, BodyPix, and ComfyUI integration without consuming Rodin API credits.

**Verification script:**
```bash
python verify_setup.py
```
Checks all imports and dependencies without running full pipeline.

## Removed from Minimal Version

This minimal pipeline excludes:
- Cage deformation system (chumpy, scipy)
- 3D mesh processing utilities (trimesh, pyglet, networkx)
- TripoSR (alternative 3D generation, superseded by Rodin API)
- Linear Blend Skinning (gpytoolbox)
- Local Stable Diffusion (diffusers, accelerate)

Focus is on the core speech-to-3D-clothing pipeline with external services (ComfyUI, Rodin API).

**Re-added in this version:**
- WebSocket UI for browser-based Three.js interface (`--ui` flag)
- Mesh calibration using BlazePose landmarks
