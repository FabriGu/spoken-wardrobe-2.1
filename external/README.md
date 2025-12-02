# External Dependencies

This directory should contain the `depthai_blazepose` module for OAK-D camera integration.

## Required: depthai_blazepose

The pipeline requires BlazePose integration for OAK-D Pro camera.

### Option 1: Clone from official repository (Recommended)

```bash
cd external
git clone https://github.com/geaxgx/depthai_blazepose.git
```

**Note:** If the above repository doesn't exist or has been moved, try:

### Option 2: Extract from depthai-experiments

```bash
cd external
git clone https://github.com/luxonis/depthai-experiments.git
# Look for gen2-blazepose or similar blazepose implementation
# Extract the necessary BlazeposeDepthaiEdge.py and BlazeposeRenderer.py files
# Place them in: external/depthai_blazepose/
```

### Required Files

After setup, you should have:

```
external/
└── depthai_blazepose/
    ├── BlazeposeDepthaiEdge.py    # Main tracker class
    ├── BlazeposeRenderer.py        # Visualization renderer
    └── [other supporting files]
```

### Verification

Test the setup with:

```bash
python -c "import sys; sys.path.insert(0, 'external/depthai_blazepose'); from BlazeposeDepthaiEdge import BlazeposeDepthai; print('✓ BlazePose import successful')"
```

## Alternative: Skip OAK-D Camera

If you don't have an OAK-D Pro camera, you would need to modify the pipeline to use a regular webcam with MediaPipe instead. This requires code changes in `speech_to_clothing_with_rodin_api.py`.
