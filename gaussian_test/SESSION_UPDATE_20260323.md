# Gaussian Splat Try-On Session Update
**Date:** March 23, 2026
**Branch:** `gaussian-exploration`
**Working Directory:** `gaussian_test/` and `src/modules/`

---

## Overview

This session continued work on the Gaussian Splat virtual try-on system. Key accomplishments:
1. Fixed calibration UX (countdown instead of hold)
2. Created clothing extraction utility
3. Integrated Gaussian splats with the main speech-to-clothing pipeline
4. Created new pipeline file that replaces Rodin API with local splat generation

---

## Architecture Clarification

### Existing Pipeline (Rodin API)
```
Speech → Camera → BodyPix Mask → ComfyUI Inpainting → Rodin API → GLB
                                       ↓
                              generated_clothing.png  (full scene)
                                       ↓
                              clothing_mesh.glb       (60-90s cloud)
```

### New Pipeline (Gaussian Splats) - NOW IMPLEMENTED
```
Speech → Camera → BodyPix Mask → ComfyUI Inpainting → Extract → Splat
                                       ↓
                              generated_clothing.png  (full scene)
                                       ↓
                              mask.png applied to extract clothing
                                       ↓
                              clothing_only.png       (transparent bg)
                                       ↓
                              clothing_splat.ply      (~1s local)
```

**Key Insight:** The ComfyUI inpainting outputs the FULL scene (body + clothing). We need to apply the mask to extract ONLY the clothing before generating the Gaussian splat.

---

## New Files Created This Session

### 1. `gaussian_test/extract_clothing.py`
**Purpose:** Extracts clothing from inpainted images using the mask.

**What it does:**
- Takes `generated_clothing.png` (full scene) and `mask.png`
- Applies mask as alpha channel
- Outputs `clothing_only.png` (clothing on transparent background)

**Usage:**
```bash
# Single folder
python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/

# All folders
python3 extract_clothing.py --all

# Preview (shows checkerboard background)
python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/ --preview
```

**Tested:** ✅ Working - generates proper RGBA with 4 channels

---

### 2. `src/modules/speech_to_clothing_with_gaussian.py`
**Purpose:** Full pipeline using Gaussian splats instead of Rodin API.

**Key differences from Rodin version:**
- No API key required
- Local generation (~1s vs 60-90s)
- Outputs PLY instead of GLB
- Includes automatic clothing extraction step

**What it saves:**
```
comfyui_generated_mesh/[timestamp]/
├── original_frame.png      # Camera capture
├── mask.png                # BodyPix segmentation
├── generated_clothing.png  # Full inpainted image (ComfyUI)
├── clothing_only.png       # NEW: Extracted clothing (transparent)
├── clothing_splat.ply      # NEW: Gaussian splat
└── metadata.json           # Includes "3d_generation_method": "gaussian_splat_local"
```

**Usage:**
```bash
python src/modules/speech_to_clothing_with_gaussian.py [--viewer] [--skip-3d]
```

**Status:** ⚠️ Not fully tested (requires OAK-D camera + ComfyUI server)

---

### 3. Updated `gaussian_test/live_tryon_demo.py`
**Changes:**
- SPACE now starts 3-2-1 countdown instead of immediate calibration
- Large centered countdown numbers (3, 2, 1)
- Camera stays live during countdown
- User can position in T-pose during countdown

**Status:** ⚠️ Needs testing with actual camera

---

## Working Implementations

| File | Status | Description |
|------|--------|-------------|
| `generate_splat.py` | ✅ Working | Depth-aware splat generation |
| `splat_preview.py` | ✅ Working | Quality analysis & visualization |
| `gaussian_weight_assigner.py` | ✅ Working | Skinning weight computation |
| `gaussian_animator.py` | ✅ Working | DQS real-time animation |
| `gaussian_tryon_pipeline.py` | ✅ Working | Integration pipeline |
| `extract_clothing.py` | ✅ Working | Mask-based clothing extraction |

---

## Needs Testing

| File | Requires | Test Command |
|------|----------|--------------|
| `live_tryon_demo.py` | Webcam | `python3 live_tryon_demo.py -v` |
| `speech_to_clothing_with_gaussian.py` | OAK-D + ComfyUI | `python src/modules/speech_to_clothing_with_gaussian.py` |

---

## Test Results This Session

### Clothing Extraction Test
```bash
python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/ -o /tmp/test_clothing_only.png
```
**Result:** ✅ Success
- Shape: (648, 1152, 4) - proper RGBA
- Transparent pixels: 652,574 (87.4%)
- Opaque pixels: 93,922 (12.6%) - the clothing

### Splat Generation from Extracted Clothing
```bash
python3 generate_splat.py /tmp/test_clothing_only.png
```
**Result:** ✅ Success
- Generation time: 0.9s
- Splats: 10,000
- Depth enabled: true

