#!/usr/bin/env python3
"""
composition_generator.py

Generates composition configuration files for the lookbook.
Combines session data, keywords, and found imagery into
anamorphic composition configs.
"""

import os
import json
import random
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from session_scanner import SessionScanner, Session
from keyword_extractor import KeywordExtractor
from found_imagery_fetcher import FoundImageryFetcher


# Bold color palette (matching JavaScript)
BOLD_COLORS = [
    "#FF1493",  # Deep Pink
    "#00CED1",  # Dark Turquoise
    "#FFD700",  # Gold
    "#FF4500",  # Orange Red
    "#9400D3",  # Dark Violet
    "#00FF7F",  # Spring Green
    "#FF6347",  # Tomato
    "#1E90FF",  # Dodger Blue
    "#FF69B4",  # Hot Pink
    "#32CD32",  # Lime Green
    "#8b5cf6",  # Purple
    "#ec4899",  # Pink
]

# Rotation angles for chaotic layout
ROTATION_ANGLES = [0, 15, -15, 30, -30, 45, -45, 90, -90, 135, -135, 180]


@dataclass
class CompositionConfig:
    """Configuration for a single composition."""
    id: str
    transcription: str
    keywords: List[str]
    background: Dict
    camera: Dict
    elements: List[Dict]


class CompositionGenerator:
    """Generate composition configs from session data."""

    def __init__(self, sessions_path: str, output_path: str,
                 found_images_path: Optional[str] = None):
        self.sessions_path = Path(sessions_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Found images directory
        self.found_images_path = Path(found_images_path) if found_images_path else None

        # Initialize components
        self.scanner = SessionScanner(str(self.sessions_path))
        self.extractor = KeywordExtractor()
        self.fetcher = None

        if self.found_images_path:
            self.fetcher = FoundImageryFetcher(str(self.found_images_path))

    def generate_all(self, fetch_images: bool = False, images_per_composition: int = 5):
        """
        Generate composition configs for all sessions with meshes.

        Args:
            fetch_images: Whether to fetch found imagery from the web
            images_per_composition: Number of found images per composition
        """
        # Scan sessions
        self.scanner.scan()
        sessions = self.scanner.get_sessions_with_mesh()

        print(f"\n[CompositionGenerator] Generating configs for {len(sessions)} sessions")

        configs = []
        composition_ids = []

        for i, session in enumerate(sessions):
            print(f"\n[{i+1}/{len(sessions)}] Processing session {session.id}")

            config = self.generate_composition(
                session,
                fetch_images=fetch_images,
                images_count=images_per_composition
            )

            if config:
                # Save individual config
                config_path = self.output_path / f"{session.id}.json"
                with open(config_path, 'w') as f:
                    json.dump(asdict(config), f, indent=2)

                configs.append(config)
                composition_ids.append(session.id)
                print(f"  Saved: {config_path.name}")

        # Save index file
        index_path = self.output_path / "index.json"
        with open(index_path, 'w') as f:
            json.dump(composition_ids, f, indent=2)

        print(f"\n[CompositionGenerator] Generated {len(configs)} compositions")
        print(f"  Index saved to: {index_path}")

        return configs

    def generate_composition(self, session: Session,
                           fetch_images: bool = False,
                           images_count: int = 5) -> Optional[CompositionConfig]:
        """Generate a single composition config."""

        if not session.has_mesh:
            print(f"  Skipping {session.id}: no mesh")
            return None

        # Extract keywords
        keywords_data = self.extractor.extract(session.transcription or "")
        keywords = keywords_data['all_keywords']

        print(f"  Keywords: {keywords[:5]}")

        # Fetch found images if enabled
        found_images = []
        if fetch_images and self.fetcher and keywords:
            print(f"  Fetching found images...")
            found_images = self.fetcher.fetch_for_keywords(
                keywords[:3],  # Top 3 keywords
                images_count,
                session.id
            )

        # Generate element configurations
        elements = self._generate_elements(session, keywords, found_images)

        # Choose background color
        background_color = random.choice(BOLD_COLORS)

        config = CompositionConfig(
            id=session.id,
            transcription=session.transcription or "",
            keywords=keywords,
            background={"color": background_color},
            camera={
                "position": [0, 0, 10],
                "fov": 50,
                "target": [0, 0, 0]
            },
            elements=elements
        )

        return config

    def _generate_elements(self, session: Session,
                          keywords: List[str],
                          found_images: List[str]) -> List[Dict]:
        """Generate element configs for a composition."""
        elements = []

        # Use relative paths for web serving
        # Paths will be relative to lookbook/ directory
        session_rel_path = f"comfyui_generated_mesh/{session.id}"

        # 1. Primary: Clothing mesh (center)
        if session.files.get('clothing_mesh'):
            elements.append({
                "type": "glb_mesh",
                "path": f"/{session_rel_path}/clothing_mesh.glb",
                "target_2d": {"x": 0.5, "y": 0.5},
                "depth_range": {"min": 4, "max": 6},
                "scale": 0.35
            })

        # 2. Original body frame (positioned randomly)
        if session.files.get('original_frame'):
            pos = self._random_edge_position()
            elements.append({
                "type": "image_plane",
                "path": f"/{session_rel_path}/original_frame.png",
                "target_2d": pos,
                "depth_range": {"min": 8, "max": 15},
                "scale": 0.15,
                "rotation": random.choice(ROTATION_ANGLES),
                "opacity": 0.7
            })

        # 3. Generated clothing image
        if session.files.get('generated_clothing'):
            pos = self._random_edge_position()
            elements.append({
                "type": "image_plane",
                "path": f"/{session_rel_path}/generated_clothing.png",
                "target_2d": pos,
                "depth_range": {"min": 6, "max": 12},
                "scale": 0.2,
                "rotation": random.choice(ROTATION_ANGLES)
            })

        # 4. Mask as ghost overlay
        if session.files.get('mask'):
            elements.append({
                "type": "image_plane",
                "path": f"/{session_rel_path}/mask.png",
                "target_2d": {"x": 0.5, "y": 0.5},
                "depth_range": {"min": 3, "max": 4},
                "scale": 0.4,
                "opacity": 0.2
            })

        # 5. 3D Text keywords
        for i, keyword in enumerate(keywords[:3]):
            if len(keyword) > 2:
                pos = self._random_position()
                elements.append({
                    "type": "text_3d",
                    "text": keyword.upper(),
                    "target_2d": pos,
                    "depth_range": {"min": 6 + i*2, "max": 10 + i*2},
                    "scale": random.uniform(0.08, 0.15),
                    "color": self._random_text_color(),
                    "rotation": random.choice(ROTATION_ANGLES)
                })

        # 6. Found imagery
        for i, img_path in enumerate(found_images[:5]):
            pos = self._random_position()
            elements.append({
                "type": "image_plane",
                "path": img_path,
                "target_2d": pos,
                "depth_range": {"min": 10 + i*2, "max": 20 + i*2},
                "scale": random.uniform(0.1, 0.25),
                "rotation": random.choice(ROTATION_ANGLES),
                "opacity": random.uniform(0.5, 0.9)
            })

        # 7. Shader effects
        # Distortion effect
        elements.append({
            "type": "shader_plane",
            "shader": "chromatic",
            "target_2d": self._random_position(),
            "depth_range": {"min": 5, "max": 10},
            "scale": random.uniform(0.15, 0.3),
            "opacity": 0.3
        })

        # Glow effect
        elements.append({
            "type": "shader_plane",
            "shader": "glow",
            "target_2d": self._random_position(),
            "depth_range": {"min": 8, "max": 15},
            "scale": random.uniform(0.2, 0.4),
            "opacity": 0.25,
            "color": random.choice(BOLD_COLORS),
            "color2": "#000000"
        })

        # 8. Diagonal cut (like reference images)
        if random.random() > 0.5:
            angle = random.choice([30, 45, 60, -30, -45, -60])
            elements.append({
                "type": "shader_plane",
                "shader": "diagonal",
                "target_2d": {"x": 0.5, "y": 0.5},
                "depth_range": {"min": 2, "max": 3},
                "width": 15,
                "height": random.uniform(0.2, 0.5),
                "scale": 1.0,
                "opacity": 0.7,
                "color": random.choice(BOLD_COLORS),
                "angle": angle,
                "rotation": angle
            })

        return elements

    def _random_position(self) -> Dict:
        """Generate random position avoiding center."""
        while True:
            x = random.uniform(0.1, 0.9)
            y = random.uniform(0.1, 0.9)

            # Check if not too close to center
            dx = x - 0.5
            dy = y - 0.5
            if (dx*dx + dy*dy) > 0.04:  # Outside center radius 0.2
                return {"x": x, "y": y}

    def _random_edge_position(self) -> Dict:
        """Generate position near edges."""
        edge = random.choice(['top', 'bottom', 'left', 'right'])

        if edge == 'top':
            return {"x": random.uniform(0.1, 0.9), "y": random.uniform(0.1, 0.3)}
        elif edge == 'bottom':
            return {"x": random.uniform(0.1, 0.9), "y": random.uniform(0.7, 0.9)}
        elif edge == 'left':
            return {"x": random.uniform(0.1, 0.3), "y": random.uniform(0.1, 0.9)}
        else:
            return {"x": random.uniform(0.7, 0.9), "y": random.uniform(0.1, 0.9)}

    def _random_text_color(self) -> str:
        """Return white or a bold color for text."""
        if random.random() > 0.3:
            return "#FFFFFF"
        return random.choice(BOLD_COLORS)


def main():
    """Run composition generator."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate lookbook compositions')
    parser.add_argument('--sessions', '-s',
                       default='../../comfyui_generated_mesh',
                       help='Path to sessions folder')
    parser.add_argument('--output', '-o',
                       default='../compositions',
                       help='Output directory for configs')
    parser.add_argument('--images-dir', '-i',
                       default='../found_images',
                       help='Directory for found images')
    parser.add_argument('--fetch-images', '-f',
                       action='store_true',
                       help='Fetch found images from web')
    parser.add_argument('--images-count', '-n',
                       type=int, default=5,
                       help='Number of found images per composition')

    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    sessions_path = (script_dir / args.sessions).resolve()
    output_path = (script_dir / args.output).resolve()
    images_path = (script_dir / args.images_dir).resolve() if args.fetch_images else None

    generator = CompositionGenerator(
        str(sessions_path),
        str(output_path),
        str(images_path) if images_path else None
    )

    generator.generate_all(
        fetch_images=args.fetch_images,
        images_per_composition=args.images_count
    )


if __name__ == '__main__':
    main()
