#!/usr/bin/env python3
"""
Extract Clothing from Inpainted Image

Applies the inpainting mask to the generated clothing image to extract
just the clothing on a transparent background.

This is needed because:
- generated_clothing.png contains the full scene (body + clothing)
- For Gaussian splat generation, we only want the clothing pixels
- The mask shows which region was inpainted (the clothing area)

Usage:
    # Process single folder
    python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/

    # Process and output to specific path
    python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/ -o clothing.png

    # Process all folders in comfyui_generated_mesh
    python3 extract_clothing.py --all

    # Preview without saving
    python3 extract_clothing.py ../comfyui_generated_mesh/1765267014/ --preview
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def extract_clothing(
    generated_path: str,
    mask_path: str,
    output_path: str = None,
    feather_pixels: int = 0,
    preview: bool = False
) -> np.ndarray:
    """
    Extract clothing from inpainted image using mask.

    Args:
        generated_path: Path to generated_clothing.png
        mask_path: Path to mask.png
        output_path: Where to save result (optional)
        feather_pixels: Edge feathering radius (0 = sharp edges)
        preview: Show preview window

    Returns:
        RGBA image with clothing on transparent background
    """
    # Load images
    generated = cv2.imread(generated_path, cv2.IMREAD_COLOR)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    if generated is None:
        raise FileNotFoundError(f"Could not load: {generated_path}")
    if mask is None:
        raise FileNotFoundError(f"Could not load: {mask_path}")

    # Verify dimensions match
    if generated.shape[:2] != mask.shape[:2]:
        raise ValueError(
            f"Dimension mismatch: generated {generated.shape[:2]} vs mask {mask.shape[:2]}"
        )

    # Optional: feather edges for smoother blending
    if feather_pixels > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), feather_pixels)

    # Convert BGR to RGB
    rgb = cv2.cvtColor(generated, cv2.COLOR_BGR2RGB)

    # Create RGBA image
    rgba = np.zeros((rgb.shape[0], rgb.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = mask  # Alpha channel from mask

    # Save if output path provided
    if output_path:
        # OpenCV needs BGRA for saving PNG with alpha
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        cv2.imwrite(output_path, bgra)
        print(f"Saved: {output_path}")

    # Preview if requested
    if preview:
        # Create checkerboard background to show transparency
        h, w = rgba.shape[:2]
        checker_size = 20
        checker = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(0, h, checker_size):
            for x in range(0, w, checker_size):
                if (y // checker_size + x // checker_size) % 2 == 0:
                    checker[y:y+checker_size, x:x+checker_size] = [200, 200, 200]
                else:
                    checker[y:y+checker_size, x:x+checker_size] = [150, 150, 150]

        # Composite clothing over checkerboard
        alpha = mask.astype(np.float32) / 255.0
        alpha = np.stack([alpha] * 3, axis=-1)
        preview_img = (generated.astype(np.float32) * alpha +
                      checker.astype(np.float32) * (1 - alpha)).astype(np.uint8)

        cv2.imshow("Extracted Clothing (press any key)", preview_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return rgba


def process_folder(folder_path: str, output_path: str = None, **kwargs) -> str:
    """
    Process a single output folder.

    Args:
        folder_path: Path to folder containing generated_clothing.png and mask.png
        output_path: Custom output path (default: folder/clothing_only.png)

    Returns:
        Path to extracted clothing image
    """
    folder = Path(folder_path)

    generated = folder / "generated_clothing.png"
    mask = folder / "mask.png"

    if not generated.exists():
        raise FileNotFoundError(f"Missing: {generated}")
    if not mask.exists():
        raise FileNotFoundError(f"Missing: {mask}")

    if output_path is None:
        output_path = str(folder / "clothing_only.png")

    extract_clothing(str(generated), str(mask), output_path, **kwargs)

    return output_path


def process_all_folders(base_path: str, **kwargs):
    """Process all folders in comfyui_generated_mesh."""
    base = Path(base_path)

    if not base.exists():
        print(f"Directory not found: {base}")
        return

    folders = sorted([f for f in base.iterdir() if f.is_dir()])

    print(f"Found {len(folders)} folders to process")

    success = 0
    skipped = 0
    failed = 0

    for folder in folders:
        try:
            # Skip if already processed
            output = folder / "clothing_only.png"
            if output.exists():
                print(f"  Skipping (exists): {folder.name}")
                skipped += 1
                continue

            process_folder(str(folder), **kwargs)
            print(f"  Processed: {folder.name}")
            success += 1

        except FileNotFoundError as e:
            print(f"  Missing files: {folder.name}")
            failed += 1
        except Exception as e:
            print(f"  Error: {folder.name} - {e}")
            failed += 1

    print(f"\nResults: {success} processed, {skipped} skipped, {failed} failed")


def main():
    parser = argparse.ArgumentParser(
        description='Extract clothing from inpainted images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'folder',
        nargs='?',
        help='Folder containing generated_clothing.png and mask.png'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output path for extracted clothing'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all folders in ../comfyui_generated_mesh/'
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Show preview window'
    )
    parser.add_argument(
        '--feather',
        type=int,
        default=0,
        help='Edge feathering radius in pixels (default: 0)'
    )

    args = parser.parse_args()

    if args.all:
        base = Path(__file__).parent.parent / "comfyui_generated_mesh"
        process_all_folders(str(base), feather_pixels=args.feather)
    elif args.folder:
        process_folder(
            args.folder,
            output_path=args.output,
            feather_pixels=args.feather,
            preview=args.preview
        )
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
