"""
State Manager for Pipeline-UI Synchronization

This module manages the pipeline state machine and coordinates state
transitions with the WebSocket server for UI updates.

Pipeline States:
    IDLE          -> Welcome screen, waiting for user to step in front
    LISTENING     -> Listening for speech above threshold
    RECORDING     -> Recording audio (10 seconds fixed)
    TRANSCRIBING  -> Whisper processing audio
    A_POSE        -> Waiting for user to strike A-pose
    CAPTURING     -> Capturing body frame with BodyPix
    GENERATING_2D -> ComfyUI/Stable Diffusion generation
    GENERATING_3D -> Rodin API 3D mesh generation
    PREVIEW       -> Showing generated 2D preview
    CALIBRATING   -> Calibrating mesh to body
    TRY_ON        -> Real-time mesh overlay on camera
    ERROR         -> Error state with message

Usage:
    from src.ui import StateManager, PipelineWebSocketServer

    server = PipelineWebSocketServer()
    state_manager = StateManager(server)

    state_manager.transition('LISTENING', prompt='Describe your clothing...')
    state_manager.transition('RECORDING', duration=10)
"""

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum, auto
import time


class PipelineState(Enum):
    """Enumeration of all pipeline states."""
    IDLE = auto()
    LISTENING = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    A_POSE = auto()
    CAPTURING = auto()
    GENERATING_2D = auto()
    GENERATING_3D = auto()
    PREVIEW = auto()
    CALIBRATING = auto()
    TRY_ON = auto()
    ERROR = auto()


@dataclass
class StateTransition:
    """Record of a state transition for debugging/logging."""
    from_state: str
    to_state: str
    timestamp: float
    data: Dict[str, Any]


