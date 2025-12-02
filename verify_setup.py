#!/usr/bin/env python3
"""
Verification script to check if all dependencies are properly installed.
Run this after setup to ensure everything is working.
"""

import sys
from pathlib import Path

def test_import(module_name, display_name=None, show_version=False):
    """Test if a module can be imported."""
    if display_name is None:
        display_name = module_name

    try:
        if show_version:
            mod = __import__(module_name)
            version = getattr(mod, '__version__', 'unknown')
            print(f"✓ {display_name} ({version})")
        else:
            __import__(module_name)
            print(f"✓ {display_name}")
        return True
    except ImportError as e:
        print(f"✗ {display_name} - FAILED")
        print(f"  Error: {e}")
        return False

def test_torch():
    """Test PyTorch with device info."""
    try:
        import torch
        print(f"✓ PyTorch ({torch.__version__})")

        # Check MPS (Mac GPU)
        if torch.backends.mps.is_available():
            print(f"  ✓ MPS (Mac GPU) available")
        elif torch.cuda.is_available():
            print(f"  ✓ CUDA (NVIDIA GPU) available")
            print(f"    GPU: {torch.cuda.get_device_name(0)}")
        else:
            print(f"  ⚠ No GPU detected - will use CPU (slower)")
        return True
    except ImportError as e:
        print(f"✗ PyTorch - FAILED")
        print(f"  Error: {e}")
        return False

def test_tensorflow():
    """Test TensorFlow."""
    try:
        import tensorflow as tf
        print(f"✓ TensorFlow ({tf.__version__})")
        return True
    except ImportError as e:
        print(f"✗ TensorFlow - FAILED")
        print(f"  Error: {e}")
        return False

def test_bodypix():
    """Test BodyPix."""
    try:
        from tf_bodypix.api import download_model, load_model
        print(f"✓ BodyPix")
        return True
    except ImportError as e:
        print(f"✗ BodyPix - FAILED")
        print(f"  Error: {e}")
        return False

def test_blazepose():
    """Test BlazePose."""
    # Add external path
    project_root = Path(__file__).parent
    blazepose_path = project_root / "external" / "depthai_blazepose"
    sys.path.insert(0, str(blazepose_path))

    try:
        from BlazeposeDepthaiEdge import BlazeposeDepthai
        from BlazeposeRenderer import BlazeposeRenderer
        print(f"✓ BlazePose (depthai_blazepose)")
        return True
    except ImportError as e:
        print(f"✗ BlazePose - FAILED")
        print(f"  Error: {e}")
        print(f"  Path checked: {blazepose_path}")
        print(f"  See external/README.md for setup instructions")
        return False

def test_project_modules():
    """Test local project modules."""
    # Add src to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

    results = []
    try:
        from modules.speechRecognition import SpeechRecognizer
        print(f"✓ speechRecognition module")
        results.append(True)
    except ImportError as e:
        print(f"✗ speechRecognition module - FAILED")
        print(f"  Error: {e}")
        results.append(False)

    try:
        from modules.comfyui_client import ComfyUIClient
        print(f"✓ comfyui_client module")
        results.append(True)
    except ImportError as e:
        print(f"✗ comfyui_client module - FAILED")
        print(f"  Error: {e}")
        results.append(False)

    return all(results)

def test_api_key():
    """Check if Rodin API key is set."""
    import os
    api_key = os.environ.get('RODIN_API_KEY')
    if api_key:
        print(f"✓ RODIN_API_KEY is set ({api_key[:8]}...{api_key[-4:]})")
        return True
    else:
        print(f"⚠ RODIN_API_KEY not set")
        print(f"  Set it with: export RODIN_API_KEY='your_key'")
        print(f"  Get key from: https://hyperhuman.deemos.com/")
        return False

def test_workflow_file():
    """Check if workflow file exists."""
    workflow_path = Path(__file__).parent / "workflows" / "sdxl_inpainting_api.json"
    if workflow_path.exists():
        print(f"✓ Workflow file exists: {workflow_path}")
        return True
    else:
        print(f"✗ Workflow file missing: {workflow_path}")
        return False

def main():
    print("="*70)
    print("Spoken Wardrobe - Installation Verification")
    print("="*70)
    print()

    print("Core Python Packages:")
    print("-" * 70)
    test_import("numpy", show_version=True)
    test_import("cv2", "opencv-python")
    test_import("PIL", "pillow")
    test_import("pyaudio")
    test_import("requests", show_version=True)
    test_import("mediapipe", show_version=True)
    print()

    print("AI/ML Frameworks:")
    print("-" * 70)
    test_torch()
    test_tensorflow()
    test_bodypix()
    print()

    print("External Dependencies:")
    print("-" * 70)
    test_blazepose()
    print()

    print("Project Modules:")
    print("-" * 70)
    test_project_modules()
    print()

    print("Configuration:")
    print("-" * 70)
    test_api_key()
    test_workflow_file()
    print()

    print("="*70)
    print("Verification Complete")
    print("="*70)
    print()
    print("If all items show ✓, you're ready to run the pipeline!")
    print()
    print("Next steps:")
    print("  1. Ensure OAK-D Pro camera is connected")
    print("  2. Set RODIN_API_KEY if not already set")
    print("  3. Run: python src/modules/speech_to_clothing_with_rodin_api.py")
    print()

if __name__ == "__main__":
    main()
