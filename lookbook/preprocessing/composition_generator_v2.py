#!/usr/bin/env python3
"""
composition_generator_v2.py

Enhanced composition generator with more chaos, varied shaders,
mesh animations, and richer visual density.
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
    "#000000",  # Black (for high contrast)
    "#FFFFFF",  # White
]

# Shader library matching JavaScript
SHADERS = [
    'dreamBlur', 'glitch', 'kineticLiquid', 'chromatic',
    'noiseField', 'scanLine', 'voronoi', 'particleCloud',
    'holographic', 'dataMosh', 'ripple', 'mandala',
    'random', 'mood:dreamy', 'mood:chaotic', 'mood:digital'
]

# Shader moods for keyword matching
SHADER_MOODS = {
    'dream': ['dreamBlur', 'ripple', 'kineticLiquid', 'mood:dreamy'],
    'red': ['chromatic', 'glitch', 'voronoi'],
    'wedding': ['dreamBlur', 'holographic', 'mandala'],
    'clown': ['glitch', 'dataMosh', 'chromatic'],
    't-shirt': ['noiseField', 'scanLine', 'kineticLiquid'],
    'dress': ['dreamBlur', 'holographic', 'ripple'],
    'chaos': ['glitch', 'dataMosh', 'voronoi', 'mood:chaotic'],
    'peace': ['dreamBlur', 'ripple', 'particleCloud', 'mood:dreamy'],
    'love': ['holographic', 'mandala', 'dreamBlur'],
    'angry': ['glitch', 'dataMosh', 'scanLine'],
    'calm': ['ripple', 'dreamBlur', 'kineticLiquid'],
}

# Rotation angles for chaotic layout
ROTATION_ANGLES = [0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90, 135, -135, 180]

# Mesh animation presets
ANIMATION_PRESETS = ['dreamy', 'chaotic', 'ethereal', 'aggressive', 'meditative']


@dataclass
class CompositionConfig:
    """Configuration for a single composition."""
    id: str
    transcription: str
    keywords: List[str]
    background: Dict
    camera: Dict
    elements: List[Dict]


class CompositionGeneratorV2:
    """Generate enhanced composition configs from session data."""

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

        print(f"\n[CompositionGeneratorV2] Generating enhanced configs for {len(sessions)} sessions")

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

        print(f"\n[CompositionGeneratorV2] Generated {len(configs)} compositions")
        print(f"  Index saved to: {index_path}")

        return configs

    def generate_composition(self, session: Session,
                           fetch_images: bool = False,
                           images_count: int = 5) -> Optional[CompositionConfig]:
        """Generate a single enhanced composition config."""

        if not session.has_mesh:
            print(f"  Skipping {session.id}: no mesh")
            return None

        # Extract keywords
        keywords_data = self.extractor.extract(session.transcription or "")
        keywords = keywords_data['all_keywords']

        print(f"  Keywords: {keywords[:5]}")

        # Determine mood from keywords
        mood = self.detect_mood(keywords)
        print(f"  Detected mood: {mood}")

        # Fetch found images if enabled
        found_images = []
        if fetch_images and self.fetcher and keywords:
            print(f"  Fetching found images...")
            found_images = self.fetcher.fetch_for_keywords(
                keywords[:3],
                images_count,
                session.id
            )

        # Generate element configurations
        elements = self._generate_elements(session, keywords, found_images, mood)

        # Choose background color based on mood
        background_color = self.select_background_color(mood, keywords)

        # Select camera position with variation
        camera_position = self.generate_camera_position(mood)

        config = CompositionConfig(
            id=session.id,
            transcription=session.transcription or "",
            keywords=keywords,
            background={"color": background_color},
            camera={
                "position": camera_position,
                "fov": 50,
                "target": [0, 0, 0]
            },
            elements=elements
        )

        return config

    def detect_mood(self, keywords: List[str]) -> str:
        """Detect mood from keywords."""
        mood_keywords = {
            'dreamy': ['dream', 'nice', 'beautiful', 'soft', 'gentle', 'elegant'],
            'chaotic': ['chaos', 'mess', 'crazy', 'wild', 'loud', 'angry'],
            'digital': ['future', 'tech', 'modern', 'glitch', 'cyber'],
            'organic': ['natural', 'flower', 'leaf', 'soft', 'flowing'],
            'aggressive': ['sharp', 'hard', 'strong', 'power', 'bold'],
            'calm': ['peace', 'quiet', 'calm', 'soft', 'gentle']
        }
        
        mood_scores = {mood: 0 for mood in mood_keywords}
        
        for kw in keywords:
            kw_lower = kw.lower()
            for mood, triggers in mood_keywords.items():
                if any(t in kw_lower for t in triggers):
                    mood_scores[mood] += 1
        
        # Return highest scoring mood, or random if tie
        max_score = max(mood_scores.values())
        if max_score > 0:
            best_moods = [m for m, s in mood_scores.items() if s == max_score]
            return random.choice(best_moods)
        
        return random.choice(['dreamy', 'chaotic', 'digital'])

    def select_background_color(self, mood: str, keywords: List[str]) -> str:
        """Select background color based on mood and keywords."""
        mood_colors = {
            'dreamy': ['#FF69B4', '#8b5cf6', '#00CED1', '#1E90FF'],
            'chaotic': ['#FF1493', '#FF4500', '#FFD700', '#000000'],
            'digital': ['#000000', '#9400D3', '#00FF7F', '#1E90FF'],
            'organic': ['#32CD32', '#00FF7F', '#FFD700', '#8b5cf6'],
            'aggressive': ['#FF0000', '#FF4500', '#000000', '#FF1493'],
            'calm': ['#00CED1', '#1E90FF', '#FFFFFF', '#8b5cf6']
        }
        
        # Check for color keywords
        color_keywords = {
            'red': '#FF0000', 'blue': '#1E90FF', 'green': '#00FF7F',
            'yellow': '#FFD700', 'pink': '#FF69B4', 'purple': '#9400D3',
            'black': '#000000', 'white': '#FFFFFF', 'orange': '#FF4500'
        }
        
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in color_keywords:
                return color_keywords[kw_lower]
        
        return random.choice(mood_colors.get(mood, BOLD_COLORS))

    def generate_camera_position(self, mood: str) -> List[float]:
        """Generate varied camera position based on mood."""
        # Standard is [0, 0, 10]
        # Vary slightly for different perspectives
        variations = {
            'dreamy': [(0, 0, 10), (1, 0.5, 10), (-0.5, 1, 10)],
            'chaotic': [(0, 0, 8), (2, -1, 12), (-1, 2, 9)],
            'digital': [(0, 0, 10), (0, 0, 15), (1, 1, 8)],
            'aggressive': [(0, 0, 7), (0, 0, 6), (2, 0, 8)]
        }
        
        pos = random.choice(variations.get(mood, [(0, 0, 10)]))
        return [pos[0], pos[1], pos[2]]

    def select_shaders_for_mood(self, mood: str, keywords: List[str], count: int = 3) -> List[str]:
        """Select appropriate shaders for mood and keywords."""
        selected = []
        
        # First, try keyword-specific shaders
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in SHADER_MOODS:
                selected.extend(SHADER_MOODS[kw_lower])
        
        # Add mood-based shaders
        if mood in SHADER_MOODS:
            selected.extend(SHADER_MOODS[mood])
        
        # If still not enough, add random shaders
        while len(selected) < count:
            selected.append(random.choice(SHADERS))
        
        # Return unique selection
        unique = list(set(selected))
        return random.sample(unique, min(count, len(unique)))

    def _generate_elements(self, session: Session,
                          keywords: List[str],
                          found_images: List[str],
                          mood: str) -> List[Dict]:
        """Generate enhanced element configs for a composition."""
        elements = []

        # Use relative paths for web serving
        session_rel_path = f"comfyui_generated_mesh/{session.id}"

        # 1. Primary: Clothing mesh (center) with animation
        if session.files.get('clothing_mesh'):
            animation_preset = self.select_animation_preset(mood)
            
            elements.append({
                "type": "glb_mesh",
                "path": f"/{session_rel_path}/clothing_mesh.glb",
                "target_2d": {"x": 0.5, "y": 0.5},
                "depth_range": {"min": 4, "max": 6},
                "scale": 0.35,
                "animation": True,
                "animationPreset": animation_preset,
                "emissive": self.select_emissive_color(mood)
            })

        # 2. Original body frame (positioned chaotically)
        if session.files.get('original_frame'):
            pos = self._random_edge_position()
            elements.append({
                "type": "image_plane",
                "path": f"/{session_rel_path}/original_frame.png",
                "target_2d": pos,
                "depth_range": {"min": 8, "max": 15},
                "scale": 0.15,
                "rotation": random.choice(ROTATION_ANGLES),
                "opacity": random.uniform(0.5, 0.8)
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
                "opacity": random.uniform(0.15, 0.3)
            })

        # 5. 3D Text keywords - more varied placement
        keyword_positions = self._generate_keyword_positions(len(keywords[:5]))
        for i, keyword in enumerate(keywords[:5]):
            if len(keyword) > 2:
                pos = keyword_positions[i] if i < len(keyword_positions) else self._random_position()
                
                # Some keywords vertical, some diagonal, some horizontal
                rotation = self._select_text_rotation(i)
                
                elements.append({
                    "type": "text_3d",
                    "text": keyword.upper(),
                    "target_2d": pos,
                    "depth_range": {"min": 6 + i * 2, "max": 10 + i * 2},
                    "scale": random.uniform(0.06, 0.15),
                    "color": self._random_text_color(),
                    "rotation": rotation,
                    "metalness": random.uniform(0.2, 0.8),
                    "roughness": random.uniform(0.2, 0.6)
                })

        # 6. Found imagery - scattered throughout depth
        for i, img_path in enumerate(found_images[:8]):
            pos = self._random_position()
            elements.append({
                "type": "image_plane",
                "path": img_path,
                "target_2d": pos,
                "depth_range": {"min": 10 + i * 2, "max": 20 + i * 2},
                "scale": random.uniform(0.08, 0.25),
                "rotation": random.choice(ROTATION_ANGLES),
                "opacity": random.uniform(0.4, 0.9)
            })

        # 7. Multiple shader effects - varied and mood-appropriate
        selected_shaders = self.select_shaders_for_mood(mood, keywords, 4)
        
        for i, shader_name in enumerate(selected_shaders):
            pos = self._random_position() if i > 0 else {"x": 0.5 + random.uniform(-0.2, 0.2), "y": 0.5 + random.uniform(-0.2, 0.2)}
            
            shader_config = {
                "type": "shader_plane",
                "shader": shader_name,
                "target_2d": pos,
                "depth_range": {"min": 4 + i * 2, "max": 8 + i * 2},
                "scale": random.uniform(0.2, 0.4),
                "opacity": random.uniform(0.2, 0.5),
                "animated": True,
                "rotation": random.choice(ROTATION_ANGLES) if random.random() > 0.5 else 0
            }
            
            # Add color for certain shaders
            if shader_name in ['dreamBlur', 'kineticLiquid', 'ripple']:
                shader_config["color"] = random.choice(BOLD_COLORS)
            
            elements.append(shader_config)

        # 8. Diagonal color bars (like reference images)
        for _ in range(random.randint(1, 3)):
            angle = random.choice([30, 45, 60, -30, -45, -60, 90, -90])
            elements.append({
                "type": "shader_plane",
                "shader": "glitch" if mood == 'chaotic' else "scanLine",
                "target_2d": {"x": random.uniform(0.2, 0.8), "y": random.uniform(0.2, 0.8)},
                "depth_range": {"min": 2, "max": 4},
                "width": 15,
                "height": random.uniform(0.1, 0.4),
                "scale": 1.0,
                "opacity": random.uniform(0.3, 0.7),
                "color": random.choice(BOLD_COLORS),
                "angle": angle,
                "rotation": angle
            })

        # 9. Add vertical text strip for full transcription (like reference images)
        if session.transcription:
            # Left side vertical text
            elements.append({
                "type": "text_3d",
                "text": self._extract_key_phrase(session.transcription),
                "target_2d": {"x": 0.08, "y": 0.5},
                "depth_range": {"min": 8, "max": 12},
                "scale": 0.06,
                "color": "#FFFFFF",
                "rotation": -90,
                "depth": 0.02  # Thinner text
            })

        return elements

    def select_animation_preset(self, mood: str) -> str:
        """Select animation preset based on mood."""
        mood_presets = {
            'dreamy': ['dreamy', 'ethereal'],
            'chaotic': ['chaotic', 'aggressive'],
            'digital': ['chaotic', 'aggressive'],
            'organic': ['dreamy', 'meditative'],
            'aggressive': ['aggressive', 'chaotic'],
            'calm': ['meditative', 'dreamy']
        }
        return random.choice(mood_presets.get(mood, ['dreamy']))

    def select_emissive_color(self, mood: str) -> str:
        """Select emissive glow color based on mood."""
        mood_emissive = {
            'dreamy': '#8b5cf6',
            'chaotic': '#ff0000',
            'digital': '#00ff7f',
            'organic': '#00ff7f',
            'aggressive': '#ff4500',
            'calm': '#00ced1'
        }
        return mood_emissive.get(mood, '#ffffff')

    def _generate_keyword_positions(self, count: int) -> List[Dict]:
        """Generate varied positions for keywords."""
        positions = []
        
        # Create a more interesting layout
        zones = [
            # Left side
            {"x": 0.15, "y": 0.3}, {"x": 0.12, "y": 0.5}, {"x": 0.18, "y": 0.7},
            # Right side
            {"x": 0.85, "y": 0.25}, {"x": 0.88, "y": 0.6}, {"x": 0.82, "y": 0.8},
            # Top and bottom
            {"x": 0.35, "y": 0.12}, {"x": 0.65, "y": 0.15},
            {"x": 0.3, "y": 0.88}, {"x": 0.7, "y": 0.85},
            # Near center but offset
            {"x": 0.4, "y": 0.4}, {"x": 0.6, "y": 0.6}
        ]
        
        random.shuffle(zones)
        return zones[:count]

    def _select_text_rotation(self, index: int) -> int:
        """Select rotation for text based on position in sequence."""
        rotations = [
            0,      # Horizontal
            90,     # Vertical up
            -90,    # Vertical down
            45,     # Diagonal
            -45,    # Diagonal
            180,    # Upside down
            30,     # Slight angle
            -30     # Slight angle
        ]
        
        # More variety as we go
        if index == 0:
            return random.choice([0, 30, -30])
        elif index < 3:
            return random.choice([0, 45, -45, 30, -30])
        else:
            return random.choice(ROTATION_ANGLES)

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
        edge = random.choice(['top', 'bottom', 'left', 'right', 'corner'])

        if edge == 'top':
            return {"x": random.uniform(0.2, 0.8), "y": random.uniform(0.1, 0.25)}
        elif edge == 'bottom':
            return {"x": random.uniform(0.2, 0.8), "y": random.uniform(0.75, 0.9)}
        elif edge == 'left':
            return {"x": random.uniform(0.1, 0.25), "y": random.uniform(0.2, 0.8)}
        elif edge == 'right':
            return {"x": random.uniform(0.75, 0.9), "y": random.uniform(0.2, 0.8)}
        else:  # corner
            x = random.choice([random.uniform(0.1, 0.25), random.uniform(0.75, 0.9)])
            y = random.choice([random.uniform(0.1, 0.25), random.uniform(0.75, 0.9)])
            return {"x": x, "y": y}

    def _random_text_color(self) -> str:
        """Return white or a bold color for text."""
        if random.random() > 0.4:
            return "#FFFFFF"
        return random.choice(BOLD_COLORS)

    def _extract_key_phrase(self, transcription: str, max_length: int = 30) -> str:
        """Extract a key phrase from transcription for vertical text."""
        # Clean up transcription
        cleaned = transcription.strip().lower()
        
        # If short enough, use as-is
        if len(cleaned) <= max_length:
            return cleaned.upper()
        
        # Otherwise, extract first meaningful part
        words = cleaned.split()
        phrase = ""
        for word in words:
            if len(phrase) + len(word) + 1 <= max_length:
                phrase += word + " "
            else:
                break
        
        return phrase.strip().upper() or "DREAM"


def main():
    """Run enhanced composition generator."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate enhanced lookbook compositions')
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

    generator = CompositionGeneratorV2(
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