class StateManager:
    """
    Manages pipeline state transitions and UI synchronization.

    Provides a clean interface for the pipeline to transition between states
    while automatically notifying connected UI clients.

    Attributes:
        current_state: Current pipeline state
        previous_state: Previous pipeline state (for back navigation)
        transition_history: List of recent state transitions
        ws_server: Reference to WebSocket server for emitting updates
    """

    # Valid state transitions (from_state -> [allowed_to_states])
    VALID_TRANSITIONS = {
        'IDLE': ['LISTENING', 'ERROR'],
        'LISTENING': ['RECORDING', 'IDLE', 'ERROR'],
        'RECORDING': ['TRANSCRIBING', 'ERROR'],
        'TRANSCRIBING': ['A_POSE', 'ERROR'],
        'A_POSE': ['CAPTURING', 'IDLE', 'ERROR'],
        'CAPTURING': ['GENERATING_2D', 'ERROR'],
        'GENERATING_2D': ['PREVIEW', 'GENERATING_3D', 'ERROR'],
        'GENERATING_3D': ['CALIBRATING', 'ERROR'],
        'PREVIEW': ['GENERATING_3D', 'IDLE', 'ERROR'],
        'CALIBRATING': ['TRY_ON', 'ERROR'],
        'TRY_ON': ['IDLE', 'ERROR'],
        'ERROR': ['IDLE']
    }

    # State metadata (descriptions for UI)
    STATE_INFO = {
        'IDLE': {
            'title': 'SPOKEN WARDROBE',
            'subtitle': 'Step in front of the camera to begin',
            'show_camera': False
        },
        'LISTENING': {
            'title': 'Listening...',
            'subtitle': 'Describe the clothing you want to create',
            'show_camera': True
        },
        'RECORDING': {
            'title': 'Recording',
            'subtitle': 'Keep describing your clothing idea',
            'show_camera': True
        },
        'TRANSCRIBING': {
            'title': 'Processing',
            'subtitle': 'Transcribing your description...',
            'show_camera': False
        },
        'A_POSE': {
            'title': 'Strike an A-Pose',
            'subtitle': 'Stand with arms slightly away from body',
            'show_camera': True
        },
        'CAPTURING': {
            'title': 'Capturing',
            'subtitle': 'Hold still...',
            'show_camera': True
        },
        'GENERATING_2D': {
            'title': 'Generating Preview',
            'subtitle': 'Creating your clothing design...',
            'show_camera': False
        },
        'GENERATING_3D': {
            'title': 'Building 3D Model',
            'subtitle': 'Converting to 3D mesh...',
            'show_camera': False
        },
        'PREVIEW': {
            'title': 'PREVIEW COMPLETE!',
            'subtitle': 'Your clothing design is ready',
            'show_camera': False
        },
        'CALIBRATING': {
            'title': 'Calibrating',
            'subtitle': 'Aligning mesh to your body...',
            'show_camera': True
        },
        'TRY_ON': {
            'title': 'Virtual Try-On',
            'subtitle': 'Move around to see your clothing',
            'show_camera': True
        },
        'ERROR': {
            'title': 'Error',
            'subtitle': 'Something went wrong',
            'show_camera': False
        }
    }

    def __init__(self, ws_server=None, max_history: int = 50):
        """
        Initialize the state manager.

        Args:
            ws_server: PipelineWebSocketServer instance (optional)
            max_history: Maximum number of transitions to keep in history
        """
        self.ws_server = ws_server
        self.current_state = 'IDLE'
        self.previous_state = None
        self.state_data: Dict[str, Any] = {}
        self.transition_history: List[StateTransition] = []
        self.max_history = max_history

        # Callbacks for state entry
        self._on_enter_callbacks: Dict[str, List[Callable]] = {}

        # Callbacks for state exit
        self._on_exit_callbacks: Dict[str, List[Callable]] = {}

    def transition(self, new_state: str, **data) -> bool:
        """
        Transition to a new state.

        Validates the transition, updates state, records history,
        and notifies the WebSocket server.

        Args:
            new_state: Target state name
            **data: State-specific data to include

        Returns:
            True if transition was successful, False otherwise
        """
        # Validate state name
        if new_state not in self.STATE_INFO:
            print(f"[StateManager] Invalid state: {new_state}")
            return False

        # Validate transition (allow any transition in permissive mode)
        # Uncomment below for strict validation:
        # if new_state not in self.VALID_TRANSITIONS.get(self.current_state, []):
        #     print(f"[StateManager] Invalid transition: {self.current_state} -> {new_state}")
        #     return False

        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            timestamp=time.time(),
            data=data
        )
        self.transition_history.append(transition)

        # Trim history if needed
        if len(self.transition_history) > self.max_history:
            self.transition_history = self.transition_history[-self.max_history:]

        # Call exit callbacks for current state
        self._call_exit_callbacks(self.current_state)

        # Update state
        self.previous_state = self.current_state
        self.current_state = new_state

        # Merge state info with provided data
        state_info = self.STATE_INFO.get(new_state, {}).copy()
        state_info.update(data)
        self.state_data = state_info

        # Notify WebSocket server
        if self.ws_server:
            self.ws_server.emit_state_change(new_state, state_info)

        # Call enter callbacks for new state
        self._call_enter_callbacks(new_state, state_info)

        print(f"[StateManager] {self.previous_state} -> {new_state}")
        return True

    def on_enter(self, state: str, callback: Callable):
        """
        Register a callback to be called when entering a state.

        Args:
            state: State name
            callback: Function to call with (state_data,)
        """
        if state not in self._on_enter_callbacks:
            self._on_enter_callbacks[state] = []
        self._on_enter_callbacks[state].append(callback)

    def on_exit(self, state: str, callback: Callable):
        """
        Register a callback to be called when exiting a state.

        Args:
            state: State name
            callback: Function to call
        """
        if state not in self._on_exit_callbacks:
            self._on_exit_callbacks[state] = []
        self._on_exit_callbacks[state].append(callback)

    def _call_enter_callbacks(self, state: str, data: dict):
        """Call all registered enter callbacks for a state."""
        for callback in self._on_enter_callbacks.get(state, []):
            try:
                callback(data)
            except Exception as e:
                print(f"[StateManager] Error in enter callback for {state}: {e}")

    def _call_exit_callbacks(self, state: str):
        """Call all registered exit callbacks for a state."""
        for callback in self._on_exit_callbacks.get(state, []):
            try:
                callback()
            except Exception as e:
                print(f"[StateManager] Error in exit callback for {state}: {e}")

    def get_state(self) -> str:
        """Get the current state name."""
        return self.current_state

    def get_state_info(self) -> Dict[str, Any]:
        """Get the current state info including metadata."""
        return self.state_data.copy()

    def is_state(self, state: str) -> bool:
        """Check if currently in a specific state."""
        return self.current_state == state

    def reset(self):
        """Reset to IDLE state."""
        self.transition('IDLE')

    def error(self, message: str):
        """Transition to ERROR state with a message."""
        self.transition('ERROR', error_message=message)

    def update_progress(self, percent: float, message: str = ''):
        """
        Update progress for current generation state.

        Only works in GENERATING_2D or GENERATING_3D states.

        Args:
            percent: Progress percentage (0-100)
            message: Optional status message
        """
        if self.current_state in ['GENERATING_2D', 'GENERATING_3D']:
            stage = '2d' if self.current_state == 'GENERATING_2D' else '3d'
            if self.ws_server:
                self.ws_server.emit_generation_progress(stage, percent, message)

    def get_history(self, count: int = 10) -> List[StateTransition]:
        """
        Get recent state transition history.

        Args:
            count: Number of transitions to return

        Returns:
            List of recent StateTransition objects
        """
        return self.transition_history[-count:]
