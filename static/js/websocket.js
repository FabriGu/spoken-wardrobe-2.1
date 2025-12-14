/**
 * WebSocket Client for Spoken Wardrobe UI
 *
 * Handles connection to the Python backend WebSocket server and
 * dispatches messages to appropriate handlers.
 *
 * Message Types (from server):
 *   - state_change: Pipeline state transitions
 *   - frame: Camera frame as base64 JPEG
 *   - audio_level: Audio level for waveform visualization
 *   - transcription: Transcribed text from Whisper
 *   - generation_progress: Progress updates during generation
 *   - mesh_ready: GLB mesh data for 3D overlay
 *   - preview_image: Generated 2D preview image
 */

export class WebSocketClient {
    /**
     * Create a WebSocket client.
     * @param {string} url - WebSocket server URL (e.g., 'ws://localhost:8765')
     */
    constructor(url = 'ws://localhost:8765') {
        this.url = url;
        this.socket = null;
        this.reconnectInterval = 2000; // 2 seconds
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
        this.isConnected = false;

        // Event handlers (to be set by app)
        this.onStateChange = null;
        this.onFrame = null;
        this.onAudioLevel = null;
        this.onTranscription = null;
        this.onGenerationProgress = null;
        this.onMeshReady = null;
        this.onPreviewImage = null;
        this.onPreviewImageCropped = null;
        this.onPreviewMask = null;
        this.onConnect = null;
        this.onDisconnect = null;
    }

    /**
     * Connect to the WebSocket server.
     */
    connect() {
        console.log(`[WebSocket] Connecting to ${this.url}...`);

        try {
            this.socket = new WebSocket(this.url);

            this.socket.onopen = () => {
                console.log('[WebSocket] Connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this._updateConnectionStatus(true);
                if (this.onConnect) this.onConnect();
            };

            this.socket.onclose = (event) => {
                console.log(`[WebSocket] Disconnected (code: ${event.code})`);
                this.isConnected = false;
                this._updateConnectionStatus(false);
                if (this.onDisconnect) this.onDisconnect();
                this._attemptReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
            };

            this.socket.onmessage = (event) => {
                this._handleMessage(event.data);
            };

        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this._attemptReconnect();
        }
    }

    /**
     * Disconnect from the server.
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    /**
     * Send a message to the server.
     * @param {object} data - Data to send as JSON
     */
    send(data) {
        if (this.isConnected && this.socket) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('[WebSocket] Cannot send - not connected');
        }
    }

    /**
     * Send a user action to the server.
     * @param {string} action - Action name (e.g., 'restart', 'skip_3d')
     * @param {object} data - Optional additional data
     */
    sendAction(action, data = {}) {
        this.send({
            type: 'user_action',
            action: action,
            ...data
        });
    }

    /**
     * Handle incoming WebSocket messages.
     * @private
     */
    _handleMessage(rawData) {
        try {
            const data = JSON.parse(rawData);

            switch (data.type) {
                case 'state_change':
                    if (this.onStateChange) {
                        this.onStateChange(data.state, data.data || {});
                    }
                    break;

                case 'frame':
                    if (this.onFrame) {
                        this.onFrame(
                            data.image,
                            data.landmarks || null,
                            data.calibration || null,
                            data.bone_rotations || null,
                            data.landmarks_2d || null,  // 2D pixel landmarks for keypoint rendering
                            data.frame_aspect || null   // Frame aspect ratio for proper scaling
                        );
                    }
                    break;

                case 'audio_level':
                    if (this.onAudioLevel) {
                        this.onAudioLevel(data.level, data.threshold);
                    }
                    break;

                case 'transcription':
                    if (this.onTranscription) {
                        this.onTranscription(data.text, data.is_final);
                    }
                    break;

                case 'generation_progress':
                    if (this.onGenerationProgress) {
                        this.onGenerationProgress(
                            data.stage,
                            data.percent,
                            data.message || ''
                        );
                    }
                    break;

                case 'mesh_ready':
                    console.log(`[WebSocket] mesh_ready received! Size: ${data.size_kb?.toFixed(1)} KB, has texture: ${!!data.texture}`);
                    if (this.onMeshReady) {
                        this.onMeshReady(data.glb, data.size_kb, data.texture);
                    }
                    break;

                case 'preview_image':
                    if (this.onPreviewImage) {
                        this.onPreviewImage(data.image);
                    }
                    break;

                case 'preview_image_cropped':
                    if (this.onPreviewImageCropped) {
                        this.onPreviewImageCropped(data.image);
                    }
                    break;

                case 'preview_mask':
                    if (this.onPreviewMask) {
                        this.onPreviewMask(data.mask);
                    }
                    break;

                case 'pong':
                    // Heartbeat response, ignore
                    break;

                default:
                    console.log('[WebSocket] Unknown message type:', data.type);
            }

        } catch (error) {
            console.error('[WebSocket] Error parsing message:', error);
        }
    }

    /**
     * Attempt to reconnect to the server.
     * @private
     */
    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WebSocket] Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        console.log(`[WebSocket] Reconnecting in ${this.reconnectInterval}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, this.reconnectInterval);
    }

    /**
     * Update the connection status indicator in the UI.
     * @private
     */
    _updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            statusEl.classList.toggle('connected', connected);
            statusEl.classList.toggle('disconnected', !connected);
            const textEl = statusEl.querySelector('.status-text');
            if (textEl) {
                textEl.textContent = connected ? 'Connected' : 'Disconnected';
            }
        }
    }

    /**
     * Start sending heartbeat pings to keep connection alive.
     */
    startHeartbeat(intervalMs = 30000) {
        this._heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping' });
            }
        }, intervalMs);
    }

    /**
     * Stop the heartbeat.
     */
    stopHeartbeat() {
        if (this._heartbeatInterval) {
            clearInterval(this._heartbeatInterval);
            this._heartbeatInterval = null;
        }
    }
}
