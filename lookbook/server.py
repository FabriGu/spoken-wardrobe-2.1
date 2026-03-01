#!/usr/bin/env python3
"""
server.py

HTTP server for the Dreamwear Lookbook.
Serves static files and provides API endpoints for:
- /api/generate-2d: Proxy to ComfyUI for 2D clothing generation
- /api/generate-3d: Proxy to Rodin API for 3D mesh generation
- /api/save: Save new composition to filesystem
- /api/share/:id: Get shareable composition data
"""

import http.server
import socketserver
import os
import sys
import json
import time
import base64
import random
import requests
import numpy as np
from pathlib import Path
from io import BytesIO
from PIL import Image

# Add src/modules to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'modules'))

try:
    from comfyui_client import ComfyUIClient
    COMFYUI_AVAILABLE = True
except ImportError:
    print("Warning: comfyui_client not available")
    COMFYUI_AVAILABLE = False

# Configuration
COMFYUI_URL = os.environ.get('COMFYUI_URL', 'http://itp-ml.itp.tsoa.nyu.edu:9199')
RODIN_API_KEY = os.environ.get('RODIN_API_KEY', '')
RODIN_BASE_URL = 'https://api.hyper3d.com/api/v2'

# Global ComfyUI client (lazy initialized)
_comfyui_client = None

def get_comfyui_client():
    """Get or create ComfyUI client."""
    global _comfyui_client
    if _comfyui_client is None and COMFYUI_AVAILABLE:
        _comfyui_client = ComfyUIClient(COMFYUI_URL, timeout=300)
    return _comfyui_client


class LookbookRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS support and API endpoints."""

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests including share redirects."""
        # Handle share links - redirect to composition viewer
        if self.path.startswith('/share/'):
            composition_id = self.path.split('/share/')[1].split('?')[0]
            self.send_response(302)
            self.send_header('Location', f'/composition.html?id={composition_id}')
            self.end_headers()
            return

        # Handle share API
        if self.path.startswith('/api/share/'):
            composition_id = self.path.split('/api/share/')[1].split('?')[0]
            self.handle_get_share_data(composition_id)
            return

        # Default: serve static files
        super().do_GET()

    def do_POST(self):
        """Handle POST requests for API endpoints."""
        if self.path == '/api/generate-2d':
            self.handle_generate_2d()
        elif self.path == '/api/generate-3d':
            self.handle_generate_3d()
        elif self.path == '/api/save':
            self.handle_save_composition()
        else:
            self.send_error(404, 'API endpoint not found')

    def _read_json_body(self):
        """Read and parse JSON request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def _send_json_response(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_error_response(self, message, status=500):
        """Send error JSON response."""
        self._send_json_response({'success': False, 'error': message}, status)

    def handle_generate_2d(self):
        """Proxy 2D generation to ComfyUI."""
        try:
            body = self._read_json_body()
            prompt = body.get('prompt', 'elegant fashion clothing')

            print(f"\n[API] /api/generate-2d")
            print(f"  Prompt: {prompt[:60]}...")

            # Check if ComfyUI is available
            client = get_comfyui_client()
            if not client:
                self._send_error_response('ComfyUI client not available')
                return

            # Get image and mask from body, or use test image
            image_b64 = body.get('image')
            mask_b64 = body.get('mask')

            if image_b64 and mask_b64:
                # Decode base64 images
                image_data = base64.b64decode(image_b64)
                mask_data = base64.b64decode(mask_b64)

                image = np.array(Image.open(BytesIO(image_data)).convert('RGB'))
                mask = np.array(Image.open(BytesIO(mask_data)).convert('L'))
                print(f"  Image size: {image.shape}")
                print(f"  Mask size: {mask.shape}")
            else:
                # Use test image or create placeholder
                print("  No image provided, using test mode")
                # Create a simple test image (gray with white center)
                image = np.full((512, 512, 3), 128, dtype=np.uint8)
                mask = np.zeros((512, 512), dtype=np.uint8)
                mask[128:384, 128:384] = 255  # Body area

            # Find workflow file
            workflow_path = Path(__file__).parent.parent / 'workflows' / 'sdxl_inpainting_api.json'

            # Generate using ComfyUI
            seed = body.get('seed', random.randint(0, 2**32 - 1))
            steps = body.get('steps', 30)
            cfg = body.get('cfg', 7.5)

            result_image = client.generate_inpainting(
                image=image,
                mask=mask,
                prompt=prompt,
                negative_prompt="low quality, blurry, distorted, deformed",
                workflow_path=str(workflow_path),
                seed=seed,
                steps=steps,
                cfg=cfg
            )

            if result_image:
                # Convert PIL Image to base64
                buffer = BytesIO()
                result_image.save(buffer, format='PNG')
                result_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                print(f"  ✓ 2D generation complete")
                self._send_json_response({
                    'success': True,
                    'image': result_b64
                })
            else:
                self._send_error_response('ComfyUI generation failed')

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            self._send_error_response(str(e))

    def handle_generate_3d(self):
        """Proxy 3D generation to Rodin API."""
        try:
            body = self._read_json_body()
            image_b64 = body.get('image')

            print(f"\n[API] /api/generate-3d")

            if not image_b64:
                self._send_error_response('No image provided', 400)
                return

            if not RODIN_API_KEY:
                self._send_error_response('RODIN_API_KEY not configured')
                return

            # Save image temporarily
            import tempfile
            image_data = base64.b64decode(image_b64)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_image_path = f.name

            try:
                # Submit to Rodin API
                print("  Submitting to Rodin API...")
                task_uuid, subscription_key = self._submit_rodin_task(temp_image_path)

                if not task_uuid:
                    self._send_error_response('Failed to submit to Rodin API')
                    return

                # Poll for completion
                print("  Waiting for generation...")
                mesh_data = self._wait_and_download_rodin(task_uuid, subscription_key)

                if mesh_data:
                    mesh_b64 = base64.b64encode(mesh_data).decode('utf-8')
                    print(f"  ✓ 3D generation complete ({len(mesh_data)/1024:.1f} KB)")
                    self._send_json_response({
                        'success': True,
                        'mesh': mesh_b64
                    })
                else:
                    self._send_error_response('Rodin generation failed')

            finally:
                # Clean up temp file
                os.unlink(temp_image_path)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            self._send_error_response(str(e))

    def _submit_rodin_task(self, image_path):
        """Submit task to Rodin API."""
        url = f"{RODIN_BASE_URL}/rodin"

        with open(image_path, 'rb') as f:
            image_data = f.read()

        files = {
            'images': ('input.png', image_data, 'image/png')
        }

        data = {
            'tier': 'Regular',
            'quality_override': '5000',
            'material': 'PBR',
            'mesh_mode': 'Raw',
            'mesh_simplify': 'true',
            'geometry_file_format': 'glb'
        }

        headers = {
            'Authorization': f'Bearer {RODIN_API_KEY}'
        }

        response = requests.post(url, files=files, data=data, headers=headers, timeout=30)

        if response.status_code not in [200, 201]:
            print(f"  Rodin API error: {response.status_code} - {response.text}")
            return None, None

        result = response.json()
        task_uuid = result.get('uuid')
        subscription_key = result.get('jobs', {}).get('subscription_key')

        return task_uuid, subscription_key

    def _wait_and_download_rodin(self, task_uuid, subscription_key):
        """Wait for Rodin task and download result."""
        max_wait = 300  # 5 minutes
        poll_interval = 5
        start_time = time.time()

        while (time.time() - start_time) < max_wait:
            time.sleep(poll_interval)

            # Check status
            status_url = f"{RODIN_BASE_URL}/status"
            headers = {
                'Authorization': f'Bearer {RODIN_API_KEY}',
                'Content-Type': 'application/json'
            }
            response = requests.post(status_url, headers=headers,
                                     json={'subscription_key': subscription_key}, timeout=10)

            if response.status_code not in [200, 201]:
                continue

            jobs = response.json().get('jobs', [])

            # Check if done
            all_done = all(job.get('status') == 'Done' for job in jobs)
            any_failed = any(job.get('status') == 'Failed' for job in jobs)

            if any_failed:
                print("  Rodin job failed")
                return None

            if all_done:
                # Download
                download_url = f"{RODIN_BASE_URL}/download"
                response = requests.post(download_url, headers=headers,
                                         json={'task_uuid': task_uuid}, timeout=30)

                if response.status_code not in [200, 201]:
                    return None

                download_list = response.json().get('list', [])

                for item in download_list:
                    if item.get('name', '').endswith('.glb'):
                        file_response = requests.get(item['url'], timeout=60)
                        if file_response.status_code == 200:
                            return file_response.content

                return None

            elapsed = time.time() - start_time
            print(f"  Waiting... ({elapsed:.0f}s)")

        print("  Rodin timeout")
        return None

    def handle_save_composition(self):
        """Save new composition to filesystem."""
        try:
            body = self._read_json_body()

            print(f"\n[API] /api/save")

            prompt = body.get('prompt', '')
            title = body.get('title', 'Untitled')

            # Generate unique ID (timestamp)
            composition_id = str(int(time.time()))

            # Create session folder
            parent = Path(__file__).parent.parent
            session_path = parent / 'comfyui_generated_mesh' / composition_id
            session_path.mkdir(parents=True, exist_ok=True)

            # Save files
            if body.get('original_frame'):
                self._save_base64_file(body['original_frame'],
                                       session_path / 'original_frame.png')
            if body.get('mask'):
                self._save_base64_file(body['mask'],
                                       session_path / 'mask.png')
            if body.get('generated_clothing'):
                self._save_base64_file(body['generated_clothing'],
                                       session_path / 'generated_clothing.png')
            if body.get('mesh'):
                self._save_base64_file(body['mesh'],
                                       session_path / 'clothing_mesh.glb')

            # Generate composition JSON
            composition = self._generate_composition_json(
                composition_id, prompt, title
            )

            # Save composition config
            compositions_path = Path(__file__).parent / 'compositions'
            compositions_path.mkdir(exist_ok=True)

            config_path = compositions_path / f'{composition_id}.json'
            with open(config_path, 'w') as f:
                json.dump(composition, f, indent=2)

            # Update index
            self._update_composition_index(composition_id)

            print(f"  ✓ Saved composition: {composition_id}")
            self._send_json_response({
                'success': True,
                'id': composition_id,
                'url': f'/composition.html?id={composition_id}'
            })

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            self._send_error_response(str(e))

    def _save_base64_file(self, b64_data, path):
        """Save base64 encoded data to file."""
        data = base64.b64decode(b64_data)
        with open(path, 'wb') as f:
            f.write(data)

    def _generate_composition_json(self, composition_id, prompt, title):
        """Generate composition JSON config."""
        # Extract words from prompt
        import re
        text = prompt.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        words = text.split()
        stopwords = {'a', 'an', 'the', 'is', 'it', 'to', 'of', 'and', 'or', 'in',
                     'on', 'for', 'with', 'me', 'my', 'i', 'make', 'want', 'like', 'would'}
        words = [w for w in words if len(w) > 2 and w not in stopwords][:12]

        # Choose random palette
        palettes = ['midnight', 'dawn', 'ocean', 'forest', 'sunset', 'void', 'dream', 'ember']
        palette = random.choice(palettes)

        palette_colors = {
            'midnight': {'background': '#0a0a1a', 'accent': '#8b5cf6', 'text': '#ffffff', 'particles': '#a78bfa'},
            'dawn': {'background': '#1a0a0a', 'accent': '#ec4899', 'text': '#fce7f3', 'particles': '#f472b6'},
            'ocean': {'background': '#0a1a1a', 'accent': '#06b6d4', 'text': '#ecfeff', 'particles': '#22d3ee'},
            'forest': {'background': '#0a1a0f', 'accent': '#22c55e', 'text': '#dcfce7', 'particles': '#4ade80'},
            'sunset': {'background': '#1a0f0a', 'accent': '#f97316', 'text': '#fff7ed', 'particles': '#fb923c'},
            'void': {'background': '#050505', 'accent': '#ffffff', 'text': '#e5e5e5', 'particles': '#d4d4d4'},
            'dream': {'background': '#0f0a1a', 'accent': '#c084fc', 'text': '#f3e8ff', 'particles': '#e879f9'},
            'ember': {'background': '#1a0505', 'accent': '#ef4444', 'text': '#fef2f2', 'particles': '#f87171'}
        }

        colors = palette_colors[palette]
        session_path = f"/comfyui_generated_mesh/{composition_id}"

        elements = []

        # Mesh element
        elements.append({
            "type": "glb_mesh",
            "path": f"{session_path}/clothing_mesh.glb",
            "target_2d": {"x": 0.5, "y": 0.5},
            "depth_range": {"min": 2.5, "max": 3.5},
            "scale": 0.4,
            "animation": True,
            "animationPreset": "dreamy",
            "pointCloud": {
                "enabled": True,
                "particleSize": 0.012,
                "particleColor": colors['particles'],
                "scatterRadius": 1.2,
                "turbulence": 0.25
            }
        })

        # Text element
        if words:
            elements.append({
                "type": "curve_text",
                "words": words,
                "center": {"x": 0, "y": 0, "z": 0},
                "fontSize": 0.5,
                "textColor": colors['text'],
                "orbitSpeed": 0.06,
                "numCurves": min(3, max(2, len(words) // 4)),
                "curveRadius": 1.4,
                "curveHeight": 0.7,
                "staggerDelay": 0.25
            })

        # Data images
        data_images = [
            ('original_frame.png', {"x": 0.15, "y": 0.35}),
            ('mask.png', {"x": 0.18, "y": 0.65}),
            ('generated_clothing.png', {"x": 0.85, "y": 0.50})
        ]

        for i, (filename, position) in enumerate(data_images):
            elements.append({
                "type": "image_plane",
                "path": f"{session_path}/{filename}",
                "target_2d": position,
                "depth_range": {"min": 5, "max": 7},
                "scale": 0.12,
                "opacity": 0.35,
                "rotation": random.choice([-10, 0, 10]),
                "spotlight": {
                    "enabled": True,
                    "intensity": 0.4,
                    "distance": 5
                },
                "bobAnimation": {
                    "enabled": True,
                    "amplitude": 0.02,
                    "speed": 0.3 + i * 0.1,
                    "offset": i * 1.5
                }
            })

        return {
            "id": composition_id,
            "title": title,
            "transcription": prompt,
            "words": words,
            "palette": palette,
            "background": {"color": colors['background']},
            "camera": {
                "position": [0, 0, 8],
                "fov": 50,
                "target": [0, 0, 0]
            },
            "effects": {
                "postProcessing": "dreamy",
                "bloom": {
                    "enabled": True,
                    "strength": 0.9,
                    "radius": 0.2
                },
                "film": {
                    "enabled": True,
                    "grainIntensity": 0.05,
                    "vignetteIntensity": 0.3
                }
            },
            "elements": elements
        }

    def _update_composition_index(self, composition_id):
        """Update the composition index file."""
        compositions_path = Path(__file__).parent / 'compositions'
        index_path = compositions_path / 'index.json'

        # Load existing index
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)
        else:
            index = []

        # Add new ID at the beginning
        if composition_id not in index:
            index.insert(0, composition_id)

        # Save updated index
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)

    def handle_get_share_data(self, composition_id):
        """Return shareable composition data."""
        config_path = Path(__file__).parent / 'compositions' / f'{composition_id}.json'

        if not config_path.exists():
            self._send_error_response('Composition not found', 404)
            return

        with open(config_path) as f:
            config = json.load(f)

        share_data = {
            'id': composition_id,
            'title': config.get('title', 'Dreamwear Creation'),
            'description': config.get('transcription', ''),
            'url': f'/share/{composition_id}',
            'image': f'/comfyui_generated_mesh/{composition_id}/generated_clothing.png'
        }

        self._send_json_response(share_data)

    def translate_path(self, path):
        """Handle special paths for accessing session data and project resources."""
        # Remove leading slash
        path = path.lstrip('/')

        # Project root directory
        parent = Path(__file__).parent.parent

        # Handle comfyui_generated_mesh path
        if path.startswith('comfyui_generated_mesh/'):
            return str(parent / path)

        # Handle prerigged path (for rigged body meshes)
        if path.startswith('prerigged/'):
            return str(parent / path)

        # Handle root-static path (for mediapipe_diagnostic.html, ClothSimulator, etc)
        # Use /root-static/ to access files from project root's static/ folder
        if path.startswith('root-static/'):
            return str(parent / 'static' / path[12:])  # Remove 'root-static/' prefix

        # Handle mediapipe_diagnostic.html directly from root static
        if path == 'mediapipe_diagnostic.html':
            return str(parent / 'static' / path)

        # Handle models path
        if path.startswith('models/'):
            return str(parent / path)

        # Default behavior (serves from lookbook/ directory, including lookbook/static/)
        return super().translate_path('/' + path)


def run_server(port=8081, directory=None):
    """Run the HTTP server."""
    if directory:
        os.chdir(directory)

    handler = LookbookRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n{'='*60}")
        print(f"Dreamwear Lookbook Server")
        print(f"{'='*60}")
        print(f"\nServing at: http://localhost:{port}")
        print(f"\nPages:")
        print(f"  Gallery:               http://localhost:{port}/index.html")
        print(f"  Create:                http://localhost:{port}/create.html")
        print(f"  Composition viewer:    http://localhost:{port}/composition.html?id=test")
        print(f"  MediaPipe Diagnostic:  http://localhost:{port}/mediapipe_diagnostic.html")
        print(f"\nAPI Endpoints:")
        print(f"  POST /api/generate-2d  - 2D clothing generation (ComfyUI)")
        print(f"  POST /api/generate-3d  - 3D mesh generation (Rodin)")
        print(f"  POST /api/save         - Save composition")
        print(f"  GET  /api/share/:id    - Get share data")
        print(f"\nConfiguration:")
        print(f"  ComfyUI: {COMFYUI_URL}")
        print(f"  Rodin API Key: {'✓ Set' if RODIN_API_KEY else '✗ Not set'}")
        if not RODIN_API_KEY:
            print(f"  (Set with: export RODIN_API_KEY='your_key')")
        print(f"\nServing paths:")
        print(f"  /prerigged/              - Pre-rigged body meshes")
        print(f"  /comfyui_generated_mesh/ - Generated clothing")
        print(f"  /root-static/            - Root static folder")
        print(f"  /static/                 - Lookbook static assets")
        print(f"\nPress Ctrl+C to stop")
        print(f"{'='*60}\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run lookbook server')
    parser.add_argument('--port', '-p', type=int, default=8081,
                       help='Port to serve on (default: 8081)')

    args = parser.parse_args()

    # Change to lookbook directory
    script_dir = Path(__file__).parent
    run_server(args.port, str(script_dir))
