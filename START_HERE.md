# ⭐ START HERE ⭐

## Quick Setup Checklist

Follow these steps in order:

### ✅ Step 1: Verify Python Version
```bash
python3 --version
```
**Required:** Python 3.11.x

If not installed: https://www.python.org/downloads/

---

### ✅ Step 2: Run Automated Setup (Mac)
```bash
cd ~/Projects/spoken-wardrobe-minimal
./setup_mac.sh
```

**This will:**
- Create virtual environment
- Install all dependencies (~5-10 minutes)
- Apply necessary patches
- Verify installation

**For Windows/PC:** Follow manual steps in README.md

---

### ✅ Step 3: Setup External Dependencies

```bash
cd external
git clone https://github.com/geaxgx/depthai_blazepose.git
cd ..
```

**If that fails:** See `external/README.md` for alternative methods

---

### ✅ Step 4: Get Rodin API Key

1. Go to: https://hyperhuman.deemos.com/
2. Sign up (free tier available)
3. Copy your API key
4. Set it:
   ```bash
   export RODIN_API_KEY="sk-your-key-here"
   ```

**To make it permanent:**
```bash
echo 'export RODIN_API_KEY="sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

---

### ✅ Step 5: Connect Hardware

- **OAK-D Pro Camera** - Plug into USB 3.0 port
- **Microphone** - Built-in or external (USB)

**Verify OAK-D:**
```bash
# Mac
system_profiler SPUSBDataType | grep -A 10 "Movidius"

# Linux
lsusb | grep Movidius
```

---

### ✅ Step 6: Verify Installation

```bash
python verify_setup.py
```

**All items should show ✓**

If any show ✗:
- Check `README.md` troubleshooting section
- Ensure all dependencies installed correctly
- Verify virtual environment is activated: `source venv/bin/activate`

---

### ✅ Step 7: Run the Pipeline!

```bash
python src/modules/speech_to_clothing_with_rodin_api.py
```

**What happens:**
1. Microphone calibration (3s) - stay quiet
2. Body detection - stand in front of camera
3. Speech detection - speak your clothing idea
4. Recording (10s) - describe in detail
5. Transcription - Whisper processes speech
6. A-pose capture (3s countdown) - arms slightly raised
7. Generation - 2D clothing (30-60s) + 3D mesh (60-90s)
8. Results saved to `comfyui_generated_mesh/[timestamp]/`

**See full walkthrough:** `QUICKSTART.md`

---

## Quick Test (Skip 3D Generation)

To test without using Rodin API credits:

```bash
python src/modules/speech_to_clothing_with_rodin_api.py --skip-3d
```

This will generate only the 2D clothing image.

---

## Enable Debug Mode

To see camera feed and debug info:

```bash
python src/modules/speech_to_clothing_with_rodin_api.py --viewer
```

---

## Troubleshooting Quick Fixes

### "Cannot connect to ComfyUI server"
- Check network: `curl http://itp-ml.itp.tsoa.nyu.edu:9199/system_stats`
- Ensure on NYU network or VPN
- Or run your own ComfyUI server

### "Speech not detected"
- Speak louder
- Check microphone permissions (System Preferences → Security & Privacy → Microphone)
- Test microphone: `python -m pyaudio` (should list devices)

### "OAK-D camera not detected"
- Unplug and replug USB cable
- Try different USB port (use USB 3.0)
- Check USB permissions

### "BlazePose import failed"
- Check: `ls external/depthai_blazepose/BlazeposeDepthaiEdge.py`
- If missing: See `external/README.md` for setup
- Try: `git clone https://github.com/gekorob/depthai_blazepose.git` in `external/`

### "RODIN_API_KEY not set"
- Verify: `echo $RODIN_API_KEY`
- Set it: `export RODIN_API_KEY="your_key"`
- Make permanent: Add to `~/.zshrc` or `~/.bashrc`

---

## Documentation Files

- **README.md** - Complete setup guide and troubleshooting
- **QUICKSTART.md** - Step-by-step walkthrough with example output
- **FILE_STRUCTURE.md** - Detailed explanation of all files
- **external/README.md** - External dependencies setup

---

## Getting Help

1. Check `README.md` troubleshooting section
2. Run `python verify_setup.py` to diagnose issues
3. Check that all ✓ in verification output
4. Ensure virtual environment is activated
5. Review error messages carefully

---

## What's Next?

After your first successful run:

1. **View your 3D mesh:**
   - Online: https://gltf-viewer.donmccurdy.com/
   - Blender: File → Import → glTF 2.0
   - Upload: `comfyui_generated_mesh/[timestamp]/clothing_mesh.glb`

2. **Try different prompts:**
   - "elegant silk evening gown in midnight blue"
   - "casual denim jacket with embroidered flowers"
   - "flowing summer dress with tropical print"

3. **Adjust quality settings:**
   - Edit `speech_to_clothing_with_rodin_api.py`
   - Lines 380-394: Stable Diffusion settings
   - Lines 428-434: Rodin API quality settings

4. **Experiment with parameters:**
   - `seed`: Different random variations
   - `steps`: Higher = better quality (slower)
   - `cfg`: Prompt adherence strength
   - `quality_override`: Mesh polygon count

---

## Support

For issues specific to:
- **Whisper**: OpenAI Whisper documentation
- **BodyPix**: TensorFlow BodyPix documentation
- **OAK-D**: Luxonis documentation
- **ComfyUI**: ComfyUI documentation
- **Rodin API**: Hyperhuman support

---

**Good luck! 🚀**
