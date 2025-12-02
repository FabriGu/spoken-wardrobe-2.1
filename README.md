# Spoken Wardrobe - Minimal Pipeline

Minimal setup for the Speech-to-Clothing pipeline with Rodin API 3D mesh generation.

## What This Does

1. **Calibrates microphone** for ambient noise
2. **Listens for speech** about your dream clothing
3. **Transcribes with Whisper** AI
4. **Captures body frame** with OAK-D Pro camera + BodyPix segmentation
5. **Generates 2D clothing** with ComfyUI (remote Stable Diffusion)
6. **Generates 3D mesh** with Rodin API
7. **Saves all outputs** (images, masks, GLB mesh)

## Hardware Requirements

- **Microphone** (PyAudio compatible)
- **OAK-D Pro Camera** (for BlazePose depth tracking)
- **GPU** (recommended):
  - Mac: Apple Silicon M1/M2/M3 (MPS)
  - PC: NVIDIA GPU with CUDA 11.8+

## Network Requirements

Access to:
- **ComfyUI Server**: `http://itp-ml.itp.tsoa.nyu.edu:9199` (or your own)
- **Rodin API**: `https://api.hyper3d.com/api/v2`

## Setup Instructions

### 1. Prerequisites

- **Python 3.11.x** (REQUIRED)
  ```bash
  python3 --version  # Should show 3.11.x
  ```

- **Git**
  ```bash
  git --version
  ```

### 2. Create Virtual Environment

```bash
cd ~/Projects/spoken-wardrobe-minimal
python3.11 -m venv venv
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows
```

### 3. Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### 4. Install Core Dependencies

```bash
pip install -r requirements-core.txt
```

**Expected time:** ~2-3 minutes

### 5. Install Platform-Specific Dependencies

**For Mac (Apple Silicon):**
```bash
pip install -r requirements-mac.txt
```

**For PC (NVIDIA GPU):**
```bash
pip install -r requirements-pc.txt
```

**Expected time:** ~5-10 minutes (downloads PyTorch, TensorFlow, etc.)

### 6. Apply Critical Patch for tfjs-graph-converter

**Mac/Linux:**
```bash
sed -i '' 's/np\.bool$/np.bool_/g' venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py
```

**PC (Windows PowerShell):**
```powershell
(Get-Content venv\Lib\site-packages\tfjs_graph_converter\util.py) -replace 'np\.bool$', 'np.bool_' | Set-Content venv\Lib\site-packages\tfjs_graph_converter\util.py
```

**Or manually edit:** `venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py`
- Line 30: Change `return np.bool` to `return np.bool_`

### 7. Setup External Dependencies

See `external/README.md` for detailed instructions on setting up `depthai_blazepose`.

**Quick setup:**
```bash
cd external
git clone https://github.com/geaxgx/depthai_blazepose.git
cd ..
```

**Verify:**
```bash
python -c "import sys; sys.path.insert(0, 'external/depthai_blazepose'); from BlazeposeDepthaiEdge import BlazeposeDepthai; print('✓ BlazePose OK')"
```

### 8. Get Rodin API Key

1. Go to: https://hyperhuman.deemos.com/
2. Sign up and get your API key
3. Set environment variable:

**Mac/Linux:**
```bash
export RODIN_API_KEY="your_api_key_here"
```

**Windows:**
```cmd
set RODIN_API_KEY=your_api_key_here
```

**Permanent setup (add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export RODIN_API_KEY="your_api_key_here"' >> ~/.zshrc
```

### 9. Verify Installation

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import tensorflow as tf; print(f'TensorFlow: {tf.__version__}')"
python -c "import mediapipe; print('MediaPipe OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "from tf_bodypix.api import load_model; print('BodyPix OK')"
```

## Usage

### Run the Full Pipeline

```bash
python src/modules/speech_to_clothing_with_rodin_api.py
```

### Command-Line Options

```bash
# Show OpenCV debug windows (for debugging)
python src/modules/speech_to_clothing_with_rodin_api.py --viewer

# Skip 3D mesh generation (2D only)
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d

# Provide API key via command line
python src/modules/speech_to_clothing_with_rodin_api.py --api-key "your_key"
```

### Pipeline Flow

1. **Calibration** (3 seconds) - Stay quiet
2. **Body detection** - Stand in front of OAK-D camera
3. **Speech detection** - Speak when prompted (volume threshold)
4. **Recording** (10 seconds fixed duration)
5. **Transcription** (Whisper processes your speech)
6. **A-pose capture** (3 second countdown)
7. **BodyPix segmentation** (generates body part mask)
8. **2D generation** (ComfyUI Stable Diffusion ~30-60s)
9. **3D generation** (Rodin API ~60-90s)
10. **Save outputs** to `comfyui_generated_mesh/[timestamp]/`

### Output Files

All results saved to: `comfyui_generated_mesh/[timestamp]/`

- `original_frame.png` - Captured body frame
- `mask.png` - BodyPix segmentation mask
- `generated_clothing.png` - 2D clothing from Stable Diffusion
- `clothing_mesh.glb` - 3D mesh from Rodin API
- `metadata.json` - Generation settings and parameters

## Troubleshooting

### "Cannot connect to ComfyUI server"

- Check network connection
- Verify you're on NYU network or VPN
- Test: `curl http://itp-ml.itp.tsoa.nyu.edu:9199/system_stats`

### "RODIN_API_KEY not set"

```bash
export RODIN_API_KEY="your_key_here"
# Verify:
echo $RODIN_API_KEY
```

### "Cannot import BlazeposeDepthaiEdge"

- Check `external/depthai_blazepose/` exists
- See `external/README.md` for setup instructions
- Verify: `ls external/depthai_blazepose/BlazeposeDepthaiEdge.py`

### "OAK-D camera not detected"

- Ensure OAK-D Pro is plugged in via USB
- Try different USB port (USB 3.0 recommended)
- Check: `lsusb | grep Movidius` (Linux) or System Report (Mac)

### "Microphone not detected"

- Check system microphone permissions
- Mac: System Preferences > Security & Privacy > Microphone
- The script defaults to "MacBook Pro Microphone" - edit line 160 if needed

### "tfjs_graph_converter error: np.bool"

- Apply the manual patch (Step 6 above)
- This is a NumPy 1.23+ compatibility issue

### Low quality 3D mesh

- Rodin API tier is set to "Regular" with ~5000 faces
- Edit line 428-434 in `speech_to_clothing_with_rodin_api.py` to adjust quality
- Higher quality = longer generation time + more credits

## Project Structure

```
spoken-wardrobe-minimal/
├── src/
│   └── modules/
│       ├── speechRecognition.py           # Whisper speech-to-text
│       ├── comfyui_client.py              # ComfyUI API client
│       └── speech_to_clothing_with_rodin_api.py  # Main pipeline
├── workflows/
│   └── sdxl_inpainting_api.json           # ComfyUI workflow config
├── external/
│   ├── README.md                          # External deps setup guide
│   └── depthai_blazepose/                 # OAK-D BlazePose (clone separately)
├── requirements-core.txt                  # Cross-platform deps
├── requirements-mac.txt                   # Mac-specific deps
├── requirements-pc.txt                    # PC-specific deps
├── venv/                                  # Virtual environment
└── README.md                              # This file
```

## Credits

- **Speech Recognition**: OpenAI Whisper
- **Body Segmentation**: TensorFlow BodyPix
- **Pose Tracking**: MediaPipe + OAK-D BlazePose
- **2D Generation**: Stable Diffusion (via ComfyUI)
- **3D Generation**: Rodin API (Hyperhuman)

## License

[Your license here]
