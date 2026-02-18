#!/usr/bin/env python3
"""
session_scanner.py

Scans the comfyui_generated_mesh folder and inventories all sessions.
Filters to only sessions that have 3D meshes (clothing_mesh.glb).
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class Session:
    """Represents a user test session with all its assets."""
    id: str                          # Timestamp ID
    path: str                        # Full path to session folder
    has_mesh: bool                   # Whether clothing_mesh.glb exists
    has_metadata: bool               # Whether metadata.json exists
    transcription: Optional[str]     # User's spoken words
    timestamp: Optional[int]         # Unix timestamp
    files: dict                      # Dict of file types to paths


class SessionScanner:
    """Scans and filters user test sessions."""

    REQUIRED_FILES = [
        'clothing_mesh.glb',
        'generated_clothing.png',
        'original_frame.png',
        'mask.png',
        'metadata.json'
    ]

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.sessions: List[Session] = []

    def scan(self) -> List[Session]:
        """Scan all session folders and return list of Session objects."""
        print(f"[SessionScanner] Scanning {self.base_path}")

        self.sessions = []

        if not self.base_path.exists():
            print(f"[SessionScanner] ERROR: Path does not exist: {self.base_path}")
            return []

        # Iterate through all subdirectories
        for item in sorted(self.base_path.iterdir()):
            if not item.is_dir():
                continue

            # Check if it looks like a timestamp folder
            if not item.name.isdigit():
                continue

            session = self._scan_session(item)
            if session:
                self.sessions.append(session)

        print(f"[SessionScanner] Found {len(self.sessions)} total sessions")
        return self.sessions

    def _scan_session(self, session_path: Path) -> Optional[Session]:
        """Scan a single session folder."""
        session_id = session_path.name

        # Check which files exist
        files = {}
        for filename in self.REQUIRED_FILES:
            file_path = session_path / filename
            if file_path.exists():
                files[filename.split('.')[0]] = str(file_path)

        has_mesh = 'clothing_mesh' in files
        has_metadata = 'metadata' in files

        # Read metadata if available
        transcription = None
        timestamp = None

        if has_metadata:
            try:
                with open(session_path / 'metadata.json', 'r') as f:
                    metadata = json.load(f)
                    transcription = metadata.get('transcription', '')
                    timestamp = metadata.get('timestamp')
            except (json.JSONDecodeError, IOError) as e:
                print(f"[SessionScanner] Warning: Could not read metadata for {session_id}: {e}")

        return Session(
            id=session_id,
            path=str(session_path),
            has_mesh=has_mesh,
            has_metadata=has_metadata,
            transcription=transcription,
            timestamp=timestamp,
            files=files
        )

    def get_sessions_with_mesh(self) -> List[Session]:
        """Filter to only sessions that have 3D meshes."""
        return [s for s in self.sessions if s.has_mesh]

    def get_sessions_without_mesh(self) -> List[Session]:
        """Get sessions that don't have 3D meshes."""
        return [s for s in self.sessions if not s.has_mesh]

    def to_json(self, filepath: str, only_with_mesh: bool = True):
        """Export sessions to JSON file."""
        sessions = self.get_sessions_with_mesh() if only_with_mesh else self.sessions

        data = [asdict(s) for s in sessions]

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"[SessionScanner] Exported {len(data)} sessions to {filepath}")

    def print_summary(self):
        """Print summary statistics."""
        total = len(self.sessions)
        with_mesh = len(self.get_sessions_with_mesh())
        without_mesh = len(self.get_sessions_without_mesh())

        print("\n=== Session Scanner Summary ===")
        print(f"Total sessions:     {total}")
        print(f"With 3D mesh:       {with_mesh}")
        print(f"Without 3D mesh:    {without_mesh}")
        print(f"Success rate:       {with_mesh/total*100:.1f}%" if total > 0 else "N/A")

        # Sample transcriptions
        sessions_with_transcriptions = [s for s in self.sessions if s.transcription]
        if sessions_with_transcriptions:
            print("\nSample transcriptions:")
            for s in sessions_with_transcriptions[:5]:
                preview = s.transcription[:60] + "..." if len(s.transcription) > 60 else s.transcription
                print(f"  [{s.id}] \"{preview}\"")


def main():
    """Run session scanner on default path."""
    import argparse

    parser = argparse.ArgumentParser(description='Scan user test sessions')
    parser.add_argument('--path', '-p',
                       default='../comfyui_generated_mesh',
                       help='Path to session folder')
    parser.add_argument('--output', '-o',
                       default='sessions.json',
                       help='Output JSON file')
    parser.add_argument('--all', '-a',
                       action='store_true',
                       help='Include sessions without meshes')

    args = parser.parse_args()

    # Resolve path relative to script location
    script_dir = Path(__file__).parent
    base_path = (script_dir / args.path).resolve()

    scanner = SessionScanner(str(base_path))
    scanner.scan()
    scanner.print_summary()

    # Export
    output_path = script_dir / args.output
    scanner.to_json(str(output_path), only_with_mesh=not args.all)


if __name__ == '__main__':
    main()
