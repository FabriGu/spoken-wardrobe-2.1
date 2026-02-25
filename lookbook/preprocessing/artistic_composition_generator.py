#!/usr/bin/env python3
"""
artistic_composition_generator.py

Generates elegant, artistic composition configurations for the lookbook.
Creates simple, focused compositions that tell the story of each creation:
- Central mesh with point cloud dissolution effect
- Orbiting text from the transcription
- Thoughtful color palette
- Metadata about the creation process

Philosophy: "A visual summary of what the person put into their work"
"""

import os
import json
import random
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

from session_scanner import SessionScanner, Session


# Elegant color palettes - each is a cohesive set
COLOR_PALETTES = {
    "midnight": {
        "background": "#0a0a1a",
        "accent": "#8b5cf6",
        "text": "#ffffff",
        "particles": "#a78bfa"
    },
    "dawn": {
        "background": "#1a0a0a",
        "accent": "#ec4899",
        "text": "#fce7f3",
        "particles": "#f472b6"
    },
    "ocean": {
        "background": "#0a1a1a",
        "accent": "#06b6d4",
        "text": "#ecfeff",
        "particles": "#22d3ee"
    },
    "forest": {
        "background": "#0a1a0f",
        "accent": "#22c55e",
        "text": "#dcfce7",
        "particles": "#4ade80"
    },
    "sunset": {
        "background": "#1a0f0a",
        "accent": "#f97316",
        "text": "#fff7ed",
        "particles": "#fb923c"
    },
    "void": {
        "background": "#050505",
        "accent": "#ffffff",
        "text": "#e5e5e5",
        "particles": "#d4d4d4"
    },
    "dream": {
        "background": "#0f0a1a",
        "accent": "#c084fc",
        "text": "#f3e8ff",
        "particles": "#e879f9"
    },
    "ember": {
        "background": "#1a0505",
        "accent": "#ef4444",
        "text": "#fef2f2",
        "particles": "#f87171"
    }
}

# Animation presets for meshes
MESH_PRESETS = ["dreamy", "ethereal", "meditative", "flow"]

# Post-processing presets
POST_PRESETS = ["dreamy", "raw", "clean"]


@dataclass
class CreationMetadata:
    """Metadata about how the piece was created."""
    timestamp: int
    created_date: str
    transcription: str
    word_count: int
    has_mesh: bool


@dataclass
class ArtisticComposition:
    """Elegant composition configuration."""
    id: str
    title: str  # Generated from transcription
    transcription: str
    words: List[str]  # Individual words for orbiting text
    metadata: Dict
    palette: str
    background: Dict
    camera: Dict
    effects: Dict  # Global effects configuration
    elements: List[Dict]


