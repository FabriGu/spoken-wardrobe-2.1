#!/bin/bash
# Setup script for Spoken Wardrobe Minimal (Mac)

set -e  # Exit on error

echo "======================================================================"
echo "Spoken Wardrobe Minimal - Mac Setup Script"
echo "======================================================================"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
if [[ "$PYTHON_VERSION" != "3.11"* ]]; then
    echo "❌ ERROR: Python 3.11.x is required, but found: $PYTHON_VERSION"
    echo "   Download from: https://www.python.org/downloads/"
    exit 1
fi
echo "✓ Python 3.11 detected"

# Check for Homebrew and install portaudio
echo ""
echo "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "❌ ERROR: Homebrew is not installed"
    echo ""
    echo "Homebrew is required to install portaudio (needed for PyAudio)."
    echo "Install Homebrew from: https://brew.sh/"
    echo ""
    echo "Run this command:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    exit 1
fi
echo "✓ Homebrew detected"

echo ""
echo "Installing portaudio (required for PyAudio)..."
if brew list portaudio &>/dev/null; then
    echo "✓ portaudio already installed"
else
    echo "Installing portaudio via Homebrew..."
    brew install portaudio
    echo "✓ portaudio installed"
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  venv already exists. Remove it? (y/n)"
    read -r response
    if [ "$response" = "y" ]; then
        rm -rf venv
    else
        echo "Keeping existing venv..."
    fi
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo "✓ pip upgraded"

# Install core dependencies
echo ""
echo "Installing core dependencies..."
echo "(This may take 2-3 minutes)"
pip install -r requirements-core.txt
echo "✓ Core dependencies installed"

# Install Mac-specific dependencies
echo ""
echo "Installing Mac-specific dependencies..."
echo "(This may take 5-10 minutes - downloading PyTorch, TensorFlow, etc.)"
pip install -r requirements-mac.txt
echo "✓ Mac dependencies installed"

# Apply tfjs patch
echo ""
echo "Applying tfjs-graph-converter patch..."
TFJS_UTIL="venv/lib/python3.11/site-packages/tfjs_graph_converter/util.py"
if [ -f "$TFJS_UTIL" ]; then
    # Replace all instances of np.bool with np.bool_ (more robust pattern)
    sed -i '' 's/np\.bool/np.bool_/g' "$TFJS_UTIL"
    echo "✓ Patch applied"
    # Verify the patch worked
    if grep -q "np\.bool[^_]" "$TFJS_UTIL"; then
        echo "⚠️  Warning: Patch may not have applied correctly"
        echo "   Please check the file manually"
    fi
else
    echo "⚠️  Warning: Could not find $TFJS_UTIL"
    echo "   You may need to apply the patch manually"
fi

# Check for external dependencies
echo ""
echo "Checking external dependencies..."
if [ ! -d "external/depthai_blazepose" ]; then
    echo "⚠️  depthai_blazepose not found"
    echo ""
    echo "Would you like to clone it now? (y/n)"
    echo "(Requires git access to geaxgx/depthai_blazepose)"
    read -r response
    if [ "$response" = "y" ]; then
        cd external
        echo "Attempting to clone depthai_blazepose..."
        if git clone https://github.com/geaxgx/depthai_blazepose.git 2>/dev/null; then
            echo "✓ depthai_blazepose cloned"
        else
            echo "❌ Clone failed. See external/README.md for manual setup instructions."
        fi
        cd ..
    else
        echo "Skipping. See external/README.md for manual setup instructions."
    fi
else
    echo "✓ depthai_blazepose found"
fi

# Verify installation
echo ""
echo "======================================================================"
echo "Verifying installation..."
echo "======================================================================"

python -c "import torch; print(f'✓ PyTorch {torch.__version__}')" 2>/dev/null || echo "❌ PyTorch import failed"
python -c "import torch; print(f'✓ MPS available: {torch.backends.mps.is_available()}')" 2>/dev/null || echo "⚠️  MPS check failed"
python -c "import tensorflow as tf; print(f'✓ TensorFlow {tf.__version__}')" 2>/dev/null || echo "❌ TensorFlow import failed"
python -c "import mediapipe; print('✓ MediaPipe OK')" 2>/dev/null || echo "❌ MediaPipe import failed"
python -c "import cv2; print('✓ OpenCV OK')" 2>/dev/null || echo "❌ OpenCV import failed"
python -c "from tf_bodypix.api import load_model; print('✓ BodyPix OK')" 2>/dev/null || echo "❌ BodyPix import failed"

echo ""
echo "======================================================================"
echo "Setup Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Get Rodin API key from: https://hyperhuman.deemos.com/"
echo "   Then set it:"
echo "   export RODIN_API_KEY=\"your_api_key_here\""
echo ""
echo "2. Ensure OAK-D Pro camera is connected"
echo ""
echo "3. Run the pipeline:"
echo "   python src/modules/speech_to_clothing_with_rodin_api.py"
echo ""
echo "For help, see README.md"
echo ""
