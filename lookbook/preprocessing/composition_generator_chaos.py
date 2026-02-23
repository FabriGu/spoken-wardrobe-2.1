#!/usr/bin/env python3
"""
composition_generator_chaos.py

MAXIMUM CHAOS version - Dense, overlapping, noisy compositions.
Embraces visual noise as aesthetic.
"""

import os
import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

from session_scanner import SessionScanner, Session
from keyword_extractor import KeywordExtractor


# Extended color palette for maximum visual noise
ALL_COLORS = [
    "#FF1493", "#00CED1", "#FFD700", "#FF4500", "#9400D3",
    "#00FF7F", "#FF6347", "#1E90FF", "#FF69B4", "#32CD32",
    "#8b5cf6", "#ec4899", "#000000", "#FFFFFF", "#FF0000",
    "#00FFFF", "#FFFF00", "#FF00FF", "#800080", "#008000",
    "#800000", "#808000", "#008080", "#C0C0C0", "#808080"
]

# All available shaders
ALL_SHADERS = [
    'dreamBlur', 'glitch', 'kineticLiquid', 'chromatic',
    'noiseField', 'scanLine', 'voronoi', 'particleCloud',
    'holographic', 'dataMosh', 'ripple', 'mandala', 'glow', 'diagonal'
]

# Animation presets
ANIMATION_PRESETS = ['dreamy', 'chaotic', 'ethereal', 'aggressive', 'meditative']


@dataclass
class CompositionConfig:
    """Configuration for a single chaotic composition."""
    id: str
    transcription: str
    keywords: List[str]
    background: Dict
    camera: Dict
    elements: List[Dict]


