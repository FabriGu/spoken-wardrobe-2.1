# Gaussian Splat Test Environment - Context & Resume Document

**Last Updated:** March 5, 2026
**Branch:** `lookbook-era`
**Working Directory:** `/Users/fabrizioguccione/Projects/spoken-wardrobe-minimal/gaussian_test/`

---

## Resume Prompt

Copy and paste this to resume work:

```
I'm continuing work on the Gaussian Splat test environment for the Spoken Wardrobe project.

Current state:
- Basic Gaussian Splat viewer is WORKING (fixed viewer.render() bug)
- Can load .ply and .splat files and render them
- Flat 2D→3D projection works (clothing appears as flat splat plane)
- Downloaded sample splat file (test_sample.splat) renders correctly
- WebSocket debug server running on port 8090

What's next according to DEVELOPMENT_PLAN.md:
- Phase 1: Integrate depth estimation (Apple Depth Pro or Depth Anything V2)
- Replace flat Z=0 projection with real depth-based 3D

Key files:
- gaussian_test/generate_splat.py - Python generator (needs depth integration)
- gaussian_test/static/js/app.js - Three.js viewer with GaussianSplats3D
- gaussian_test/server.py - aiohttp WebSocket server
- gaussian_test/DEVELOPMENT_PLAN.md - Full 6-phase roadmap

Research completed: 5 agents researched GaussianSplats3D API, 3DGS animation, virtual try-on, depth estimation, and deformation methods. Key finding: Use Spark library (not deprecated GaussianSplats3D), SMPL-X body model, and Linear Blend Skinning.

Please read gaussian_test/DEVELOPMENT_PLAN.md and gaussian_test/CONTEXT_RESUME.md for full context, then proceed with Phase 1.
```

---

## Project Overview

### Goal
Replace the Rodin API (60-90s cloud processing) with local Gaussian Splat generation for real-time clothing visualization in the Spoken Wardrobe pipeline.

### Why Gaussian Splats?
- **Speed:** <5s local vs 60-90s API
- **Animation:** Native support for pose-driven deformation via skinning
- **Cost:** No API credits
- **Quality:** Photorealistic rendering at 60+ FPS

---

## What Was Accomplished

### Session 1: Initial Setup & Bug Fixes

1. **Created test environment structure:**
   ```
   gaussian_test/
   ├── generate_splat.py      # Python Gaussian generator
   ├── server.py              # aiohttp WebSocket server
   ├── requirements.txt       # Python dependencies
   ├── eslint.config.js       # Linting config
   ├── package.json           # Node dependencies
   ├── static/
   │   ├── index.html         # Debug viewer UI
   │   ├── minimal_test.html  # Isolated library test
   │   ├── css/debug.css      # Dark theme styles
   │   └── js/app.js          # Three.js + GaussianSplats3D viewer
   ├── test_images/
   │   ├── sample.png         # Test image
   │   └── clothing_test.png  # Real clothing from pipeline
   └── output/
       ├── *.ply              # Generated splat files
       └── test_sample.splat  # Downloaded reference splat (31MB)
   ```

2. **Fixed critical rendering bug:**
   - **Problem:** Splats loaded successfully but nothing rendered (0 triangles)
   - **Root Cause:** `viewer.render()` was never called
   - **Fix:** Added `this.splatViewer.render()` in animate loop (app.js:398)
   - When `selfDrivenMode: false`, you MUST call both `update()` AND `render()`

3. **Fixed PLY generation issues:**
   - Changed from random 3D blob (z = random) to flat plane (z ≈ 0)
   - Reduced splat scales from 0.02-0.08 to 0.005-0.02
   - Added proper 3DGS PLY format with spherical harmonics

4. **Upgraded library:**
   - Updated from GaussianSplats3D 0.4.6 → 0.4.7

5. **Downloaded reference splat:**
   - `output/test_sample.splat` (31MB, ~1M splats)
   - From HuggingFace: cakewalk/splat-data
   - Confirms viewer works with real 3DGS data

### Session 2: Research Phase

Deployed 5 research agents covering:

1. **GaussianSplats3D API** → Found library is DEPRECATED, migrate to Spark
2. **3DGS Animation** → Canonical space + deformation field is standard
3. **Virtual Try-On** → GS-VTON, Gaussian Garments have code available
4. **Depth Estimation** → Apple Depth Pro (0.3s) or Depth Anything V2 best
5. **Deformation Methods** → LBS/DQS skinning with SMPL-X body model

---

## Current File States

### generate_splat.py (Key sections)
```python
# Line 182-184: Currently flat projection
y_coords = (valid_pixels[0][sample_indices] / height - 0.5) * -2
x_coords = (valid_pixels[1][sample_indices] / width - 0.5) * 2
z_coords = np.random.randn(len(sample_indices)) * 0.005  # Nearly flat

# Line 207: Current scale range
scales = np.abs(np.random.randn(num_splats, 3).astype(np.float32)) * 0.008 + 0.005
```

### app.js (Key sections)
```javascript
// Line 221-229: Viewer configuration
this.splatViewer = new GaussianSplats3D.Viewer({
    threeScene: this.scene,
    renderer: this.renderer,
    camera: this.camera,
    useBuiltInControls: false,
    selfDrivenMode: false,  // We control update/render
    dynamicScene: false,
    sharedMemoryForWorkers: false
});

// Line 391-404: Animation loop (FIXED)
if (this.splatViewer) {
    try {
        this.splatViewer.update();
        this.splatViewer.render();  // CRITICAL: Must call render()
    } catch (e) {
        console.error('Splat viewer error:', e);
    }
} else {
    this.renderer.render(this.scene, this.camera);
}
```

