# Quick Start Guide

## Absolute Fastest Setup (Mac)

```bash
cd ~/Projects/spoken-wardrobe-minimal

# Run automated setup
./setup_mac.sh

# Set API key
export RODIN_API_KEY="your_key_from_hyperhuman.deemos.com"

# Run pipeline
python src/modules/speech_to_clothing_with_rodin_api.py
```

## What Happens When You Run It

### 1. Calibration (3 seconds)
```
🎤 Calibrating microphone (3s)...
   Please stay quiet...
```
**What to do:** Stay silent, let it measure ambient noise.

### 2. Body Detection
```
👤 Waiting for body detection...
   Stand in front of OAK-D camera...
```
**What to do:** Stand in view of the OAK-D Pro camera.

### 3. Speech Detection
```
🎤 Listening for speech...
   Say: 'Describe your dream dress using your imagination'
   Speak when volume > 125
```
**What to do:** Speak loudly enough to trigger recording (volume shown in terminal).

### 4. Recording (10 seconds)
```
🎙️  Recording for 10.0 seconds...
```
**What to do:** Describe your clothing idea (e.g., "a beautiful red dress with golden patterns").

### 5. Transcription
```
📝 Transcribing with Whisper...
======================================================================
✅ Transcription: 'a beautiful red dress with golden patterns'
======================================================================
```
**What to do:** Wait for Whisper to process your speech.

### 6. A-Pose Capture (3 second countdown)
```
🤸 Please stand in A-pose...
   3 second countdown starting...
   3...
   2...
   1...
```
**What to do:** Stand in A-pose (arms slightly raised, legs apart).

### 7. BodyPix Segmentation
```
🎭 Running BodyPix segmentation...
✓ BodyPix complete in 2.34s
```
**What to do:** Wait (automatic).

### 8. 2D Clothing Generation (30-60 seconds)
```
🎨 Generating 2D clothing with ComfyUI...
   Prompt: 'a beautiful red dress with golden patterns'
⏳ Generating (this may take 30-60s on first run)...
✓ Generation complete in 45.2s
```
**What to do:** Wait for Stable Diffusion to generate clothing.

### 9. 3D Mesh Generation (60-90 seconds)
```
🎲 Generating 3D mesh with Rodin API (Direct)...
   Input: /tmp/clothing_2d_1699999999.png
   Tier: Regular
   This may take 60-90 seconds...
   ⏳ Waiting for generation...
   Job abcd1234: Processing
   Job abcd1234: Done
✓ Generation complete in 78.3s
```
**What to do:** Wait for Rodin to create 3D mesh.

### 10. Save Results
```
💾 Saving to: comfyui_generated_mesh/1699999999
  ✓ original_frame.png
  ✓ mask.png
  ✓ generated_clothing.png
  ✓ clothing_mesh.glb (1234.5 KB)
  ✓ metadata.json

✅ All files saved to: comfyui_generated_mesh/1699999999
```

**Done!** Check the output folder for your results.

## View the 3D Mesh

You can view the GLB file with:
- **Online:** https://gltf-viewer.donmccurdy.com/
- **Blender:** Import > glTF 2.0 (.glb/.gltf)
- **Three.js:** Use the viewer from the original repo

## Common Issues

### "Cannot connect to ComfyUI server"
```bash
# Test connection
curl http://itp-ml.itp.tsoa.nyu.edu:9199/system_stats
```
- Make sure you're on NYU network or VPN
- Or run your own ComfyUI server and change line 947 in the script

### "Speech not detected"
- Speak louder
- Check microphone permissions (System Preferences > Security & Privacy)
- Lower threshold in script (line 194: change `2.5` to `2.0`)

### "OAK-D camera not detected"
- Check USB connection (use USB 3.0 port)
- Try unplugging and replugging
- Run `python tests/test_oakd_blazepose_basic.py` to test camera

