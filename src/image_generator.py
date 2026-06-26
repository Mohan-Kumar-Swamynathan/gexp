#!/usr/bin/env python3
"""
Image generator — fetches one Ghibli-style image per scene from pollinations.ai.
Free, no API key, no login.
Falls back to PIL gradient on failure.
"""

import hashlib
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Dict

log = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/{prompt}"
TIMEOUT   = 60
RETRIES   = 3
RETRY_WAIT = 4  # seconds between retries

# Ghibli base suffix appended to every image prompt
GHIBLI_SUFFIX = (
    "studio ghibli style, hayao miyazaki, hand-drawn anime, "
    "soft watercolor painting, detailed natural background, "
    "warm cinematic lighting, painterly texture, "
    "high quality anime illustration, no text, no watermark"
)

NEGATIVE = (
    "realistic photo, 3d render, blurry, ugly, nsfw, "
    "text, watermark, western cartoon, low quality, dark"
)


def _build_url(prompt: str, width: int, height: int, seed: int) -> str:
    full_prompt = f"{prompt}, {GHIBLI_SUFFIX}"
    encoded = urllib.parse.quote(full_prompt)
    return (
        f"{POLLINATIONS_BASE.format(prompt=encoded)}"
        f"?width={width}&height={height}&nologo=true&seed={seed}&model=flux"
    )


def fetch_image(prompt: str, output_path: str,
                width: int = 768, height: int = 432) -> str:
    """
    Fetch a Ghibli-style image for the given prompt.
    Saves to output_path. Returns output_path.
    """
    seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % 99999
    url  = _build_url(prompt, width, height, seed)

    for attempt in range(RETRIES):
        try:
            log.info(f"Fetching image (attempt {attempt+1}): {prompt[:60]}...")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()

            if len(data) < 5000:
                raise ValueError(f"Response too small: {len(data)} bytes")

            Path(output_path).write_bytes(data)
            log.info(f"Image saved ({len(data)//1024}KB) → {output_path}")
            return output_path

        except Exception as e:
            log.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt < RETRIES - 1:
                time.sleep(RETRY_WAIT)

    log.warning("All image fetch attempts failed — using PIL fallback")
    return _fallback_image(prompt, output_path, width, height)


def _fallback_image(text: str, output_path: str,
                    width: int, height: int) -> str:
    """Pastel gradient fallback when pollinations is unreachable."""
    from PIL import Image, ImageFilter

    PALETTES = [
        ((120, 180, 100), (60, 120, 60)),
        ((255, 160, 80),  (200, 80, 50)),
        ((135, 206, 235), (100, 180, 210)),
        ((80, 60, 140),   (140, 80, 160)),
        ((180, 220, 130), (90, 150, 80)),
    ]
    h   = int(hashlib.md5(text.encode()).hexdigest()[:4], 16)
    top, bot = PALETTES[h % len(PALETTES)]

    img = Image.new("RGB", (width, height))
    px  = img.load()
    for y in range(height):
        t = y / height
        for x in range(width):
            px[x, y] = (
                int(top[0] * (1-t) + bot[0] * t),
                int(top[1] * (1-t) + bot[1] * t),
                int(top[2] * (1-t) + bot[2] * t),
            )
    img.filter(ImageFilter.GaussianBlur(3)).save(output_path)
    log.info(f"Fallback gradient image → {output_path}")
    return output_path


def fetch_all_scenes(scenes: List[Dict], output_dir: str,
                     width: int = 768, height: int = 432) -> List[str]:
    """
    Fetch images for all scenes. Returns list of image paths in scene order.
    Adds a small delay between requests to be polite to pollinations.ai.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    image_paths = []

    for scene in scenes:
        idx    = scene["scene"] - 1
        prompt = scene.get("image_prompt", "ghibli forest anime style")
        path   = str(Path(output_dir) / f"scene_{idx:03d}.jpg")

        img_path = fetch_image(prompt, path, width, height)
        image_paths.append(img_path)

        # Polite delay between requests (pollinations has no rate limit docs,
        # but rapid fire can cause 429s)
        if idx < len(scenes) - 1:
            time.sleep(2)

    log.info(f"All {len(image_paths)} scene images fetched")
    return image_paths


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    test_scenes = [
        {"scene": 1, "image_prompt": "young Tamil girl in ancient magical forest, glowing shrine"},
        {"scene": 2, "image_prompt": "spirit fox sitting by a moonlit river, fireflies"},
    ]
    paths = fetch_all_scenes(test_scenes, "/tmp/gexp_test_images")
    for p in paths:
        print(f"✓ {p}")