### Splat Quality Analysis
```
Center:     (-0.496, 0.234, 0.140)  ← Offset because clothing was on left side of frame
X range:    [-1.000, -0.156]
Z range:    [0.036, 0.250]
Depth:      44/100 ⚠  ← Lower because clothing is relatively flat
Color:      91/100 ✓
Overall:    67/100
```

**Note:** The offset center and lower depth score are expected because:
1. The clothing is not centered in the original camera frame
2. Clothing is flatter than a full 3D scene

---

## File Structure

```
spoken-wardrobe-minimal/
├── src/modules/
│   ├── speech_to_clothing_with_rodin_api.py   # Original (unchanged)
│   └── speech_to_clothing_with_gaussian.py    # NEW: Gaussian version
│
├── gaussian_test/
│   ├── generate_splat.py           # Splat generation
│   ├── splat_preview.py            # Analysis tool
│   ├── extract_clothing.py         # NEW: Clothing extraction
│   ├── gaussian_weight_assigner.py # Skinning weights
│   ├── gaussian_animator.py        # DQS animation
│   ├── gaussian_tryon_pipeline.py  # Integration
│   ├── live_tryon_demo.py          # Live camera demo (updated)
│   └── output/                     # Generated PLY files
│
└── comfyui_generated_mesh/
    └── [timestamp]/
        ├── original_frame.png
        ├── mask.png
        ├── generated_clothing.png
        ├── clothing_only.png       # NEW (if using Gaussian pipeline)
        └── clothing_splat.ply      # NEW (if using Gaussian pipeline)
```

---

## Quick Test Commands

```bash
cd gaussian_test
source ../venv/bin/activate

# 1. Extract clothing from existing ComfyUI output
python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/

# 2. Generate splat from extracted clothing
python3 generate_splat.py ../comfyui_generated_mesh/1765267014/clothing_only.png

# 3. Analyze the splat
python3 splat_preview.py --no-viz

# 4. Test live demo (requires camera)
python3 live_tryon_demo.py -v
```

---

## Continuation Prompt

**CONTINUATION PROMPT FOR CLAUDE:**

I'm continuing work on the Gaussian Splat virtual try-on system. Here's what's been built:

**Architecture:**
The pipeline now has TWO options for 3D generation:
1. `speech_to_clothing_with_rodin_api.py` - Uses Rodin cloud API (60-90s, outputs GLB)
2. `speech_to_clothing_with_gaussian.py` - Uses local Gaussian splats (~1s, outputs PLY)

**Key insight implemented:** The ComfyUI inpainting outputs the full scene (body + clothing). We extract ONLY the clothing by applying the mask, creating `clothing_only.png` with transparent background. This is then fed to the Gaussian splat generator.

**Files created this session (March 23, 2026):**
1. `gaussian_test/extract_clothing.py` - Applies mask to extract clothing ✅ tested
2. `src/modules/speech_to_clothing_with_gaussian.py` - Full pipeline with splats ⚠️ needs testing

**What needs testing:**
1. `live_tryon_demo.py` - Countdown calibration UX (requires webcam)
2. `speech_to_clothing_with_gaussian.py` - Full end-to-end (requires OAK-D + ComfyUI)

**Key files to read:**
- `gaussian_test/SESSION_UPDATE_20260323.md` - This file
- `gaussian_test/extract_clothing.py` - Clothing extraction utility
- `src/modules/speech_to_clothing_with_gaussian.py` - New pipeline

**Potential issues to investigate:**
1. Splat center offset (clothing not centered in frame)
2. Lower depth score for flat clothing vs full scenes
3. Integration between try-on demo and full pipeline

**Next steps:**
1. Test live_tryon_demo.py with webcam
2. Test full Gaussian pipeline if OAK-D + ComfyUI available
3. Consider adding splat centering/normalization step

---

## Dependencies

All dependencies are in the existing venv. No new packages needed.

---

## Performance Comparison

| Step | Rodin API | Gaussian Splat |
|------|-----------|----------------|
| 2D Generation (ComfyUI) | 30-60s | 30-60s (same) |
| Clothing Extraction | N/A | <0.1s |
| 3D Generation | 60-90s (cloud) | ~1s (local) |
| **Total 3D** | **60-90s** | **~1s** |
| Output Format | GLB mesh | PLY splat |
| Requires Internet | Yes (API) | No |
| Requires API Key | Yes | No |

---

## Known Issues

1. **Splat center offset:** Clothing position in frame is preserved. May need normalization for try-on.

2. **Lower depth scores:** Extracted clothing has less depth variation than full scenes. This is expected but may affect visual quality.

3. **Not yet tested end-to-end:** The new `speech_to_clothing_with_gaussian.py` pipeline compiles but hasn't been run with actual hardware.