### "RODIN_API_KEY not set"
```bash
export RODIN_API_KEY="sk-xxx-yyy-zzz"
# Make permanent:
echo 'export RODIN_API_KEY="sk-xxx-yyy-zzz"' >> ~/.zshrc
```

## Tips for Best Results

### Speech Input
- Speak clearly and describe:
  - Color: "red", "blue", "golden"
  - Material: "silk", "leather", "denim"
  - Style: "elegant", "casual", "haute couture"
  - Patterns: "floral", "striped", "polka dots"

Example: "an elegant silk dress in deep blue with golden floral embroidery"

### Body Pose
- **A-pose works best** (arms slightly raised 30-45°)
- Stand 1-2 meters from camera
- Good lighting (avoid backlighting)
- Wear fitted clothing for better segmentation

### 2D Generation Quality
- Edit line 380-394 to adjust Stable Diffusion settings:
  - `steps`: Higher = better quality but slower (20-50)
  - `cfg`: Higher = follows prompt more strictly (7-12)
  - `seed`: Change for different results

### 3D Mesh Quality
- Edit line 428-434 to adjust Rodin settings:
  - `quality_override`: "5000" (low-poly) to "10000" (high-poly)
  - Higher quality = longer generation time + more API credits

## Example Session Log

```
======================================================================
Speech-to-Clothing Pipeline with Rodin API (Direct)
======================================================================
✓ Pipeline initialized
✓ 3D mesh generation enabled (Rodin API Direct)
✓ API key configured: sk-1234a...b5cd
======================================================================

🎤 Calibrating microphone (3.0s)...
   Please stay quiet...
✓ Calibration complete!
   Ambient noise: 45
   Speech threshold: 112

📷 Initializing OAK-D Pro camera...
✓ OAK-D Pro initialized

👤 Waiting for body detection...
   Stand in front of OAK-D camera...
✓ Body detected!

🎤 Listening for speech...
   Say: 'Describe your dream dress using your imagination'
   Speak when volume > 112

✓ Speech detected! (volume: 324)

🎙️  Recording for 10.0 seconds...
✓ Recording complete (624 chunks)

📝 Transcribing with Whisper...
======================================================================
✅ Transcription: 'a beautiful flowing red silk gown with golden embroidery'
======================================================================

🤸 Please stand in A-pose...
   3 second countdown starting...
   3...
   2...
   1...

📸 Frame captured!
🎭 Running BodyPix segmentation...
✓ BodyPix complete in 2.15s

🎨 Generating 2D clothing with ComfyUI...
   Prompt: 'a beautiful flowing red silk gown with golden embroidery'
✓ ComfyUI server is reachable
✓ Uploaded: input_abc123.png → input_abc123.png
✓ Generation complete in 42.3s

🎲 Generating 3D mesh with Rodin API (Direct)...
   ✓ Task submitted: task-xyz789
   ⏳ Waiting for generation...
   Job xyz78901: Processing
   Job xyz78901: Processing
   Job xyz78901: Done
✓ Generation complete in 73.2s
   📥 Downloading mesh...
   Downloading: mesh.glb
   ✓ Saved: /tmp/rodin_output_1699999999/mesh.glb (1432.8 KB)
✓ Mesh downloaded: /tmp/rodin_output_1699999999/mesh.glb

💾 Saving to: comfyui_generated_mesh/1699999999
  ✓ original_frame.png
  ✓ mask.png
  ✓ generated_clothing.png
  ✓ clothing_mesh.glb (1432.8 KB)
  ✓ metadata.json

✅ All files saved to: comfyui_generated_mesh/1699999999

✅ Pipeline complete! Check output folder for results.
   Location: comfyui_generated_mesh/1699999999
```

**Total time:** ~2-3 minutes

## Next Steps

- View your 3D mesh in Blender or online viewer
- Try different prompts and see how results vary
- Adjust quality settings for better results
- Integrate with real-time AR overlay (see original repo)
