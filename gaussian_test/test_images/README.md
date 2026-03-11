# Test Images

Place PNG images here for Gaussian Splat generation testing.

## Recommended Images

1. **Generated clothing images** from the main pipeline:
   ```bash
   cp ../comfyui_generated_mesh/*/generated_clothing.png .
   ```

2. **Any PNG with transparency** - the generator will use the alpha channel to determine which pixels to convert to splats.

## Requirements

- Format: PNG (recommended) or JPG
- Transparency: PNG with alpha channel works best
- Resolution: Any (will be resized to max 512x512 for processing)

## Example Usage

```bash
# Copy a generated clothing image
cp ../comfyui_generated_mesh/1234567890/generated_clothing.png sample.png

# Generate splat via CLI
python generate_splat.py test_images/sample.png -v

# Or use the web interface at http://localhost:8090
```