### server.py
- Port: 8090
- Endpoints: `/ws` (WebSocket), `/api/status`, `/api/generate`, `/output/*`
- Lists both .ply and .splat files

---

## Research Findings Summary

### Recommended Architecture
```
2D Clothing Image (from ComfyUI/Stable Diffusion)
    ↓
Depth Estimation (Apple Depth Pro - 0.3s)
    ↓
Point Cloud (Open3D or built-in scripts)
    ↓
Gaussian Splat Initialization
    ↓
SMPL-X Body Model (fitted from BlazePose landmarks)
    ↓
Linear Blend Skinning (GPU shader)
    ↓
Real-time Rendering (Spark library - 60+ FPS)
```

### Key Libraries to Use
| Purpose | Library | Status |
|---------|---------|--------|
| 3DGS Rendering | **Spark** (not GaussianSplats3D) | Active development |
| Depth Estimation | Apple Depth Pro | Production ready |
| Body Model | SMPL-X | Standard |
| Body Tracking | BlazePose (existing) | Already integrated |

### Performance Benchmarks (from research)
| Method | Training | Rendering | Platform |
|--------|----------|-----------|----------|
| 3DGS-Avatar | 30 min | 50+ FPS | GPU |
| HUGS (Apple) | 30 min | 60 FPS | GPU |
| SplattingAvatar | - | 300+ FPS | Desktop |
| TaoAvatar | - | 90 FPS | Vision Pro |

---

## Development Plan (6 Phases)

See `DEVELOPMENT_PLAN.md` for full details.

| Phase | Description | Duration | Status |
|-------|-------------|----------|--------|
| 1 | Depth-based 3D generation | 1-2 days | **NEXT** |
| 2 | Migrate to Spark library | 1 day | Pending |
| 3 | SMPL-X body model integration | 2-3 days | Pending |
| 4 | Linear Blend Skinning animation | 2-3 days | Pending |
| 5 | Pipeline integration | 1-2 days | Pending |
| 6 | Advanced features (optional) | 1-2 weeks | Pending |

**Total estimated: 7-11 days**

---

## How to Run

### Start the server:
```bash
cd /Users/fabrizioguccione/Projects/spoken-wardrobe-minimal/gaussian_test
source ../venv/bin/activate
python3 server.py --port 8090
```

### Open viewer:
```
http://localhost:8090
```

### Test with clothing:
1. Click "Refresh Images"
2. Select "clothing_test.png"
3. Click "Generate Splat"
4. Load the generated .ply file

### Test with reference splat:
1. Click "Refresh Outputs"
2. Select "test_sample.splat"
3. Click "Load Splat"
4. Should see a 3D scene (real 3DGS capture)

---

## Key Decisions Made

1. **Flat projection first** → Get rendering working before depth
2. **GaussianSplats3D for prototype** → Will migrate to Spark later
3. **10,000 splats default** → Balance of quality/performance
4. **PLY format** → Standard 3DGS format with spherical harmonics

## Decisions Pending

1. **Physics simulation?** (Realistic cloth dynamics, adds complexity)
2. **Target platform?** (Desktop vs mobile affects splat count)
3. **Real-time generation?** (Or pre-generate and cache?)
4. **Keep Rodin fallback?** (For reliability during development)

---

## Known Issues

1. **FPS drops with large splats** - 1M+ splats from test_sample.splat causes low FPS
2. **No depth yet** - Clothing renders as flat plane, not 3D shape
3. **GaussianSplats3D deprecated** - Should migrate to Spark
4. **No body tracking** - Splats don't follow BlazePose yet

---

## GitHub Repositories for Reference

### Essential:
- https://github.com/apple/ml-depth-pro (Depth estimation)
- https://github.com/sparkjsdev/spark (3DGS viewer replacement)
- https://github.com/vchoutas/smplx (Body model)

### Virtual Try-On:
- https://github.com/yukangcao/GS-VTON
- https://github.com/eth-ait/Gaussian-Garments

### Avatar Animation:
- https://github.com/mikeqzy/3dgs-avatar-release
- https://github.com/kv2000/ASH

### Curated List:
- https://github.com/MrNeRF/awesome-3D-gaussian-splatting

---

## Next Immediate Steps

### Phase 1, Task 1: Install Depth Estimation

```bash
cd /Users/fabrizioguccione/Projects/spoken-wardrobe-minimal/gaussian_test
source ../venv/bin/activate

# Option A: Apple Depth Pro
pip install git+https://github.com/apple/ml-depth-pro.git

# Option B: Depth Anything V2
git clone https://github.com/DepthAnything/Depth-Anything-V2.git
cd Depth-Anything-V2
pip install -r requirements.txt
```

### Phase 1, Task 2: Modify generate_splat.py

Replace flat Z projection (line ~182) with:
```python
# Load depth model
from depth_pro import DepthPro
depth_model = DepthPro.load()

# In generate() method:
depth_map, focal_length = depth_model.infer(image_path)
z_coords = depth_map[valid_pixels] * depth_scale  # Real depth!
```

### Phase 1, Task 3: Test and tune
- Generate splat from clothing_test.png
- Verify 3D depth appears correct
- Adjust depth_scale parameter

---

## Session Notes

- ESLint configured and passing
- Python syntax validation passing
- Server restarts cleanly (kills old process first)
- WebSocket reconnection works (3s retry)
- Both .ply and .splat formats supported

---

## Contact/Credits

Research agents found papers from:
- Apple Machine Learning Research (HUGS, Depth Pro)
- ETH Zurich (Gaussian Garments)
- CVPR 2024 (3DGS-Avatar, SplattingAvatar)
- NeurIPS 2024 (HumanSplat)
- World Labs (Spark library)
