#!/usr/bin/env python3
"""
server.py

Simple HTTP server for the Dreamwear Lookbook.
Serves static files and provides CORS headers for local development.
"""

import http.server
import socketserver
import os
from pathlib import Path


class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS support."""

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

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

    handler = CORSHTTPRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n{'='*60}")
        print(f"Dreamwear Lookbook Server")
        print(f"{'='*60}")
        print(f"\nServing at: http://localhost:{port}")
        print(f"\nURLs:")
        print(f"  Gallery:               http://localhost:{port}/index.html")
        print(f"  Composition viewer:    http://localhost:{port}/composition.html?id=test")
        print(f"  MediaPipe Diagnostic:  http://localhost:{port}/mediapipe_diagnostic.html")
        print(f"\nServing paths:")
        print(f"  /prerigged/           - Pre-rigged body meshes")
        print(f"  /comfyui_generated_mesh/ - Generated clothing")
        print(f"  /root-static/         - Root static folder (ClothSim, MediaPipe)")
        print(f"  /static/              - Lookbook static assets")
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
