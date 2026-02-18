#!/usr/bin/env python3
"""
found_imagery_fetcher.py

Fetches found imagery from the internet based on keywords.
Uses free APIs: Unsplash Source, Pexels, Wikimedia Commons.
"""

import os
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote
import hashlib

# Try to import requests, make it optional
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[FoundImageryFetcher] requests not available, image fetching disabled")


class FoundImageryFetcher:
    """Fetch images from various free sources."""

    def __init__(self, output_dir: str, cache_dir: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Optional cache to avoid re-downloading
        self.cache_dir = Path(cache_dir) if cache_dir else self.output_dir / '.cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds

        # Pexels API key (optional, from environment)
        self.pexels_api_key = os.environ.get('PEXELS_API_KEY')

    def fetch_for_keywords(self, keywords: List[str], count: int = 10,
                          session_id: str = None) -> List[str]:
        """
        Fetch images for a list of keywords.

        Args:
            keywords: List of search keywords
            count: Total number of images to fetch
            session_id: Optional session ID for organizing output

        Returns:
            List of downloaded image paths
        """
        if not REQUESTS_AVAILABLE:
            print("[FoundImageryFetcher] requests module not available, skipping image fetch")
            return []

        if not keywords:
            print("[FoundImageryFetcher] No keywords provided")
            return []

        # Create session-specific output directory
        if session_id:
            output_path = self.output_dir / session_id
        else:
            output_path = self.output_dir

        output_path.mkdir(parents=True, exist_ok=True)

        downloaded = []
        images_per_keyword = max(1, count // len(keywords))

        for keyword in keywords:
            # Try multiple sources for each keyword
            keyword_images = self._fetch_for_keyword(
                keyword,
                images_per_keyword,
                output_path
            )
            downloaded.extend(keyword_images)

            if len(downloaded) >= count:
                break

        print(f"[FoundImageryFetcher] Downloaded {len(downloaded)} images")
        return downloaded[:count]

    def _fetch_for_keyword(self, keyword: str, count: int,
                          output_path: Path) -> List[str]:
        """Fetch images for a single keyword."""
        images = []

        # Try Unsplash Source first (no API key needed)
        unsplash_images = self._fetch_unsplash(keyword, count, output_path)
        images.extend(unsplash_images)

        # If we need more, try Pexels (requires API key)
        if len(images) < count and self.pexels_api_key:
            remaining = count - len(images)
            pexels_images = self._fetch_pexels(keyword, remaining, output_path)
            images.extend(pexels_images)

        return images

    def _fetch_unsplash(self, keyword: str, count: int,
                       output_path: Path) -> List[str]:
        """
        Fetch from Unsplash Source.
        Free, no API key needed, but random images.
        """
        images = []
        base_url = "https://source.unsplash.com/random/800x600"

        for i in range(count):
            self._rate_limit()

            try:
                # Add keyword and random seed to get different images
                url = f"{base_url}?{quote(keyword)}&sig={i}"

                response = requests.get(url, timeout=15, allow_redirects=True)

                if response.status_code == 200:
                    # Generate filename from keyword and index
                    safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
                    filename = f"unsplash_{safe_keyword}_{i}.jpg"
                    filepath = output_path / filename

                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    images.append(str(filepath))
                    print(f"  Downloaded: {filename}")

            except Exception as e:
                print(f"  Failed to fetch from Unsplash for '{keyword}': {e}")

        return images

    def _fetch_pexels(self, keyword: str, count: int,
                     output_path: Path) -> List[str]:
        """
        Fetch from Pexels API.
        Requires API key (free tier: 200 requests/hour).
        """
        if not self.pexels_api_key:
            return []

        images = []
        url = "https://api.pexels.com/v1/search"

        headers = {
            "Authorization": self.pexels_api_key
        }

        params = {
            "query": keyword,
            "per_page": min(count, 15),  # Pexels max is 80
            "page": 1
        }

        self._rate_limit()

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()

                for i, photo in enumerate(data.get('photos', [])[:count]):
                    # Get medium size image
                    img_url = photo['src'].get('medium') or photo['src'].get('small')

                    if img_url:
                        img_response = requests.get(img_url, timeout=15)

                        if img_response.status_code == 200:
                            safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
                            filename = f"pexels_{safe_keyword}_{i}.jpg"
                            filepath = output_path / filename

                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)

                            images.append(str(filepath))
                            print(f"  Downloaded: {filename}")

            elif response.status_code == 429:
                print("  Pexels rate limit exceeded")

        except Exception as e:
            print(f"  Failed to fetch from Pexels for '{keyword}': {e}")

        return images

    def _fetch_wikimedia(self, keyword: str, count: int,
                        output_path: Path) -> List[str]:
        """
        Fetch from Wikimedia Commons.
        Free, no API key, public domain images.
        """
        images = []
        url = "https://commons.wikimedia.org/w/api.php"

        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,  # File namespace
            "gsrsearch": f"filetype:bitmap {keyword}",
            "gsrlimit": count,
            "prop": "imageinfo",
            "iiprop": "url|size",
            "iiurlwidth": 800
        }

        self._rate_limit()

        try:
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                pages = data.get('query', {}).get('pages', {})

                for i, (_, page) in enumerate(pages.items()):
                    if i >= count:
                        break

                    imageinfo = page.get('imageinfo', [{}])[0]
                    img_url = imageinfo.get('thumburl') or imageinfo.get('url')

                    if img_url:
                        img_response = requests.get(img_url, timeout=15)

                        if img_response.status_code == 200:
                            safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
                            filename = f"wikimedia_{safe_keyword}_{i}.jpg"
                            filepath = output_path / filename

                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)

                            images.append(str(filepath))
                            print(f"  Downloaded: {filename}")

        except Exception as e:
            print(f"  Failed to fetch from Wikimedia for '{keyword}': {e}")

        return images

    def _rate_limit(self):
        """Enforce minimum time between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def get_cache_path(self, url: str) -> Path:
        """Get cache path for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"


def main():
    """Test the fetcher."""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch found imagery')
    parser.add_argument('keywords', nargs='+', help='Keywords to search')
    parser.add_argument('--output', '-o', default='./found_images',
                       help='Output directory')
    parser.add_argument('--count', '-n', type=int, default=5,
                       help='Number of images per keyword')

    args = parser.parse_args()

    fetcher = FoundImageryFetcher(args.output)
    images = fetcher.fetch_for_keywords(args.keywords, args.count)

    print(f"\nDownloaded {len(images)} images:")
    for img in images:
        print(f"  {img}")


if __name__ == '__main__':
    main()