class ArtisticCompositionGenerator:
    """Generate elegant artistic compositions."""

    def __init__(self, sessions_path: str, output_path: str):
        self.sessions_path = Path(sessions_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.scanner = SessionScanner(str(self.sessions_path))

    def generate_all(self):
        """Generate artistic compositions for all sessions."""
        self.scanner.scan()
        sessions = self.scanner.get_sessions_with_mesh()

        print(f"\n[ArtisticGenerator] Creating elegant compositions for {len(sessions)} sessions")

        compositions = []
        composition_ids = []

        for i, session in enumerate(sessions):
            print(f"\n[{i+1}/{len(sessions)}] {session.id}")

            composition = self.generate_composition(session)

            if composition:
                # Save individual config
                config_path = self.output_path / f"{session.id}.json"
                with open(config_path, 'w') as f:
                    json.dump(asdict(composition), f, indent=2)

                compositions.append(composition)
                composition_ids.append(session.id)
                print(f"  → {composition.title}")

        # Save index
        index_path = self.output_path / "index.json"
        with open(index_path, 'w') as f:
            json.dump(composition_ids, f, indent=2)

        print(f"\n[ArtisticGenerator] Created {len(compositions)} compositions")
        return compositions

    def generate_composition(self, session: Session) -> Optional[ArtisticComposition]:
        """Generate a single artistic composition."""
        if not session.has_mesh:
            return None

        # Extract words from transcription
        transcription = session.transcription or ""
        words = self._extract_words(transcription)

        # Generate title from first few meaningful words
        title = self._generate_title(words, transcription)

        # Choose palette based on words/mood
        palette_name = self._choose_palette(words)
        palette = COLOR_PALETTES[palette_name]

        # Create metadata
        metadata = {
            "timestamp": int(session.id),
            "created_date": self._timestamp_to_date(int(session.id)),
            "transcription": transcription,
            "word_count": len(words),
            "has_mesh": session.has_mesh
        }

        # Create elements
        elements = self._create_elements(session, words, palette)

        # Global effects configuration
        effects = {
            "postProcessing": random.choice(POST_PRESETS),
            "bloom": {
                "enabled": True,
                "strength": random.uniform(0.6, 1.0),
                "radius": random.uniform(0.3, 0.5)
            },
            "film": {
                "enabled": True,
                "grainIntensity": random.uniform(0.03, 0.08),
                "vignetteIntensity": random.uniform(0.2, 0.35)
            }
        }

        return ArtisticComposition(
            id=session.id,
            title=title,
            transcription=transcription,
            words=words,
            metadata=metadata,
            palette=palette_name,
            background={"color": palette["background"]},
            camera={
                "position": [0, 0, 8],
                "fov": 50,
                "target": [0, 0, 0]
            },
            effects=effects,
            elements=elements
        )

    def _extract_words(self, transcription: str) -> List[str]:
        """Extract meaningful words from transcription."""
        # Clean and split
        text = transcription.lower()
        # Remove punctuation except hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        words = text.split()

        # Filter out very short words and common stopwords
        stopwords = {'a', 'an', 'the', 'is', 'it', 'to', 'of', 'and', 'or', 'in', 'on', 'for', 'with', 'me', 'my', 'i', 'make', 'want', 'like', 'would'}
        words = [w for w in words if len(w) > 2 and w not in stopwords]

        # Remove duplicates while preserving order
        seen = set()
        unique_words = []
        for w in words:
            if w not in seen:
                seen.add(w)
                unique_words.append(w)

        return unique_words[:12]  # Max 12 words for orbiting

    def _generate_title(self, words: List[str], transcription: str) -> str:
        """Generate an artistic title from words."""
        if not words:
            return "Untitled"

        # Take first 2-3 meaningful words
        title_words = words[:3]
        title = ' '.join(w.capitalize() for w in title_words)

        # Always return the title as-is, even if short
        return title

    def _choose_palette(self, words: List[str]) -> str:
        """Choose a color palette based on the words."""
        # Keywords that suggest certain palettes
        palette_keywords = {
            "midnight": ["night", "dark", "purple", "space", "galaxy", "star"],
            "dawn": ["pink", "rose", "soft", "gentle", "flower", "bloom"],
            "ocean": ["blue", "water", "sea", "wave", "ocean", "cool", "aqua"],
            "forest": ["green", "nature", "leaf", "tree", "earth", "organic"],
            "sunset": ["orange", "warm", "sun", "fire", "gold", "yellow"],
            "void": ["black", "white", "minimal", "simple", "clean", "void"],
            "dream": ["dream", "fantasy", "magic", "ethereal", "mystic"],
            "ember": ["red", "hot", "passion", "intense", "bold", "crimson"]
        }

        word_set = set(words)

        # Score each palette
        scores = {}
        for palette, keywords in palette_keywords.items():
            score = sum(1 for kw in keywords if kw in word_set)
            scores[palette] = score

        # If any palette has matches, choose the best one
        best_palette = max(scores, key=scores.get)
        if scores[best_palette] > 0:
            return best_palette

        # Otherwise random
        return random.choice(list(COLOR_PALETTES.keys()))

    def _create_elements(self, session: Session, words: List[str], palette: Dict) -> List[Dict]:
        """Create the composition elements."""
        elements = []
        session_path = f"/comfyui_generated_mesh/{session.id}"

        # 1. Central mesh with point cloud effect
        if session.files.get('clothing_mesh'):
            elements.append({
                "type": "glb_mesh",
                "path": f"{session_path}/clothing_mesh.glb",
                "target_2d": {"x": 0.5, "y": 0.5},
                "depth_range": {"min": 2.5, "max": 3.5},
                "scale": 0.4,
                "animation": True,
                "animationPreset": random.choice(MESH_PRESETS),
                # Point cloud dissolution effect
                "pointCloud": {
                    "enabled": True,
                    "particleSize": 0.012,
                    "particleColor": palette["particles"],
                    "scatterRadius": 1.2,
                    "turbulence": 0.25
                }
            })

        # 2. Orbiting text effect (transcription words)
        if words:
            elements.append({
                "type": "curve_text",
                "words": words,
                "center": {"x": 0, "y": 0, "z": 0},
                "fontSize": 0.1,
                "textColor": palette["text"],
                "orbitSpeed": 0.06,
                "numCurves": min(3, max(2, len(words) // 4)),
                "curveRadius": 1.4,
                "curveHeight": 0.7,
                "staggerDelay": 0.25
            })

        # 3. Data images cluster - show all available process images
        # These are arranged around the mesh to show the creation journey
        data_images = [
            ('original_frame.png', 'original_frame', {"x": 0.15, "y": 0.35}),
            ('mask.png', 'mask', {"x": 0.18, "y": 0.65}),
            ('generated_clothing.png', 'generated_clothing', {"x": 0.85, "y": 0.50}),
        ]

        for i, (filename, file_key, position) in enumerate(data_images):
            # Check if file exists (file_key without extension and underscores)
            lookup_key = file_key.replace('_', '')
            if session.files.get(lookup_key) or session.files.get(file_key):
                elements.append({
                    "type": "image_plane",
                    "path": f"{session_path}/{filename}",
                    "target_2d": position,
                    "depth_range": {"min": 5, "max": 7},
                    "scale": 0.12,
                    "opacity": 0.35,
                    "rotation": random.choice([-10, 0, 10]),
                    # Spotlight effect for visibility
                    "spotlight": {
                        "enabled": True,
                        "intensity": 0.4,
                        "distance": 5
                    },
                    # Subtle bob animation
                    "bobAnimation": {
                        "enabled": True,
                        "amplitude": 0.02,
                        "speed": 0.3 + i * 0.1,  # Slightly different speeds
                        "offset": i * 1.5  # Phase offset
                    }
                })

        return elements

    def _timestamp_to_date(self, timestamp: int) -> str:
        """Convert Unix timestamp to readable date."""
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return "Unknown"


def main():
    """Run the artistic composition generator."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate artistic lookbook compositions')
    parser.add_argument('--sessions', '-s',
                       default='../../comfyui_generated_mesh',
                       help='Path to sessions folder')
    parser.add_argument('--output', '-o',
                       default='../compositions',
                       help='Output directory for configs')

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    sessions_path = (script_dir / args.sessions).resolve()
    output_path = (script_dir / args.output).resolve()

    print(f"Sessions: {sessions_path}")
    print(f"Output: {output_path}")

    generator = ArtisticCompositionGenerator(
        str(sessions_path),
        str(output_path)
    )

    generator.generate_all()


if __name__ == '__main__':
    main()
