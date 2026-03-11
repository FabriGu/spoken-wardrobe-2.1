/**
 * Gaussian Splat Test Viewer
 * Debug interface for testing splat generation and rendering
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

class GaussianSplatViewer {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.splatViewer = null;

        this.ws = null;
        this.connected = false;
        this.reconnectTimeout = null;

        this.stats = {
            fps: 0,
            lastTime: performance.now(),
            frames: 0
        };

        this.init();
    }

    init() {
        this.setupThreeJS();
        this.setupWebSocket();
        this.setupUI();
        this.animate();

        this.log('info', 'Viewer initialized');
    }

    setupThreeJS() {
        const container = document.getElementById('viewer-container');
        const canvas = document.getElementById('viewer-canvas');

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);

        // Camera
        this.camera = new THREE.PerspectiveCamera(
            60,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(2, 2, 2);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.autoRotate = true;
        this.controls.autoRotateSpeed = 1;

        // Grid helper (hidden by default)
        this.grid = new THREE.GridHelper(10, 10, 0x333333, 0x222222);
        this.grid.visible = false;
        this.scene.add(this.grid);

        // Axes helper (hidden by default)
        this.axes = new THREE.AxesHelper(2);
        this.axes.visible = false;
        this.scene.add(this.axes);

        // Add ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        // Handle resize
        window.addEventListener('resize', () => this.onResize());
    }

    setupWebSocket() {
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${location.host}/ws`;
        this.log('info', `Connecting to ${wsUrl}...`);

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.connected = true;
                const statusEl = document.getElementById('connection-status');
                statusEl.textContent = 'WS: Connected';
                statusEl.classList.add('connected');
                this.log('info', 'WebSocket connected');

                // Request lists
                this.ws.send(JSON.stringify({ type: 'list_images' }));
                this.ws.send(JSON.stringify({ type: 'list_outputs' }));
            };

            this.ws.onclose = () => {
                this.connected = false;
                const statusEl = document.getElementById('connection-status');
                statusEl.textContent = 'WS: Disconnected';
                statusEl.classList.remove('connected');
                this.log('warn', 'WebSocket disconnected, reconnecting in 3s...');

                // Reconnect after delay
                if (this.reconnectTimeout) {
                    clearTimeout(this.reconnectTimeout);
                }
                this.reconnectTimeout = setTimeout(() => this.setupWebSocket(), 3000);
            };

            this.ws.onerror = (err) => {
                this.log('error', `WebSocket error: ${err.message || 'Unknown error'}`);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    this.log('error', `Failed to parse message: ${e.message}`);
                }
            };
        } catch (e) {
            this.log('error', `Failed to connect: ${e.message}`);
        }
    }

    handleMessage(data) {
        switch (data.type) {
        case 'image_list':
            this.populateSelect('image-select', data.images);
            this.log('debug', `Found ${data.images.length} images`);
            break;

        case 'output_list':
            this.populateSelect('output-select', data.outputs);
            this.log('debug', `Found ${data.outputs.length} outputs`);
            break;

        case 'status':
            this.setStatus(data.status);
            if (data.backend) {
                document.getElementById('stat-backend').textContent = data.backend;
            }
            if (data.device) {
                document.getElementById('stat-device').textContent = data.device;
            }
            break;

        case 'generated':
            this.handleGenerated(data.result);
            break;

        case 'pong':
            // Heartbeat response
            break;
        }
    }

    handleGenerated(result) {
        if (result.success) {
            this.setStatus('ready');
            this.updateTimings(result.timings);
            this.updateStats(result.stats);
            this.log('info', `Generated: ${result.output}`);

            // Auto-load the generated splat
            this.loadSplat(result.output);

            // Refresh output list
            if (this.ws && this.connected) {
                this.ws.send(JSON.stringify({ type: 'list_outputs' }));
            }
        } else {
            this.setStatus('error');
            this.log('error', `Generation failed: ${result.errors.join(', ')}`);
        }
    }

    async loadSplat(path) {
        this.log('info', `Loading splat: ${path}`);
        this.setStatus('loading');
        document.getElementById('loading-indicator').classList.remove('hidden');

        try {
            // Remove existing splat viewer if any
            if (this.splatViewer) {
                try {
                    this.splatViewer.dispose();
                } catch (e) {
                    this.log('warn', `Error disposing previous viewer: ${e.message}`);
                }
                this.splatViewer = null;
            }

            // Clear scene of any splat-related objects
            const toRemove = [];
            this.scene.traverse((obj) => {
                if (obj.userData && obj.userData.isSplat) {
                    toRemove.push(obj);
                }
            });
            toRemove.forEach(obj => this.scene.remove(obj));

            // Get the filename from the path
            const filename = path.split('/').pop();
            const splatUrl = `/output/${filename}`;

            this.log('debug', `Loading from URL: ${splatUrl}`);

            // Create new splat viewer
            this.splatViewer = new GaussianSplats3D.Viewer({
                threeScene: this.scene,
                renderer: this.renderer,
                camera: this.camera,
                useBuiltInControls: false,
                selfDrivenMode: false,
                dynamicScene: false,
                sharedMemoryForWorkers: false
            });

            await this.splatViewer.addSplatScene(splatUrl, {
                showLoadingUI: false,
                progressiveLoad: true
            });

            this.setStatus('ready');
            this.log('info', 'Splat loaded successfully');

        } catch (error) {
            this.setStatus('error');
            this.log('error', `Failed to load splat: ${error.message}`);
            console.error(error);
        }

        document.getElementById('loading-indicator').classList.add('hidden');
    }

    setupUI() {
        // Generate button
        document.getElementById('btn-generate').onclick = () => {
            const image = document.getElementById('image-select').value;
            if (!image) {
                this.log('warn', 'No image selected');
                return;
            }
            if (!this.ws || !this.connected) {
                this.log('error', 'Not connected to server');
                return;
            }
            this.setStatus('generating');
            this.ws.send(JSON.stringify({ type: 'generate', image }));
            this.log('info', `Generating from: ${image}`);
        };

        // Load button
        document.getElementById('btn-load').onclick = () => {
            const output = document.getElementById('output-select').value;
            if (!output) {
                this.log('warn', 'No output selected');
                return;
            }
            this.loadSplat(output);
        };

        // Refresh buttons
        document.getElementById('btn-refresh-images').onclick = () => {
            if (this.ws && this.connected) {
                this.ws.send(JSON.stringify({ type: 'list_images' }));
                this.log('debug', 'Refreshing image list');
            }
        };
        document.getElementById('btn-refresh-outputs').onclick = () => {
            if (this.ws && this.connected) {
                this.ws.send(JSON.stringify({ type: 'list_outputs' }));
                this.log('debug', 'Refreshing output list');
            }
        };

        // View controls
        document.getElementById('ctrl-rotate').onchange = (e) => {
            this.controls.autoRotate = e.target.checked;
        };
        document.getElementById('ctrl-grid').onchange = (e) => {
            this.grid.visible = e.target.checked;
        };
        document.getElementById('ctrl-axes').onchange = (e) => {
            this.axes.visible = e.target.checked;
        };
        document.getElementById('btn-reset-camera').onclick = () => {
            this.camera.position.set(2, 2, 2);
            this.camera.lookAt(0, 0, 0);
            this.controls.reset();
            this.log('debug', 'Camera reset');
        };

        // Clear log
        document.getElementById('btn-clear-log').onclick = () => {
            document.getElementById('log-container').innerHTML = '';
        };
    }

    populateSelect(selectId, items) {
        const select = document.getElementById(selectId);
        const currentValue = select.value;

        // Clear existing options (except first)
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add new options
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item;
            option.textContent = item.split('/').pop();
            select.appendChild(option);
        });

        // Restore selection if still valid
        if (currentValue && items.includes(currentValue)) {
            select.value = currentValue;
        }
    }

    setStatus(status) {
        const el = document.getElementById('status-indicator');
        el.textContent = status.toUpperCase();
        el.className = `status-${status}`;
    }

    updateTimings(timings) {
        document.getElementById('time-preprocess').textContent =
            timings.preprocess ? `${(timings.preprocess * 1000).toFixed(0)}ms` : '--';
        document.getElementById('time-generation').textContent =
            timings.generation ? `${(timings.generation * 1000).toFixed(0)}ms` : '--';
        document.getElementById('time-save').textContent =
            timings.save ? `${(timings.save * 1000).toFixed(0)}ms` : '--';
        document.getElementById('time-total').textContent =
            timings.total ? `${(timings.total).toFixed(2)}s` : '--';
    }

    updateStats(stats) {
        document.getElementById('stat-splats').textContent =
            stats.num_splats?.toLocaleString() || '--';
        document.getElementById('stat-filesize').textContent =
            stats.file_size_mb ? `${stats.file_size_mb.toFixed(2)} MB` : '--';
        document.getElementById('stat-backend').textContent = stats.backend || '--';
        document.getElementById('stat-device').textContent = stats.device || '--';
    }

    log(level, message) {
        const container = document.getElementById('log-container');
        const entry = document.createElement('div');
        entry.className = 'log-entry';

        const time = new Date().toISOString().substr(11, 8);
        entry.innerHTML = `
            <span class="log-time">[${time}]</span>
            <span class="log-${level}">${message}</span>
        `;

        container.appendChild(entry);
        container.scrollTop = container.scrollHeight;

        // Also log to console
        const consoleMethod = level === 'info' ? 'log' : level;
        if (typeof console[consoleMethod] === 'function') {
            console[consoleMethod](`[SplatViewer] ${message}`);
        } else {
            console.log(`[SplatViewer] ${message}`);
        }
    }

    onResize() {
        const container = document.getElementById('viewer-container');
        this.camera.aspect = container.clientWidth / container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(container.clientWidth, container.clientHeight);
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        // Update controls
        this.controls.update();

        // Update and render splat viewer if exists
        if (this.splatViewer) {
            try {
                this.splatViewer.update();
                this.splatViewer.render();  // CRITICAL: Must call render() when selfDrivenMode is false!
            } catch (e) {
                // Log errors for debugging
                console.error('Splat viewer error:', e);
            }
        } else {
            // Only render standard Three.js scene when no splat viewer
            this.renderer.render(this.scene, this.camera);
        }

        // Update FPS
        this.stats.frames++;
        const now = performance.now();
        if (now - this.stats.lastTime >= 1000) {
            document.getElementById('render-fps').textContent = this.stats.frames;
            this.stats.frames = 0;
            this.stats.lastTime = now;
        }

        // Update render stats
        const info = this.renderer.info;
        document.getElementById('render-calls').textContent = info.render.calls;
        document.getElementById('render-tris').textContent =
            info.render.triangles.toLocaleString();
    }
}

// Start viewer when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.splatViewer = new GaussianSplatViewer();
    });
} else {
    window.splatViewer = new GaussianSplatViewer();
}
