/**
 * Timeline Grid Installation Configuration
 *
 * Runtime configuration for the "Dream to Reality" installation.
 * Override via URL parameters: ?aspect=32:9&debug=true
 */

export default {
    // Display configuration
    aspectRatio: '16:9',              // '16:9', '32:9', '1:1', 'auto'
    cameraResolution: { w: 1280, h: 720 },
    cellResolution: { w: 640, h: 480 },

    // Timing (milliseconds)
    act1Duration: 45000,              // Dream phase (speech capture)
    eraDisplayDuration: 15000,        // Per era in grid
    transitionDuration: 2000,         // Grid zoom animation
    act3Duration: 45000,              // Finale runway

    // Grid configuration
    totalEras: 12,
    gridProgression: [
        { eras: 1, cols: 1, rows: 1 },   // 1 era: 1x1
        { eras: 4, cols: 2, rows: 2 },   // 4 eras: 2x2
        { eras: 9, cols: 3, rows: 3 },   // 9 eras: 3x3
        { eras: 12, cols: 4, rows: 3 },  // 12 eras: 4x3
    ],

    // Backend
    wsUrl: 'ws://localhost:8765',

    // Audio
    enableAudio: true,
    audioVolume: 0.6,

    // Debug options
    showFps: false,
    skipEras: [],                     // [1, 2, 3] to skip specific eras
    jumpToAct: null,                  // 1, 2, or 3 to skip ahead

    // Era definitions
    eras: [
        {
            id: 1,
            year: '1963',
            name: 'Roberts Edge',
            description: 'The first edge detection algorithm',
            effect: 'robertsEdge',
            implementation: 'shader',
            aesthetic: {
                colorMode: 'green-phosphor',
                scanlines: true,
                resolution: 160
            }
        },
        {
            id: 2,
            year: '1970s',
            name: 'Hough Transform',
            description: 'Line and shape detection',
            effect: 'houghTransform',
            implementation: 'opencv',
            aesthetic: {
                overlay: 'detected-lines',
                gridPattern: true
            }
        },
        {
            id: 3,
            year: '1986',
            name: 'Canny Edge',
            description: 'Clean, precise edge detection',
            effect: 'cannyEdge',
            implementation: 'shader',
            aesthetic: {
                colorMode: 'white-on-black',
                lineWidth: 1
            }
        },
        {
            id: 4,
            year: '1990s',
            name: 'Watershed',
            description: 'Region-based segmentation',
            effect: 'watershed',
            implementation: 'opencv-worker',
            aesthetic: {
                colorMode: 'rainbow-regions',
                showBoundaries: true
            }
        },
        {
            id: 5,
            year: '2004',
            name: 'GrabCut',
            description: 'Interactive foreground extraction',
            effect: 'grabCut',
            implementation: 'opencv-worker',
            aesthetic: {
                background: 'checkerboard',
                showRect: true
            }
        },
        {
            id: 6,
            year: '2009-12',
            name: 'Magic Mirror',
            description: 'Early AR clothing try-on',
            effect: 'magicMirror',
            implementation: 'shader',
            aesthetic: {
                overlayDrift: true,
                lowRes: true
            }
        },
        {
            id: 7,
            year: '2015-17',
            name: 'OpenPose',
            description: 'Deep learning pose estimation',
            effect: 'openPose',
            implementation: 'tfjs',
            aesthetic: {
                keypoints: 18,
                coloredJoints: true
            }
        },
        {
            id: 8,
            year: '2018-20',
            name: 'BlazePose',
            description: 'Real-time 3D pose tracking',
            effect: 'blazePose',
            implementation: 'mediapipe',
            aesthetic: {
                keypoints: 33,
                show3D: true
            }
        },
        {
            id: 9,
            year: '2020-22',
            name: 'BodyPix',
            description: 'Body part segmentation',
            effect: 'bodyPix',
            implementation: 'tfjs',
            aesthetic: {
                colorCoded: true,
                showLabels: true
            }
        },
        {
            id: 10,
            year: '2023-24',
            name: 'AI 2D Generation',
            description: 'Stable Diffusion clothing',
            effect: 'aiGen2D',
            implementation: 'result-display',
            aesthetic: {
                generatingAnimation: true
            }
        },
        {
            id: 11,
            year: '2024-25',
            name: '3D Mesh',
            description: 'Image to 3D conversion',
            effect: 'meshGen',
            implementation: 'threejs',
            aesthetic: {
                wireframe: true,
                rotation: true
            }
        },
        {
            id: 12,
            year: 'Future',
            name: 'Real-time Try-On',
            description: 'Mesh follows body',
            effect: 'tryOn',
            implementation: 'mesh-deform',
            aesthetic: {
                glowEdges: true,
                particles: true
            }
        }
    ]
};

/**
 * Parse URL parameters and merge with config
 */
export function getConfigWithOverrides() {
    const params = new URLSearchParams(window.location.search);
    const config = { ...arguments[0] || {} };

    if (params.has('aspect')) {
        config.aspectRatio = params.get('aspect');
    }
    if (params.has('debug')) {
        config.showFps = params.get('debug') === 'true';
    }
    if (params.has('skip')) {
        config.skipEras = params.get('skip').split(',').map(Number);
    }
    if (params.has('act')) {
        config.jumpToAct = parseInt(params.get('act'));
    }
    if (params.has('duration')) {
        config.eraDisplayDuration = parseInt(params.get('duration'));
    }

    return config;
}
