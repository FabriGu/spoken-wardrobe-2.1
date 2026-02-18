#!/usr/bin/env python3
"""
keyword_extractor.py

Extracts keywords from user transcriptions using NLP.
Uses spaCy for POS tagging and noun/adjective extraction.
Falls back to simple tokenization if spaCy is not available.
"""

import re
from typing import List, Dict, Set
from collections import Counter

# Try to import spaCy, fall back to simple extraction
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("[KeywordExtractor] spaCy not available, using simple extraction")


class KeywordExtractor:
    """Extract keywords from transcriptions."""

    # Common stop words to filter out
    STOP_WORDS = {
        'want', 'please', 'make', 'give', 'get', 'like', 'think', 'really',
        'just', 'going', 'would', 'could', 'should', 'need', 'have', 'can',
        'some', 'yeah', 'okay', 'yes', 'no', 'oh', 'um', 'uh', 'hmm', 'hm',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'this', 'that', 'these', 'those', 'it', 'its', 'i', 'me', 'my',
        'you', 'your', 'we', 'our', 'they', 'their', 'he', 'she', 'him', 'her',
        'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'now', 'also', 'here', 'there', 'something', 'anything', 'nothing',
        'one', 'two', 'three', 'four', 'five', 'maybe', 'actually', 'know',
        'thing', 'stuff', 'sort', 'kind', 'lot', 'bit', 'way', 'right', 'sure'
    }

    # Fashion-related terms to prioritize
    FASHION_TERMS = {
        # Garments
        'shirt', 't-shirt', 'tshirt', 'dress', 'pants', 'jeans', 'jacket',
        'coat', 'skirt', 'sweater', 'hoodie', 'blouse', 'suit', 'vest',
        'shorts', 'leggings', 'cardigan', 'blazer', 'gown', 'robe', 'cape',
        'uniform', 'costume', 'outfit', 'armor', 'cloak',
        # Colors
        'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink',
        'black', 'white', 'gray', 'grey', 'brown', 'gold', 'silver',
        'turquoise', 'cyan', 'magenta', 'navy', 'crimson', 'scarlet',
        # Materials
        'silk', 'cotton', 'wool', 'leather', 'denim', 'velvet', 'satin',
        'lace', 'chiffon', 'sequin', 'metallic', 'shiny', 'matte',
        # Styles
        'casual', 'formal', 'elegant', 'vintage', 'modern', 'classic',
        'bohemian', 'gothic', 'punk', 'streetwear', 'sporty', 'luxury',
        'minimalist', 'maximalist', 'retro', 'futuristic',
        # Descriptors
        'beautiful', 'sexy', 'cute', 'cool', 'nice', 'fancy', 'simple',
        'colorful', 'bright', 'dark', 'light', 'bold', 'soft', 'loud',
        # Characters/themes
        'clown', 'princess', 'superhero', 'wizard', 'ninja', 'warrior',
        'angel', 'demon', 'fairy', 'vampire', 'zombie', 'robot', 'alien',
        'wedding', 'party', 'christmas', 'halloween', 'summer', 'winter'
    }

    def __init__(self, use_spacy: bool = True):
        self.nlp = None
        if use_spacy and SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("[KeywordExtractor] Using spaCy for extraction")
            except OSError:
                print("[KeywordExtractor] spaCy model not found, using simple extraction")
                print("  Install with: python -m spacy download en_core_web_sm")

    def extract(self, transcription: str) -> Dict:
        """
        Extract keywords from a transcription.

        Returns:
            Dict with:
                - primary: Main nouns (garments, objects)
                - modifiers: Adjectives (colors, styles)
                - all_keywords: Combined unique keywords
                - raw_text: Cleaned transcription
        """
        if not transcription or not transcription.strip():
            return {
                'primary': [],
                'modifiers': [],
                'all_keywords': [],
                'raw_text': ''
            }

        # Clean text
        text = self._clean_text(transcription)

        if self.nlp:
            return self._extract_with_spacy(text)
        else:
            return self._extract_simple(text)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Lowercase
        text = text.lower()

        # Remove repeated words (ASR artifacts like "red red red red")
        words = text.split()
        cleaned_words = []
        prev_word = None
        repeat_count = 0

        for word in words:
            if word == prev_word:
                repeat_count += 1
                if repeat_count < 3:  # Allow up to 2 repeats
                    cleaned_words.append(word)
            else:
                cleaned_words.append(word)
                repeat_count = 0
            prev_word = word

        text = ' '.join(cleaned_words)

        # Remove punctuation except hyphens
        text = re.sub(r'[^\w\s-]', ' ', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        return text

    def _extract_with_spacy(self, text: str) -> Dict:
        """Extract keywords using spaCy NLP."""
        doc = self.nlp(text)

        nouns = []
        adjectives = []

        for token in doc:
            lemma = token.lemma_.lower()

            # Skip stop words
            if lemma in self.STOP_WORDS:
                continue

            # Skip very short tokens
            if len(lemma) < 2:
                continue

            # Collect by POS
            if token.pos_ == 'NOUN':
                nouns.append(lemma)
            elif token.pos_ == 'ADJ':
                adjectives.append(lemma)
            # Also catch proper nouns that might be fashion terms
            elif token.pos_ == 'PROPN' and lemma.lower() in self.FASHION_TERMS:
                nouns.append(lemma.lower())

        # Deduplicate while preserving order
        nouns = list(dict.fromkeys(nouns))
        adjectives = list(dict.fromkeys(adjectives))

        # Prioritize fashion-related terms
        nouns = self._prioritize_fashion(nouns)
        adjectives = self._prioritize_fashion(adjectives)

        all_keywords = list(dict.fromkeys(adjectives + nouns))

        return {
            'primary': nouns[:5],
            'modifiers': adjectives[:5],
            'all_keywords': all_keywords[:10],
            'raw_text': text
        }

    def _extract_simple(self, text: str) -> Dict:
        """Simple keyword extraction without NLP."""
        words = text.split()

        # Filter stop words
        filtered = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]

        # Count frequencies
        counter = Counter(filtered)

        # Separate likely adjectives (colors) and nouns
        adjectives = [w for w, _ in counter.most_common()
                     if w in self.FASHION_TERMS and self._is_likely_adjective(w)]
        nouns = [w for w, _ in counter.most_common()
                if w in self.FASHION_TERMS and not self._is_likely_adjective(w)]

        # Add any remaining high-frequency words
        remaining = [w for w, c in counter.most_common(10)
                    if w not in adjectives and w not in nouns and c > 1]

        all_keywords = list(dict.fromkeys(adjectives + nouns + remaining))

        return {
            'primary': nouns[:5] if nouns else remaining[:3],
            'modifiers': adjectives[:5],
            'all_keywords': all_keywords[:10],
            'raw_text': text
        }

    def _is_likely_adjective(self, word: str) -> bool:
        """Check if word is likely an adjective (color, style descriptor)."""
        color_words = {
            'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink',
            'black', 'white', 'gray', 'grey', 'brown', 'gold', 'silver',
            'turquoise', 'cyan', 'magenta', 'navy', 'crimson', 'scarlet'
        }
        style_words = {
            'casual', 'formal', 'elegant', 'vintage', 'modern', 'classic',
            'beautiful', 'sexy', 'cute', 'cool', 'nice', 'fancy', 'simple',
            'colorful', 'bright', 'dark', 'light', 'bold', 'soft', 'shiny'
        }
        return word in color_words or word in style_words

    def _prioritize_fashion(self, words: List[str]) -> List[str]:
        """Sort words to prioritize fashion-related terms."""
        fashion = [w for w in words if w in self.FASHION_TERMS]
        other = [w for w in words if w not in self.FASHION_TERMS]
        return fashion + other


def main():
    """Test keyword extraction on sample transcriptions."""
    extractor = KeywordExtractor()

    test_transcriptions = [
        "Can I get a red t-shirt please? One red t-shirt right now please.",
        "Make me clown. Clownify me.",
        "Nice wedding dress.",
        "get a red t-shirt please. I think that's a really nice red t-shirt.",
        "a red or or warriors armor.",
        "Where a red dress? Gold needs a red dress sexy red dress",
        "Red, red, red, red, red, red, red, red",  # ASR artifact
        "I want a blue elegant gown with silver sequins"
    ]

    print("=== Keyword Extraction Test ===\n")

    for transcription in test_transcriptions:
        result = extractor.extract(transcription)
        print(f"Input: \"{transcription[:50]}...\"" if len(transcription) > 50 else f"Input: \"{transcription}\"")
        print(f"  Primary: {result['primary']}")
        print(f"  Modifiers: {result['modifiers']}")
        print(f"  All: {result['all_keywords']}")
        print()


if __name__ == '__main__':
    main()
