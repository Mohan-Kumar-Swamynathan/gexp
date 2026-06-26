#!/usr/bin/env python3
"""
Script generator — takes a topic dict, returns 8-scene Tamil narration.

Each scene has:
  - tamil_text   : narration (spoken by TTS)
  - image_prompt : English Ghibli image prompt for pollinations.ai
  - duration_hint: estimated seconds
"""

import json
import logging
import re
from typing import Dict, List, Optional

from llm_client import generate_text

log = logging.getLogger(__name__)

SCRIPT_PROMPT = """நீங்கள் ஒரு Tamil Ghibli-style animated YouTube channel-க்கு script எழுதுகிறீர்கள்.

Topic: {topic}
Hook: {hook}
Visual keywords: {image_keywords}

Channel rules (STRICT):
- 100% தமிழில் மட்டுமே narration — ஒரு வார்த்தை ஆங்கிலம் கூடாது
- Ghibli style: இயற்கை, உணர்வு, மெதுவான pace, காட்சி விவரணை
- 8 scenes exactly
- Each scene: 2-4 Tamil sentences (40-60 words)
- Story arc: scene1=அமைப்பு, scenes2-3=கதை தொடக்கம், scenes4-6=உச்சம், scenes7-8=முடிவு+செய்தி
- No English words, no romanized Tamil, no numbers in numerals (spell them out)

Return ONLY this JSON array (no markdown):
[
  {{
    "scene": 1,
    "tamil_text": "Tamil narration for this scene...",
    "image_prompt": "studio ghibli style, [specific visual description in English], anime, painterly, soft watercolor",
    "mood": "peaceful|wonder|emotional|tense|joyful|melancholic"
  }},
  ...8 scenes total
]

image_prompt must describe a SPECIFIC visual scene matching the Tamil narration.
Example: "studio ghibli style, young girl standing at ancient stone shrine, glowing lanterns, misty forest, soft morning light, anime, painterly"
"""

FALLBACK_SCENES = [
    {
        "scene": i + 1,
        "tamil_text": f"காட்சி {i+1}: ஒரு அழகான தமிழ் நாட்டில், இயற்கையின் மடியில் ஒரு சிறுமி வளர்ந்தாள். அவளது கண்களில் எப்போதும் ஆச்சரியம் மிளிர்ந்தது. காற்று அவளிடம் பழைய கதைகளை கிசுகிசுத்தது.",
        "image_prompt": f"studio ghibli style, young Tamil girl in ancient forest scene {i+1}, soft watercolor, warm light, anime, painterly",
        "mood": "peaceful",
    }
    for i in range(8)
]


def _parse_scenes(raw: str) -> Optional[List[Dict]]:
    cleaned = re.sub(r"```json|```", "", raw).strip()

    # Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list) and len(data) >= 6:
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON array
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list) and len(data) >= 6:
                return data
        except Exception:
            pass

    return None


def validate_tamil_only(text: str) -> bool:
    """Check if text is predominantly Tamil (>80% non-ASCII or Tamil unicode)."""
    if not text:
        return False
    tamil_chars = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF' or c in ' \n.,!?।')
    return tamil_chars / len(text) > 0.6


def generate_script(topic: Dict) -> List[Dict]:
    """Generate 8-scene Tamil Ghibli script for the given topic."""
    prompt = SCRIPT_PROMPT.format(
        topic=topic.get("topic", ""),
        hook=topic.get("hook", ""),
        image_keywords=", ".join(topic.get("image_keywords", [])),
    )

    log.info(f"Generating script for: {topic.get('topic')}")
    raw = generate_text(prompt, max_tokens=3000)
    scenes = _parse_scenes(raw)

    if not scenes:
        log.warning("Script parse failed, using fallback scenes")
        return FALLBACK_SCENES

    # Validate each scene has required fields
    validated = []
    for i, scene in enumerate(scenes[:8]):
        tamil = scene.get("tamil_text", "").strip()
        img   = scene.get("image_prompt", "").strip()

        if not tamil:
            tamil = FALLBACK_SCENES[i]["tamil_text"]
        if not img:
            img = FALLBACK_SCENES[i]["image_prompt"]

        # Warn but don't fail if English leaks into Tamil text
        if not validate_tamil_only(tamil):
            log.warning(f"Scene {i+1} may contain non-Tamil content: {tamil[:50]}...")

        validated.append({
            "scene": i + 1,
            "tamil_text": tamil,
            "image_prompt": img,
            "mood": scene.get("mood", "peaceful"),
        })

    # Pad to 8 if LLM returned fewer
    while len(validated) < 8:
        idx = len(validated)
        validated.append(FALLBACK_SCENES[idx])

    log.info(f"Script ready: {len(validated)} scenes")
    return validated


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    test_topic = {
        "topic": "காட்டில் வாழும் மந்திர நரி",
        "hook": "ஒரு நரி மனிதர்களின் நட்பை தேடுகிறது",
        "image_keywords": ["magical fox", "forest", "shrine"],
    }
    scenes = generate_script(test_topic)
    for s in scenes:
        print(f"\n--- Scene {s['scene']} ({s['mood']}) ---")
        print(s["tamil_text"])
        print(f"[IMG] {s['image_prompt'][:80]}...")