class ChaosCompositionGenerator:
    """Generate MAXIMUM CHAOS composition configs."""

    def __init__(self, sessions_path: str, output_path: str):
        self.sessions_path = Path(sessions_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.scanner = SessionScanner(str(self.sessions_path))
        self.extractor = KeywordExtractor()

    def generate_all(self):
        """Generate chaotic composition configs for all sessions."""
        self.scanner.scan()
        sessions = self.scanner.get_sessions_with_mesh()

        print(f"\n[ChaosGenerator] Generating MAXIMUM CHAOS for {len(sessions)} sessions")

        configs = []
        composition_ids = []

        for i, session in enumerate(sessions):
            print(f"\n[{i+1}/{len(sessions)}] CHAOS for session {session.id}")

            config = self.generate_chaos_composition(session)

            if config:
                config_path = self.output_path / f"{session.id}.json"
                with open(config_path, 'w') as f:
                    json.dump(asdict(config), f, indent=2)

                configs.append(config)
                composition_ids.append(session.id)
                print(f"  Elements: {len(config.elements)} | Keywords: {config.keywords[:3]}")

        # Save index
        index_path = self.output_path / "index.json"
        with open(index_path, 'w') as f:
            json.dump(composition_ids, f, indent=2)

        print(f"\n[ChaosGenerator] Generated {len(configs)} chaotic compositions")
        return configs

    def generate_chaos_composition(self, session: Session) -> Optional[CompositionConfig]:
        """Generate a single MAXIMUM CHAOS composition."""
        if not session.has_mesh:
            return None

        keywords = self.extractor.extract(session.transcription or "")['all_keywords']
        mood = self.detect_mood(keywords)
        
        # Generate chaotic elements
        elements = self._generate_chaos_elements(session, keywords, mood)
        
        # Chaotic background
        background_color = random.choice(ALL_COLORS)
        
        # Random camera position for varied perspective
        camera_pos = [
            random.uniform(-2, 2),
            random.uniform(-1, 1),
            random.uniform(8, 12)
        ]

        return CompositionConfig(
            id=session.id,
            transcription=session.transcription or "",
            keywords=keywords,
            background={"color": background_color},
            camera={
                "position": camera_pos,
                "fov": random.randint(45, 60),
                "target": [random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 0]
            },
            elements=elements
        )

    def detect_mood(self, keywords: List[str]) -> str:
        """Detect mood from keywords."""
        chaos_words = ['chaos', 'crazy', 'wild', 'mess', 'angry', 'loud', 'hard']
        calm_words = ['peace', 'calm', 'soft', 'gentle', 'quiet', 'dream']
        
        chaos_score = sum(1 for kw in keywords if any(c in kw.lower() for c in chaos_words))
        calm_score = sum(1 for kw in keywords if any(c in kw.lower() for c in calm_words))
        
        if chaos_score > calm_score:
            return 'chaotic'
        elif calm_score > chaos_score:
            return 'calm'
        return random.choice(['chaotic', 'dreamy', 'digital'])

    def _generate_chaos_elements(self, session: Session, keywords: List[str], mood: str) -> List[Dict]:
        """Generate MAXIMUM CHAOS elements - dense, overlapping, noisy."""
        elements = []
        session_rel_path = f"comfyui_generated_mesh/{session.id}"
        
        # 1. CENTER: Animated mesh with glow
        if session.files.get('clothing_mesh'):
            elements.append({
                "type": "glb_mesh",
                "path": f"/{session_rel_path}/clothing_mesh.glb",
                "target_2d": {"x": 0.5 + random.uniform(-0.1, 0.1), "y": 0.5 + random.uniform(-0.1, 0.1)},
                "depth_range": {"min": 3, "max": 5},
                "scale": random.uniform(0.3, 0.45),
                "animation": True,
                "animationPreset": random.choice(ANIMATION_PRESETS),
                "emissive": random.choice(ALL_COLORS),
                "wireframe": random.random() > 0.7  # Sometimes wireframe
            })

        # 2. MANY IMAGES - Scatter everywhere, heavy overlap
        image_sources = []
        if session.files.get('original_frame'):
            image_sources.append(f"/{session_rel_path}/original_frame.png")
        if session.files.get('generated_clothing'):
            image_sources.append(f"/{session_rel_path}/generated_clothing.png")
        if session.files.get('mask'):
            image_sources.append(f"/{session_rel_path}/mask.png")
        
        # Add each image multiple times at different positions (overlapping)
        for img_path in image_sources:
            for _ in range(random.randint(2, 5)):  # Multiple instances
                elements.append({
                    "type": "image_plane",
                    "path": img_path,
                    "target_2d": self._chaos_position(),
                    "depth_range": {"min": random.uniform(2, 8), "max": random.uniform(8, 20)},
                    "scale": random.uniform(0.1, 0.35),
                    "rotation": random.choice([0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90, 120, -120, 150, -150, 180]),
                    "opacity": random.uniform(0.3, 0.9),
                    "billboard": random.random() > 0.3
                })

        # 3. MANY SHADERS - Cover the space with shader effects
        num_shaders = random.randint(6, 12)  # Lots of shaders
        for i in range(num_shaders):
            shader = random.choice(ALL_SHADERS)
            elements.append({
                "type": "shader_plane",
                "shader": shader,
                "target_2d": self._chaos_position(),
                "depth_range": {"min": random.uniform(1, 6), "max": random.uniform(6, 15)},
                "scale": random.uniform(0.15, 0.5),
                "opacity": random.uniform(0.2, 0.7),
                "animated": True,
                "rotation": random.choice([0, 45, -45, 90, -90, 30, -30, 60, -60]),
                "color": random.choice(ALL_COLORS) if shader in ['dreamBlur', 'glow', 'ripple'] else None
            })

        # 4. DIAGONAL BARS - Chaotic strips cutting through
        for _ in range(random.randint(2, 5)):
            elements.append({
                "type": "shader_plane",
                "shader": random.choice(['diagonal', 'glitch', 'scanLine']),
                "target_2d": {"x": random.uniform(0.2, 0.8), "y": random.uniform(0.2, 0.8)},
                "depth_range": {"min": 1, "max": 3},
                "width": random.uniform(8, 20),
                "height": random.uniform(0.05, 0.3),
                "scale": 1.0,
                "opacity": random.uniform(0.3, 0.8),
                "color": random.choice(ALL_COLORS),
                "angle": random.choice([20, 30, 45, 60, 70, -20, -30, -45, -60, -70, 90, -90]),
                "rotation": random.choice([20, 30, 45, 60, 70, -20, -30, -45, -60, -70])
            })

        # 5. MANY TEXT ELEMENTS - Keywords everywhere, all rotations
        all_texts = keywords[:8]  # Use more keywords
        if session.transcription:
            # Add fragmented phrases
            words = session.transcription.split()
            for i in range(0, min(len(words), 3)):
                phrase = ' '.join(words[i:i+3]).upper()
                if len(phrase) > 3:
                    all_texts.append(phrase)
        
        for i, text in enumerate(all_texts):
            if len(text) > 2:
                # Varied rotations: horizontal, vertical, diagonal, upside-down
                rotation = random.choice([
                    0, 0,  # Horizontal (more common)
                    90, -90,  # Vertical
                    45, -45, 60, -60,  # Diagonal
                    180,  # Upside down
                    30, -30, 120, -120  # Other angles
                ])
                
                elements.append({
                    "type": "text_3d",
                    "text": text.upper()[:15],  # Limit length
                    "target_2d": self._chaos_position(),
                    "depth_range": {"min": random.uniform(3, 10), "max": random.uniform(10, 20)},
                    "scale": random.uniform(0.04, 0.12),
                    "color": random.choice(["#FFFFFF"] + ALL_COLORS[:12]),
                    "rotation": rotation,
                    "metalness": random.uniform(0.1, 0.9),
                    "roughness": random.uniform(0.1, 0.8),
                    "emissive": random.choice([None, random.choice(ALL_COLORS[:10])])
                })

        # 6. VERTICAL TEXT STRIP - Full transcription on edge
        if session.transcription:
            # Left side vertical text
            elements.append({
                "type": "text_3d",
                "text": session.transcription[:40].upper(),  # First 40 chars
                "target_2d": {"x": random.uniform(0.03, 0.08), "y": 0.5},
                "depth_range": {"min": 5, "max": 12},
                "scale": 0.05,
                "color": random.choice(["#FFFFFF", "#000000", "#FF1493", "#00CED1"]),
                "rotation": -90,
                "depth": 0.02
            })
            
            # Right side vertical text (upside down)
            elements.append({
                "type": "text_3d",
                "text": session.transcription[-40:].upper()[::-1],  # Last 40 chars reversed
                "target_2d": {"x": random.uniform(0.92, 0.97), "y": 0.5},
                "depth_range": {"min": 6, "max": 14},
                "scale": 0.04,
                "color": random.choice(["#FFFFFF", "#FF69B4", "#32CD32"]),
                "rotation": 90
            })

        # 7. ON-DEMAND IMAGERY - URLs for dynamic loading
        # These will be fetched client-side based on keywords
        for keyword in keywords[:5]:
            # Unsplash random with keyword
            img_url = f"https://source.unsplash.com/random/400x400?{keyword.replace(' ', '')}"
            elements.append({
                "type": "image_plane",
                "path": img_url,  # Direct URL - fetched on demand
                "target_2d": self._chaos_position(),
                "depth_range": {"min": random.uniform(8, 15), "max": random.uniform(15, 25)},
                "scale": random.uniform(0.1, 0.25),
                "rotation": random.choice([0, 45, -45, 90, -90, 180]),
                "opacity": random.uniform(0.4, 0.8),
                "unlit": True,
                "crossOrigin": "anonymous"
            })

        # Shuffle elements so depth order is random (more chaos)
        random.shuffle(elements)
        
        return elements

    def _chaos_position(self) -> Dict:
        """Generate chaotic position - anywhere on screen, including center."""
        # Bias toward edges but allow center overlap
        if random.random() > 0.3:
            # Edge-biased
            edge = random.choice(['top', 'bottom', 'left', 'right', 'center'])
            if edge == 'top':
                return {"x": random.uniform(0.1, 0.9), "y": random.uniform(0.05, 0.35)}
            elif edge == 'bottom':
                return {"x": random.uniform(0.1, 0.9), "y": random.uniform(0.65, 0.95)}
            elif edge == 'left':
                return {"x": random.uniform(0.05, 0.35), "y": random.uniform(0.1, 0.9)}
            elif edge == 'right':
                return {"x": random.uniform(0.65, 0.95), "y": random.uniform(0.1, 0.9)}
            else:  # center-ish
                return {"x": random.uniform(0.3, 0.7), "y": random.uniform(0.3, 0.7)}
        else:
            # Truly random anywhere
            return {"x": random.uniform(0.05, 0.95), "y": random.uniform(0.05, 0.95)}


def main():
    """Run chaos generator."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate MAXIMUM CHAOS compositions')
    parser.add_argument('--sessions', '-s',
                       default='../../comfyui_generated_mesh',
                       help='Path to sessions folder')
    parser.add_argument('--output', '-o',
                       default='../compositions',
                       help='Output directory')

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    sessions_path = (script_dir / args.sessions).resolve()
    output_path = (script_dir / args.output).resolve()

    generator = ChaosCompositionGenerator(
        str(sessions_path),
        str(output_path)
    )

    generator.generate_all()


if __name__ == '__main__':
    main()
