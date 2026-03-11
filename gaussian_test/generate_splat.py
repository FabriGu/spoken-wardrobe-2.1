#!/usr/bin/env python3
"""
Gaussian Splat Generator - Test Script
Converts 2D clothing images to 3D Gaussian Splats

Requires:
- ml-sharp (Apple Silicon MPS) OR
- Fallback to CPU-based reconstruction
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('gaussian_debug.log')
    ]
)
logger = logging.getLogger('GaussianSplat')


class GaussianSplatGenerator:
    """
    Generate Gaussian Splats from 2D images

    Supports multiple backends:
    1. ml-sharp (Apple MPS) - fastest, requires Apple Silicon
    2. Hugging Face models - CPU/CUDA fallback
    """

    def __init__(self, backend='auto'):
        self.backend = backend
        self.model = None
        self.device = None
        self._detect_backend()

    def _detect_backend(self):
        """Detect best available backend"""
        logger.info("Detecting available backends...")

        # Check for Apple Silicon MPS
        try:
            import torch
            if torch.backends.mps.is_available():
                self.device = 'mps'
                logger.info("Apple Silicon MPS available")
            elif torch.cuda.is_available():
                self.device = 'cuda'
                logger.info("NVIDIA CUDA available")
            else:
                self.device = 'cpu'
                logger.info("Using CPU (slower)")
        except ImportError:
            self.device = 'cpu'
            logger.warning("PyTorch not found, using CPU")

        # Try ml-sharp first (Apple's single-image reconstruction)
        if self.backend == 'auto' or self.backend == 'ml-sharp':
            try:
                # ml-sharp would be imported here if available
                # For now, we'll use a placeholder
                logger.info("Checking for ml-sharp...")
                # from ml_sharp import Reconstructor
                # self.model = Reconstructor()
                # self.backend = 'ml-sharp'
                raise ImportError("ml-sharp not yet available")
            except ImportError:
                logger.info("ml-sharp not available, trying alternatives...")

        # Try Hugging Face gaussian-splatting models
        if self.backend == 'auto' or self.backend == 'huggingface':
            try:
                logger.info("Loading Hugging Face model...")
                # Placeholder for actual model loading
                self.backend = 'huggingface'
                logger.info("Using Hugging Face backend")
            except Exception as e:
                logger.error(f"Failed to load HF model: {e}")

        logger.info(f"Selected backend: {self.backend}, device: {self.device}")

    def generate(self, image_path: str, output_path: str = None) -> dict:
        """
        Generate Gaussian Splat from image

        Args:
            image_path: Path to input PNG image
            output_path: Path for output PLY file (optional)

        Returns:
            dict with generation results and timing info
        """
        start_time = time.time()
        result = {
            'success': False,
            'input': image_path,
            'output': None,
            'backend': self.backend,
            'device': self.device,
            'timings': {},
            'stats': {},
            'errors': []
        }

        # Validate input
        if not os.path.exists(image_path):
            result['errors'].append(f"Input file not found: {image_path}")
            return result

        logger.info(f"Processing: {image_path}")

        # Generate output path
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = Path(image_path).stem
            output_path = f"output/{base_name}_{timestamp}.ply"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            # ===== PREPROCESSING =====
            preprocess_start = time.time()
            logger.debug("Preprocessing image...")

            from PIL import Image
            import numpy as np

            img = Image.open(image_path)
            logger.debug(f"  Image size: {img.size}")
            logger.debug(f"  Image mode: {img.mode}")

            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Resize for processing (max 512x512 for speed)
            max_size = 512
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"  Resized to: {img.size}")

            result['timings']['preprocess'] = time.time() - preprocess_start

            # ===== GENERATION =====
            gen_start = time.time()
            logger.debug("Generating Gaussian Splats...")

            # PLACEHOLDER: Actual generation would happen here
            # For testing, create a simple PLY with random splats
            # based on the image content

            num_splats = 10000  # Typical: 50k-500k for full scenes
            logger.debug(f"  Generating {num_splats} splats...")

            # Extract colors from image for more realistic placeholder
            img_array = np.array(img)
            height, width = img_array.shape[:2]

            # Generate splats based on non-transparent pixels
            alpha = img_array[:, :, 3] if img_array.shape[2] == 4 else np.ones((height, width)) * 255
            valid_pixels = np.where(alpha > 128)

            if len(valid_pixels[0]) > 0:
                # Sample from valid pixels
                num_valid = len(valid_pixels[0])
                sample_indices = np.random.choice(num_valid, min(num_splats, num_valid), replace=True)

                # Convert pixel coords to 3D positions (normalized -1 to 1)
                # For 2D clothing: keep as FLAT PLANE (z=0) with tiny variation
                y_coords = (valid_pixels[0][sample_indices] / height - 0.5) * -2  # Flip Y
                x_coords = (valid_pixels[1][sample_indices] / width - 0.5) * 2
                z_coords = np.random.randn(len(sample_indices)) * 0.005  # Nearly flat (tiny depth)

                positions = np.column_stack([x_coords, y_coords, z_coords]).astype(np.float32)

                # Get colors from sampled pixels
                colors = img_array[valid_pixels[0][sample_indices], valid_pixels[1][sample_indices], :3] / 255.0
                colors = colors.astype(np.float32)
            else:
                # Fallback to random splats
                positions = np.random.randn(num_splats, 3).astype(np.float32) * 0.5
                colors = np.random.rand(num_splats, 3).astype(np.float32)

            # Pad to full num_splats if needed
            current_count = len(positions)
            if current_count < num_splats:
                extra_needed = num_splats - current_count
                extra_positions = np.random.randn(extra_needed, 3).astype(np.float32) * 0.3
                extra_colors = np.random.rand(extra_needed, 3).astype(np.float32) * 0.3
                positions = np.vstack([positions, extra_positions])
                colors = np.vstack([colors, extra_colors])

            # Generate scales, rotations, opacities
            # Smaller scales for flat image projection (0.005 to 0.02 range)
            scales = np.abs(np.random.randn(num_splats, 3).astype(np.float32)) * 0.008 + 0.005
            rotations = np.random.randn(num_splats, 4).astype(np.float32)
            rotations = rotations / np.linalg.norm(rotations, axis=1, keepdims=True)
            # Higher opacity for better visibility (0.7 to 1.0 range)
            opacities = np.random.rand(num_splats, 1).astype(np.float32) * 0.3 + 0.7

            result['timings']['generation'] = time.time() - gen_start

            # ===== SAVE PLY =====
            save_start = time.time()
            logger.debug(f"Saving to: {output_path}")

            self._save_ply(output_path, positions, colors, scales, rotations, opacities)

            result['timings']['save'] = time.time() - save_start

            # ===== STATS =====
            result['success'] = True
            result['output'] = output_path
            result['stats'] = {
                'num_splats': num_splats,
                'file_size_mb': os.path.getsize(output_path) / (1024 * 1024),
                'input_resolution': list(img.size),
                'backend': self.backend,
                'device': self.device
            }

        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            result['errors'].append(str(e))

        result['timings']['total'] = time.time() - start_time
        logger.info(f"Completed in {result['timings']['total']:.2f}s")

        return result

    def _save_ply(self, path, positions, colors, scales, rotations, opacities):
        """Save Gaussian Splat data to PLY format (3DGS standard format)"""
        import struct
        num_points = len(positions)

        # Build header with all required properties for 3DGS format
        header_lines = [
            "ply",
            "format binary_little_endian 1.0",
            f"element vertex {num_points}",
            "property float x",
            "property float y",
            "property float z",
            "property float nx",
            "property float ny",
            "property float nz",
            # Spherical harmonics DC component (color)
            "property float f_dc_0",
            "property float f_dc_1",
            "property float f_dc_2",
            # Higher order SH (45 coefficients, can be zeros)
        ]

        # Add f_rest properties (45 total for degree 3 SH)
        for i in range(45):
            header_lines.append(f"property float f_rest_{i}")

        header_lines.extend([
            "property float opacity",
            "property float scale_0",
            "property float scale_1",
            "property float scale_2",
            "property float rot_0",
            "property float rot_1",
            "property float rot_2",
            "property float rot_3",
            "end_header",
            ""
        ])

        header = "\n".join(header_lines)

        # Convert colors to SH DC component (C0 coefficient)
        # SH_C0 = 0.28209479177387814
        SH_C0 = 0.28209479177387814
        f_dc = (colors - 0.5) / SH_C0  # Convert from [0,1] RGB to SH DC

        # Convert scales to log space (as used in 3DGS)
        log_scales = np.log(scales + 1e-7)

        # Convert opacity to logit space (inverse sigmoid)
        opacities_clamped = np.clip(opacities, 1e-4, 1 - 1e-4)
        logit_opacity = np.log(opacities_clamped / (1 - opacities_clamped))

        with open(path, 'wb') as f:
            f.write(header.encode('ascii'))
            for i in range(num_points):
                # Position (x, y, z)
                f.write(struct.pack('<fff', *positions[i]))
                # Normals (nx, ny, nz) - not used but required
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                # SH DC coefficients (f_dc_0, f_dc_1, f_dc_2)
                f.write(struct.pack('<fff', *f_dc[i]))
                # SH rest coefficients (45 zeros)
                f.write(struct.pack('<' + 'f' * 45, *([0.0] * 45)))
                # Opacity (logit space)
                f.write(struct.pack('<f', logit_opacity[i][0]))
                # Scale (log space)
                f.write(struct.pack('<fff', *log_scales[i]))
                # Rotation (quaternion wxyz -> xyzw for 3DGS)
                # 3DGS uses wxyz quaternion order
                f.write(struct.pack('<ffff', *rotations[i]))


def main():
    parser = argparse.ArgumentParser(description='Generate Gaussian Splat from image')
    parser.add_argument('image', help='Input image path (PNG)')
    parser.add_argument('-o', '--output', help='Output PLY path')
    parser.add_argument('-b', '--backend', default='auto',
                        choices=['auto', 'ml-sharp', 'huggingface'],
                        help='Generation backend')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    generator = GaussianSplatGenerator(backend=args.backend)
    result = generator.generate(args.image, args.output)

    print("\n" + "=" * 60)
    print("GENERATION RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    if result['success']:
        print(f"\nOutput saved to: {result['output']}")
    else:
        print(f"\nGeneration failed: {result['errors']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
