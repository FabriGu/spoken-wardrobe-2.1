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
import torch
from transformers import pipeline

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

    def __init__(self, backend='auto', use_depth=True):
        self.backend = backend
        self.model = None
        self.device = None
        self.depth_pipe = None
        self.use_depth = use_depth
        self._detect_backend()
        if use_depth:
            self._init_depth_model()

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

    def _init_depth_model(self):
        """Initialize Depth Anything V2 model for depth estimation"""
        logger.info("Loading Depth Anything V2 model...")
        try:
            # Use MPS for Apple Silicon, CUDA for NVIDIA, CPU as fallback
            if self.device == 'mps':
                device_id = 'mps'
            elif self.device == 'cuda':
                device_id = 0
            else:
                device_id = -1  # CPU

            self.depth_pipe = pipeline(
                task="depth-estimation",
                model="depth-anything/Depth-Anything-V2-Small-hf",
                device=device_id
            )
            logger.info("Depth Anything V2 loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load depth model: {e}")
            logger.warning("Falling back to flat projection")
            self.depth_pipe = None
            self.use_depth = False

    def generate(self, image_path: str, output_path: str = None, depth_scale: float = 0.05,
                 center_content: bool = True, smooth_depth: bool = True,
                 remove_outliers: bool = True) -> dict:
        """
        Generate Gaussian Splat from image

        Args:
            image_path: Path to input PNG image
            output_path: Path for output PLY file (optional)
            depth_scale: Scale factor for depth values (default: 0.5)
            center_content: Center the content before processing (default: True)
            smooth_depth: Apply smoothing to depth map (default: True)
            remove_outliers: Remove outlier splats (default: True)

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
            # Use gaussian_test/output directory
            script_dir = Path(__file__).parent
            output_path = str(script_dir / f"output/{base_name}_{timestamp}.ply")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            # ===== PREPROCESSING =====
            preprocess_start = time.time()
            logger.debug("Preprocessing image...")

            from PIL import Image
            import numpy as np
            from scipy import ndimage

            img = Image.open(image_path)
            logger.debug(f"  Image size: {img.size}")
            logger.debug(f"  Image mode: {img.mode}")

            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            img_array = np.array(img)

            # ===== CENTER CONTENT =====
            if center_content:
                logger.debug("  Centering content...")
                img_array, bbox = self._center_content(img_array)
                logger.debug(f"  Original bbox: {bbox}")
                img = Image.fromarray(img_array)

            # Resize for processing (max 512x512 for speed)
            max_size = 512
            orig_size = img.size
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                img_array = np.array(img)
                logger.debug(f"  Resized to: {img.size}")

            result['timings']['preprocess'] = time.time() - preprocess_start

            # ===== DEPTH ESTIMATION =====
            depth_start = time.time()
            depth_map = None

            if self.use_depth and self.depth_pipe is not None:
                logger.debug("Running depth estimation...")
                try:
                    # For transparent images, fill background before depth estimation
                    # This prevents Depth Anything from getting confused by transparency
                    img_for_depth = self._prepare_for_depth(img_array)
                    depth_img = Image.fromarray(img_for_depth)

                    depth_result = self.depth_pipe(depth_img)
                    depth_map = np.array(depth_result['depth'])

                    # Apply smoothing to reduce artificial layering
                    if smooth_depth:
                        depth_map = ndimage.gaussian_filter(depth_map.astype(np.float32), sigma=2.0)

                    # Normalize depth to 0-1 range
                    depth_min, depth_max = depth_map.min(), depth_map.max()
                    if depth_max > depth_min:
                        depth_map = (depth_map - depth_min) / (depth_max - depth_min)
                    else:
                        depth_map = np.zeros_like(depth_map)

                    # Invert so closer objects have smaller z (camera convention)
                    depth_map = 1.0 - depth_map
                    logger.debug(f"  Depth map shape: {depth_map.shape}")
                    logger.debug(f"  Depth range: {depth_map.min():.3f} to {depth_map.max():.3f}")
                except Exception as e:
                    logger.warning(f"Depth estimation failed: {e}")
                    depth_map = None

            result['timings']['depth_estimation'] = time.time() - depth_start

            # ===== GENERATION =====
            gen_start = time.time()
            logger.debug("Generating Gaussian Splats...")

            num_splats = 10000  # Typical: 50k-500k for full scenes
            logger.debug(f"  Generating {num_splats} splats...")

            # Extract colors from image
            height, width = img_array.shape[:2]

            # Generate splats based on non-transparent pixels
            alpha = img_array[:, :, 3] if img_array.shape[2] == 4 else np.ones((height, width)) * 255
            valid_pixels = np.where(alpha > 128)

            if len(valid_pixels[0]) > 0:
                # Sample from valid pixels
                num_valid = len(valid_pixels[0])
                sample_indices = np.random.choice(num_valid, min(num_splats, num_valid), replace=True)

                # Find content bounding box for proper centering
                y_min, y_max = valid_pixels[0].min(), valid_pixels[0].max()
                x_min, x_max = valid_pixels[1].min(), valid_pixels[1].max()
                content_center_y = (y_min + y_max) / 2
                content_center_x = (x_min + x_max) / 2
                content_height = y_max - y_min
                content_width = x_max - x_min

                # Convert pixel coords to 3D positions (centered on content, not frame)
                # Normalize to [-1, 1] based on content size
                # Image coords: Y increases downward (top=0)
                # 3D coords: Y increases upward (top=positive)
                # So we DON'T flip Y - keep image orientation
                scale_factor = max(content_height, content_width) / 2
                y_coords = (valid_pixels[0][sample_indices] - content_center_y) / scale_factor
                x_coords = (valid_pixels[1][sample_indices] - content_center_x) / scale_factor

                # Use real depth if available, otherwise flat projection
                if depth_map is not None:
                    # Sample depth values at the sampled pixel locations
                    sampled_depths = depth_map[
                        valid_pixels[0][sample_indices],
                        valid_pixels[1][sample_indices]
                    ]
                    # Center depth around 0, scale to reasonable range
                    z_coords = (sampled_depths - 0.5) * depth_scale
                    logger.debug(f"  Using real depth: z range [{z_coords.min():.3f}, {z_coords.max():.3f}]")
                else:
                    # Fallback: nearly flat with tiny variation
                    z_coords = np.random.randn(len(sample_indices)) * 0.005
                    logger.debug("  Using flat projection (no depth)")

                positions = np.column_stack([x_coords, y_coords, z_coords]).astype(np.float32)

                # Get colors from sampled pixels
                colors = img_array[valid_pixels[0][sample_indices], valid_pixels[1][sample_indices], :3] / 255.0
                colors = colors.astype(np.float32)

                # ===== OUTLIER REMOVAL =====
                if remove_outliers:
                    positions, colors = self._remove_outliers(positions, colors)
                    logger.debug(f"  After outlier removal: {len(positions)} splats")

            else:
                # Fallback to random splats
                positions = np.random.randn(num_splats, 3).astype(np.float32) * 0.5
                colors = np.random.rand(num_splats, 3).astype(np.float32)

            # Pad to full num_splats if needed (with nearby positions, not random)
            current_count = len(positions)
            if current_count < num_splats:
                extra_needed = num_splats - current_count
                # Duplicate existing points with small jitter instead of random
                dup_indices = np.random.choice(current_count, extra_needed, replace=True)
                extra_positions = positions[dup_indices] + np.random.randn(extra_needed, 3).astype(np.float32) * 0.01
                extra_colors = colors[dup_indices] * (0.9 + np.random.rand(extra_needed, 1).astype(np.float32) * 0.2)
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
                'device': self.device,
                'depth_enabled': self.use_depth and depth_map is not None
            }

        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            result['errors'].append(str(e))

        result['timings']['total'] = time.time() - start_time
        logger.info(f"Completed in {result['timings']['total']:.2f}s")

        return result

    def _center_content(self, img_array: np.ndarray) -> tuple:
        """
        Center the non-transparent content in the image.

        Args:
            img_array: RGBA image array

        Returns:
            Tuple of (centered_array, original_bbox)
        """
        alpha = img_array[:, :, 3]
        coords = np.where(alpha > 128)

        if len(coords[0]) == 0:
            return img_array, None

        # Find bounding box
        y_min, y_max = coords[0].min(), coords[0].max()
        x_min, x_max = coords[1].min(), coords[1].max()
        bbox = (x_min, y_min, x_max, y_max)

        # Calculate content center and image center
        content_center_y = (y_min + y_max) // 2
        content_center_x = (x_min + x_max) // 2
        img_center_y = img_array.shape[0] // 2
        img_center_x = img_array.shape[1] // 2

        # Calculate shift needed
        shift_y = img_center_y - content_center_y
        shift_x = img_center_x - content_center_x

        # Create centered image
        centered = np.zeros_like(img_array)

        # Calculate source and destination regions
        src_y_start = max(0, -shift_y)
        src_y_end = min(img_array.shape[0], img_array.shape[0] - shift_y)
        src_x_start = max(0, -shift_x)
        src_x_end = min(img_array.shape[1], img_array.shape[1] - shift_x)

        dst_y_start = max(0, shift_y)
        dst_y_end = min(img_array.shape[0], img_array.shape[0] + shift_y)
        dst_x_start = max(0, shift_x)
        dst_x_end = min(img_array.shape[1], img_array.shape[1] + shift_x)

        # Copy content to centered position
        centered[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = \
            img_array[src_y_start:src_y_end, src_x_start:src_x_end]

        return centered, bbox

    def _prepare_for_depth(self, img_array: np.ndarray) -> np.ndarray:
        """
        Prepare image for depth estimation by filling transparent areas.

        Depth Anything gets confused by transparency. We fill transparent
        areas with a neutral gray to help it focus on the actual content.

        Args:
            img_array: RGBA image array

        Returns:
            RGB image array with transparency filled
        """
        # Create RGB output
        rgb = img_array[:, :, :3].copy()
        alpha = img_array[:, :, 3]

        # Fill transparent areas with neutral gray (128)
        # This helps Depth Anything focus on the actual clothing
        mask = alpha < 128
        rgb[mask] = [128, 128, 128]

        return rgb

    def _remove_outliers(self, positions: np.ndarray, colors: np.ndarray,
                         std_threshold: float = 2.5) -> tuple:
        """
        Remove outlier splats that are too far from the main cluster.

        Uses simple statistical outlier detection based on position.

        Args:
            positions: Nx3 array of positions
            colors: Nx3 array of colors
            std_threshold: Number of standard deviations for outlier detection

        Returns:
            Tuple of (filtered_positions, filtered_colors)
        """
        if len(positions) < 100:
            return positions, colors

        # Calculate center and std for each dimension
        center = positions.mean(axis=0)
        std = positions.std(axis=0)

        # Find points within threshold
        distances = np.abs(positions - center) / (std + 1e-6)
        max_distances = distances.max(axis=1)
        inlier_mask = max_distances < std_threshold

        # Keep at least 50% of points
        if inlier_mask.sum() < len(positions) * 0.5:
            # Sort by distance and keep top 50%
            sorted_indices = np.argsort(max_distances)
            keep_count = len(positions) // 2
            inlier_mask = np.zeros(len(positions), dtype=bool)
            inlier_mask[sorted_indices[:keep_count]] = True

        return positions[inlier_mask], colors[inlier_mask]

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
    parser.add_argument('--no-depth', action='store_true',
                        help='Disable depth estimation (flat projection)')
    parser.add_argument('--depth-scale', type=float, default=0.05,
                        help='Depth scale factor (default: 0.05 for flat clothing)')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    generator = GaussianSplatGenerator(backend=args.backend, use_depth=not args.no_depth)
    result = generator.generate(args.image, args.output, depth_scale=args.depth_scale)

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
