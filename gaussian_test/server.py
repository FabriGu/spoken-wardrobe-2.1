#!/usr/bin/env python3
"""
Gaussian Splat Test Server
- HTTP server for static files
- WebSocket for real-time updates
- REST API for generation triggers
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from aiohttp import web
import aiohttp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('SplatServer')

# Import our generator
from generate_splat import GaussianSplatGenerator


class GaussianSplatServer:
    def __init__(self, host='localhost', port=8090):
        self.host = host
        self.port = port
        self.generator = GaussianSplatGenerator()
        self.websockets = set()
        self.current_job = None

    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websockets.add(ws)
        logger.info(f"WebSocket connected ({len(self.websockets)} total)")

        # Send initial status
        await ws.send_json({
            'type': 'status',
            'status': 'ready',
            'backend': self.generator.backend,
            'device': self.generator.device
        })

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self.handle_ws_message(ws, data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        finally:
            self.websockets.discard(ws)
            logger.info(f"WebSocket disconnected ({len(self.websockets)} remaining)")

        return ws

    async def handle_ws_message(self, ws, data):
        """Process incoming WebSocket messages"""
        msg_type = data.get('type')

        if msg_type == 'generate':
            # Start generation
            image_path = data.get('image')
            logger.info(f"Generate request for: {image_path}")
            await self.broadcast({
                'type': 'status',
                'status': 'generating',
                'image': image_path
            })

            # Run generation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.generator.generate,
                image_path
            )

            await self.broadcast({
                'type': 'generated',
                'result': result
            })

        elif msg_type == 'list_images':
            # List available test images
            images = list(Path('test_images').glob('*.png'))
            images.extend(Path('test_images').glob('*.jpg'))
            images.extend(Path('test_images').glob('*.jpeg'))
            await ws.send_json({
                'type': 'image_list',
                'images': [str(p) for p in sorted(images)]
            })

        elif msg_type == 'list_outputs':
            # List generated splats (PLY and SPLAT formats)
            outputs = list(Path('output').glob('*.ply'))
            outputs.extend(Path('output').glob('*.splat'))
            await ws.send_json({
                'type': 'output_list',
                'outputs': [str(p) for p in sorted(outputs, reverse=True)]
            })

        elif msg_type == 'ping':
            await ws.send_json({'type': 'pong'})

    async def broadcast(self, data):
        """Send message to all connected clients"""
        for ws in list(self.websockets):
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                self.websockets.discard(ws)

    async def api_generate(self, request):
        """REST API: POST /api/generate"""
        data = await request.json()
        image_path = data.get('image')

        if not image_path or not os.path.exists(image_path):
            return web.json_response({'error': 'Image not found'}, status=400)

        result = self.generator.generate(image_path)
        return web.json_response(result)

    async def api_status(self, request):
        """REST API: GET /api/status"""
        return web.json_response({
            'status': 'ready',
            'backend': self.generator.backend,
            'device': self.generator.device,
            'connected_clients': len(self.websockets)
        })

    async def api_list_images(self, request):
        """REST API: GET /api/images"""
        images = list(Path('test_images').glob('*.png'))
        images.extend(Path('test_images').glob('*.jpg'))
        return web.json_response({
            'images': [str(p) for p in sorted(images)]
        })

    async def api_list_outputs(self, request):
        """REST API: GET /api/outputs"""
        outputs = list(Path('output').glob('*.ply'))
        outputs.extend(Path('output').glob('*.splat'))
        return web.json_response({
            'outputs': [str(p) for p in sorted(outputs, reverse=True)]
        })

    def create_app(self):
        """Create aiohttp application"""
        app = web.Application()

        # WebSocket
        app.router.add_get('/ws', self.websocket_handler)

        # REST API
        app.router.add_get('/api/status', self.api_status)
        app.router.add_post('/api/generate', self.api_generate)
        app.router.add_get('/api/images', self.api_list_images)
        app.router.add_get('/api/outputs', self.api_list_outputs)

        # Static files
        static_path = Path(__file__).parent / 'static'
        app.router.add_static('/static/', static_path)

        # Serve output files (PLY)
        output_path = Path(__file__).parent / 'output'
        if output_path.exists():
            app.router.add_static('/output/', output_path)

        # Serve test images
        test_images_path = Path(__file__).parent / 'test_images'
        if test_images_path.exists():
            app.router.add_static('/test_images/', test_images_path)

        # Root route - serve index.html
        async def index_handler(request):
            return web.FileResponse(static_path / 'index.html')

        app.router.add_get('/', index_handler)

        return app

    def run(self):
        """Start the server"""
        app = self.create_app()
        logger.info(f"Starting Gaussian Splat Test Server")
        logger.info(f"  URL: http://{self.host}:{self.port}")
        logger.info(f"  Backend: {self.generator.backend}")
        logger.info(f"  Device: {self.generator.device}")
        logger.info("Press Ctrl+C to stop")
        web.run_app(app, host=self.host, port=self.port)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Gaussian Splat Test Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8090, help='Port to bind to')
    args = parser.parse_args()

    server = GaussianSplatServer(host=args.host, port=args.port)
    server.run()
