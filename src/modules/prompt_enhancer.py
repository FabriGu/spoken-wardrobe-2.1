"""
Prompt Enhancer for Spoken Wardrobe

Transforms user clothing descriptions into creative, artistic prompts
that generate interesting, bizarre, and non-sexualized fashion designs.

The enhancer uses either:
1. OpenAI API (if OPENAI_API_KEY is set) for intelligent prompt rewriting
2. Rule-based enhancement as fallback

The goal is to take simple descriptions like "a red dress" and transform
them into creative prompts like "avant-garde crimson gown with geometric
origami folds and asymmetric hemline, deconstructed haute couture"

Usage:
    from modules.prompt_enhancer import PromptEnhancer

    enhancer = PromptEnhancer()
    enhanced = enhancer.enhance("a blue dress")
    # Returns creative, artistic prompt
"""

import os
import random
from typing import Optional

# Try to import OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class PromptEnhancer:
    """
    Enhances clothing prompts to be more creative, artistic, and non-sexualized.
    """

    # Words/phrases to avoid in prompts (sexualized or problematic)
    BLOCKED_TERMS = [
        'sexy', 'seductive', 'revealing', 'skimpy', 'tight', 'form-fitting',
        'low-cut', 'cleavage', 'busty', 'curvy', 'provocative', 'sensual',
        'lingerie', 'bikini', 'underwear', 'nude', 'naked', 'see-through',
        'transparent', 'sheer', 'skin-tight', 'bodycon', 'mini skirt',
        'hot', 'attractive', 'beautiful woman', 'pretty girl', 'gorgeous',
        'feminine figure', 'hourglass', 'voluptuous',
        # Additional blocked terms for safety
        'bare', 'exposed', 'topless', 'bottomless', 'bra', 'panties',
        'thong', 'swimsuit', 'crop top', 'mini', 'short shorts', 'booty',
        'nsfw', 'erotic', 'sexual', 'sensuous', 'alluring', 'flirty'
    ]

    # Creative style modifiers to add artistic flair
    CREATIVE_STYLES = [
        'avant-garde', 'deconstructed', 'sculptural', 'architectural',
        'biomimetic', 'neo-futuristic', 'post-apocalyptic chic',
        'retro-futurism', 'cyberpunk utilitarian', 'organic minimalism',
        'brutalist fashion', 'parametric design', 'origami-inspired',
        'wearable art', 'geometric abstraction', 'kinetic fashion',
        'sustainable couture', 'upcycled luxury', 'digital glitch aesthetic',
        'maximalist baroque', 'neo-gothic revival', 'space age mod'
    ]

    # Interesting texture/material descriptors
    TEXTURES = [
        'iridescent', 'holographic', 'matte', 'crinkled', 'pleated',
        'quilted', 'embossed', 'laser-cut', 'hand-woven', 'distressed',
        'metallic thread', 'raw edge', 'frayed', 'layered mesh',
        'structured canvas', 'recycled textile', 'bio-fabric',
        'mushroom leather', 'pineapple fiber', '3D printed elements'
    ]

    # Structural/design elements
    DESIGN_ELEMENTS = [
        'asymmetric hemline', 'exaggerated shoulders', 'oversized silhouette',
        'dramatic draping', 'unexpected cutouts', 'modular components',
        'transformable panels', 'integrated pockets', 'statement collar',
        'sculptural sleeves', 'architectural pleats', 'geometric panels',
        'deconstructed seams', 'exposed construction', 'floating layers',
        'cocoon shape', 'bell silhouette', 'trapeze form'
    ]

    # Color descriptions (more interesting than basic colors)
    COLOR_ENHANCEMENTS = {
        'red': ['crimson', 'burgundy', 'rust', 'terracotta', 'vermillion', 'oxblood'],
        'blue': ['cobalt', 'cerulean', 'indigo', 'prussian blue', 'midnight', 'petrol'],
        'green': ['emerald', 'forest', 'sage', 'olive', 'jade', 'chartreuse'],
        'yellow': ['mustard', 'saffron', 'ochre', 'golden', 'amber', 'canary'],
        'purple': ['aubergine', 'plum', 'lavender', 'violet', 'mauve', 'grape'],
        'pink': ['dusty rose', 'coral', 'salmon', 'blush', 'fuchsia', 'magenta'],
        'orange': ['tangerine', 'burnt orange', 'peach', 'apricot', 'copper'],
        'black': ['jet black', 'charcoal', 'onyx', 'obsidian', 'ink black'],
        'white': ['ivory', 'cream', 'pearl', 'off-white', 'alabaster', 'bone'],
        'brown': ['chocolate', 'caramel', 'cognac', 'chestnut', 'mahogany', 'taupe'],
        'gray': ['slate', 'ash', 'dove gray', 'graphite', 'silver', 'heather']
    }

    # System prompt for LLM-based enhancement
    LLM_SYSTEM_PROMPT = """You are a visionary fashion alchemist who transforms mundane clothing descriptions into extraordinary, impossible garments that could only exist in dreams.

YOUR MISSION: Take the user's simple clothing idea and reimagine it as something that defies physics, blends genres, or transcends reality.

TRANSFORMATION RULES:
1. Push boundaries: Add surreal, fantastical, or sci-fi elements that challenge what clothing CAN be
2. Mix unexpected materials: Living moss + chrome, liquid mercury + silk, bioluminescent fibers, crystallized smoke, woven starlight
3. Add impossible physics: Gravity-defying drapes, clothes that shimmer between dimensions, fabrics that flow upward
4. Include architectural/organic hybrids: Garments that grow, breathe, transform, or seem alive
5. Reference art movements: Surrealism, Art Nouveau, Brutalism, Cyberpunk, Baroque excess
6. Think Alexander McQueen meets Iris van Herpen meets fever dreams
7. Keep it wearable but EXTRAORDINARY - this is haute couture from another dimension

FORBIDDEN:
- Mundane, realistic, or ordinary descriptions
- Sexualized or revealing designs
- Body type descriptions
- Simple color-only changes ("red dress" is boring, transform it completely)

OUTPUT: One vivid paragraph (60-80 words) describing the impossible garment. Focus on materials, textures, movement, and surreal details that make it feel like it stepped out of a dream.

EXAMPLES:
"red dress" → "A flowing crimson gown that appears to be woven from captured sunset light, with panels of crystallized rose petals cascading into a hem of perpetual mist. The bodice features biomechanical ribbing in burnished copper that pulses gently, while the sleeves dissolve into thousands of hovering silk fragments that reform with each gesture."

"blue jacket" → "An architectural indigo jacket constructed from folded origami steel and living moss patches that slowly creep across the surface. The shoulders extend into impossible geometric spires that cast prismatic shadows, while the interior is lined with a fabric that displays a slowly swirling galaxy pattern."

"simple shirt" → "A luminescent tunic woven from phosphorescent spider silk and shattered mirror fragments, featuring collar spines that extend into delicate antennae. The fabric shifts between states of matter, appearing liquid when still but solidifying into angular crystalline forms when in motion."
"""

    def __init__(self, use_llm: bool = True, openai_api_key: Optional[str] = None):
        """
        Initialize the prompt enhancer.

        Args:
            use_llm: Whether to try using LLM for enhancement (falls back to rules if unavailable)
            openai_api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.use_llm = use_llm
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        self.llm_available = OPENAI_AVAILABLE and bool(self.openai_api_key)

        if self.use_llm and self.llm_available:
            openai.api_key = self.openai_api_key
            print("[PromptEnhancer] OpenAI API available for prompt enhancement")
        else:
            print("[PromptEnhancer] Using rule-based prompt enhancement")

    def enhance(self, prompt: str) -> str:
        """
        Enhance a clothing prompt to be more creative and non-sexualized.

        Args:
            prompt: User's raw clothing description

        Returns:
            Enhanced prompt for image generation
        """
        # First, clean the prompt of any problematic terms
        cleaned = self._remove_blocked_terms(prompt)

        # Try LLM enhancement if available
        if self.use_llm and self.llm_available:
            try:
                enhanced = self._enhance_with_llm(cleaned)
                if enhanced:
                    return enhanced
            except Exception as e:
                print(f"[PromptEnhancer] LLM enhancement failed: {e}, using rules")

        # Fall back to rule-based enhancement
        return self._enhance_with_rules(cleaned)

    def _remove_blocked_terms(self, prompt: str) -> str:
        """Remove any blocked/problematic terms from the prompt."""
        result = prompt.lower()
        for term in self.BLOCKED_TERMS:
            result = result.replace(term.lower(), '')
        # Clean up extra spaces
        result = ' '.join(result.split())
        return result if result.strip() else prompt

    def _enhance_with_llm(self, prompt: str) -> Optional[str]:
        """Use OpenAI API to enhance the prompt creatively."""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Enhance this clothing prompt: {prompt}"}
                ],
                max_tokens=150,
                temperature=0.8
            )
            enhanced = response.choices[0].message.content.strip()
            print(f"[PromptEnhancer] LLM enhanced: '{prompt}' → '{enhanced}'")
            return enhanced
        except Exception as e:
            print(f"[PromptEnhancer] OpenAI API error: {e}")
            return None

    def _enhance_with_rules(self, prompt: str) -> str:
        """Use rule-based enhancement for creative prompts."""
        prompt_lower = prompt.lower()

        # Enhance colors
        for basic_color, fancy_colors in self.COLOR_ENHANCEMENTS.items():
            if basic_color in prompt_lower:
                fancy = random.choice(fancy_colors)
                prompt = prompt_lower.replace(basic_color, fancy, 1)
                prompt_lower = prompt.lower()

        # Add creative style
        style = random.choice(self.CREATIVE_STYLES)
        texture = random.choice(self.TEXTURES)
        design = random.choice(self.DESIGN_ELEMENTS)

        # Build enhanced prompt
        enhanced_parts = [
            style,
            prompt.strip(),
            f"with {texture} fabric",
            f"featuring {design}",
            "artistic construction",
            "unconventional silhouette",
            "wearable art aesthetic"
        ]

        enhanced = ', '.join(enhanced_parts)

        print(f"[PromptEnhancer] Rule-enhanced: '{prompt}' → '{enhanced}'")
        return enhanced


# Quick test
if __name__ == "__main__":
    enhancer = PromptEnhancer(use_llm=False)  # Test rules only

    test_prompts = [
        "a red dress",
        "blue jeans",
        "white shirt",
        "leather jacket",
        "summer dress",
        "formal suit"
    ]

    print("\n=== Prompt Enhancement Test ===\n")
    for prompt in test_prompts:
        enhanced = enhancer.enhance(prompt)
        print(f"Original: {prompt}")
        print(f"Enhanced: {enhanced}")
        print("-" * 50)
