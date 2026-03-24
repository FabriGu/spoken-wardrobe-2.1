#!/usr/bin/env python3
"""
Gaussian Splat Preview Tool

A simple tool to visualize and analyze generated Gaussian splats.
Shows the splat as a 3D point cloud with depth coloring.

Usage:
    python3 splat_preview.py                    # Preview latest splat
    python3 splat_preview.py path/to/file.ply   # Preview specific file
    python3 splat_preview.py --generate         # Generate new and preview
"""

import sys
import struct
import argparse
import numpy as np
from pathlib import Path

# Check for required libraries
try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def load_ply(path: str) -> tuple:
    """
    Load positions and colors from a 3DGS PLY file.

    Returns:
        Tuple of (positions, colors) arrays
    """
    positions = []
    colors = []

    with open(path, 'rb') as f:
        # Read header
        num_vertices = 0
        while True:
            line = f.readline().decode('ascii').strip()
            if line.startswith('element vertex'):
                num_vertices = int(line.split()[-1])
            if line == 'end_header':
                break

        # Read binary data
        # Format: x y z nx ny nz f_dc[3] f_rest[45] opacity scale[3] rot[4]
        floats_per_vertex = 62
        SH_C0 = 0.28209479177387814

        for _ in range(num_vertices):
            data = struct.unpack('<' + 'f' * floats_per_vertex,
                                f.read(4 * floats_per_vertex))

            positions.append([data[0], data[1], data[2]])

            # Color from SH DC component
            r = data[6] * SH_C0 + 0.5
            g = data[7] * SH_C0 + 0.5
            b = data[8] * SH_C0 + 0.5
            colors.append([
                np.clip(r, 0, 1),
                np.clip(g, 0, 1),
                np.clip(b, 0, 1)
            ])

    return np.array(positions, dtype=np.float32), np.array(colors, dtype=np.float32)


def analyze_splat(positions: np.ndarray, colors: np.ndarray) -> dict:
    """Analyze splat quality metrics."""

    stats = {
        'num_splats': len(positions),
        'x_range': (positions[:, 0].min(), positions[:, 0].max()),
        'y_range': (positions[:, 1].min(), positions[:, 1].max()),
        'z_range': (positions[:, 2].min(), positions[:, 2].max()),
        'z_std': positions[:, 2].std(),
        'z_mean': positions[:, 2].mean(),
        'color_mean': colors.mean(axis=0),
        'color_std': colors.std(axis=0),
        'center': positions.mean(axis=0),
    }

    # Depth quality score (0-100)
    # Good depth should have z_std > 0.05 and range > 0.2
    z_range = stats['z_range'][1] - stats['z_range'][0]
    depth_score = min(100, (stats['z_std'] / 0.15) * 50 + (z_range / 0.4) * 50)
    stats['depth_score'] = depth_score

    # Color variance score
    color_variance = colors.std()
    stats['color_score'] = min(100, color_variance * 300)

    # Overall quality
    stats['quality_score'] = (depth_score + stats['color_score']) / 2

    return stats


def print_analysis(stats: dict, path: str):
    """Print splat analysis to console."""
    print("\n" + "=" * 60)
    print(f"GAUSSIAN SPLAT ANALYSIS: {Path(path).name}")
    print("=" * 60)

    print(f"\n📊 BASIC STATS:")
    print(f"   Splats:     {stats['num_splats']:,}")
    print(f"   Center:     ({stats['center'][0]:.3f}, {stats['center'][1]:.3f}, {stats['center'][2]:.3f})")

    print(f"\n📐 DIMENSIONS:")
    print(f"   X range:    [{stats['x_range'][0]:.3f}, {stats['x_range'][1]:.3f}]")
    print(f"   Y range:    [{stats['y_range'][0]:.3f}, {stats['y_range'][1]:.3f}]")
    print(f"   Z range:    [{stats['z_range'][0]:.3f}, {stats['z_range'][1]:.3f}]")
    print(f"   Z std:      {stats['z_std']:.4f}")

    print(f"\n🎨 COLOR:")
    print(f"   Mean RGB:   ({stats['color_mean'][0]:.2f}, {stats['color_mean'][1]:.2f}, {stats['color_mean'][2]:.2f})")
    print(f"   Std RGB:    ({stats['color_std'][0]:.2f}, {stats['color_std'][1]:.2f}, {stats['color_std'][2]:.2f})")

    print(f"\n⭐ QUALITY SCORES:")
    print(f"   Depth:      {stats['depth_score']:.0f}/100 {'✓' if stats['depth_score'] > 50 else '⚠'}")
    print(f"   Color:      {stats['color_score']:.0f}/100 {'✓' if stats['color_score'] > 50 else '⚠'}")
    print(f"   Overall:    {stats['quality_score']:.0f}/100")

    if stats['quality_score'] < 30:
        print("\n⚠️  Low quality - consider regenerating with different parameters")
    elif stats['quality_score'] < 60:
        print("\n📝 Moderate quality - usable but could be improved")
    else:
        print("\n✅ Good quality splat!")


def visualize_matplotlib(positions: np.ndarray, colors: np.ndarray, title: str = "Gaussian Splat"):
    """3D visualization using matplotlib."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not available for visualization")
        return

    fig = plt.figure(figsize=(15, 5))

    # 3D scatter plot
    ax1 = fig.add_subplot(131, projection='3d')

    # Sample for performance (max 5000 points)
    if len(positions) > 5000:
        idx = np.random.choice(len(positions), 5000, replace=False)
        pos_sample = positions[idx]
        col_sample = colors[idx]
    else:
        pos_sample = positions
        col_sample = colors

    ax1.scatter(pos_sample[:, 0], pos_sample[:, 1], pos_sample[:, 2],
                c=col_sample, s=1, alpha=0.5)
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    ax1.set_zlabel('Z')
    ax1.set_title('3D View')

    # XY projection (front view)
    ax2 = fig.add_subplot(132)
    ax2.scatter(pos_sample[:, 0], pos_sample[:, 1], c=col_sample, s=1, alpha=0.5)
    ax2.set_xlabel('X')
    ax2.set_ylabel('Y')
    ax2.set_title('Front View (XY)')
    ax2.set_aspect('equal')
    ax2.invert_yaxis()

    # Depth histogram
    ax3 = fig.add_subplot(133)
    ax3.hist(positions[:, 2], bins=50, color='steelblue', edgecolor='white')
    ax3.set_xlabel('Z (Depth)')
    ax3.set_ylabel('Count')
    ax3.set_title('Depth Distribution')
    ax3.axvline(positions[:, 2].mean(), color='red', linestyle='--', label=f'Mean: {positions[:, 2].mean():.3f}')
    ax3.legend()

    plt.suptitle(title)
    plt.tight_layout()
    plt.show()


def visualize_cv2(positions: np.ndarray, colors: np.ndarray, title: str = "Gaussian Splat"):
    """Interactive 2D visualization using OpenCV."""
    if not HAS_CV2:
        print("OpenCV not available for visualization")
        return

    # Create image
    img_size = 800
    img = np.zeros((img_size, img_size, 3), dtype=np.uint8)

    # Normalize positions to image coordinates
    x_min, x_max = positions[:, 0].min(), positions[:, 0].max()
    y_min, y_max = positions[:, 1].min(), positions[:, 1].max()

    margin = 0.1
    x_range = (x_max - x_min) * (1 + margin)
    y_range = (y_max - y_min) * (1 + margin)
    scale = min(img_size / x_range, img_size / y_range) * 0.8

    cx, cy = img_size // 2, img_size // 2

    # Sort by depth for proper rendering
    z_order = np.argsort(positions[:, 2])

    # Draw splats
    for idx in z_order:
        x = int((positions[idx, 0] - (x_min + x_max) / 2) * scale + cx)
        y = int((positions[idx, 1] - (y_min + y_max) / 2) * scale + cy)

        if 0 <= x < img_size and 0 <= y < img_size:
            # Color from RGB to BGR
            color = (
                int(colors[idx, 2] * 255),
                int(colors[idx, 1] * 255),
                int(colors[idx, 0] * 255)
            )

            # Size based on depth (closer = larger)
            z_norm = (positions[idx, 2] - positions[:, 2].min()) / max(positions[:, 2].ptp(), 0.01)
            size = max(1, int(2 + z_norm * 3))

            cv2.circle(img, (x, y), size, color, -1)

    # Add info text
    cv2.putText(img, f"{len(positions)} splats", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"Z range: [{positions[:, 2].min():.2f}, {positions[:, 2].max():.2f}]",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "Press Q to quit, S to save", (10, img_size - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

    # Show window
    cv2.imshow(title, img)

    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord('s'):
            save_path = f"/tmp/splat_preview_{Path(title).stem}.png"
            cv2.imwrite(save_path, img)
            print(f"Saved to {save_path}")

    cv2.destroyAllWindows()
    return img


def find_latest_ply(output_dir: str = "output") -> str:
    """Find the most recent PLY file."""
    output_path = Path(__file__).parent / output_dir
    ply_files = list(output_path.glob("*.ply"))

    if not ply_files:
        return None

    return str(sorted(ply_files, key=lambda p: p.stat().st_mtime)[-1])


def generate_new_splat(image_path: str = None) -> str:
    """Generate a new splat from image."""
    from generate_splat import GaussianSplatGenerator

    if image_path is None:
        # Find first test image
        test_images = Path(__file__).parent / "test_images"
        images = list(test_images.glob("*.png")) + list(test_images.glob("*.jpg"))
        if not images:
            print("No test images found")
            return None
        image_path = str(images[0])

    print(f"\nGenerating splat from: {image_path}")
    generator = GaussianSplatGenerator(use_depth=True)
    result = generator.generate(image_path)

    if result['success']:
        print(f"Generated: {result['output']}")
        return result['output']
    else:
        print(f"Generation failed: {result['errors']}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Preview and analyze Gaussian splats')
    parser.add_argument('ply_file', nargs='?', help='PLY file to preview (uses latest if not specified)')
    parser.add_argument('--generate', '-g', action='store_true', help='Generate new splat first')
    parser.add_argument('--image', '-i', help='Image to generate splat from')
    parser.add_argument('--matplotlib', '-m', action='store_true', help='Use matplotlib instead of OpenCV')
    parser.add_argument('--no-viz', '-n', action='store_true', help='Analysis only, no visualization')

    args = parser.parse_args()

    # Determine PLY file to use
    if args.generate:
        ply_path = generate_new_splat(args.image)
        if not ply_path:
            return 1
    elif args.ply_file:
        ply_path = args.ply_file
    else:
        ply_path = find_latest_ply()
        if not ply_path:
            print("No PLY files found. Use --generate to create one.")
            return 1

    # Load and analyze
    print(f"\nLoading: {ply_path}")
    positions, colors = load_ply(ply_path)
    stats = analyze_splat(positions, colors)
    print_analysis(stats, ply_path)

    # Visualize
    if not args.no_viz:
        title = Path(ply_path).stem
        if args.matplotlib or not HAS_CV2:
            if HAS_MATPLOTLIB:
                visualize_matplotlib(positions, colors, title)
            else:
                print("\nNo visualization available (install matplotlib or opencv)")
        else:
            visualize_cv2(positions, colors, title)

    return 0


if __name__ == '__main__':
    sys.exit(main())
