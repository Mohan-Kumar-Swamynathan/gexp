#!/usr/bin/env python3
"""
Topic finder for Tamil Ghibli story channel.

Sources (all free, no key needed):
  - Tamil/Indian mythology & folklore seed list (curated)
  - Wikipedia "On This Day" Tamil events
  - LLM generates fresh angle on topic

Output: one unique topic not seen in used_topics.json
"""

import json
import logging
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from llm_client import generate_text

log = logging.getLogger(__name__)

USED_TOPICS_FILE = Path(__file__).parent.parent / "data" / "used_topics.json"

# ── Seed topic categories for Ghibli-style Tamil stories ──────────────────────
# LLM will pick + expand one of these into a specific story topic
SEED_CATEGORIES = [
    "தமிழ் நாட்டுப்புற கதைகள்",          # Tamil folk tales
    "சங்க இலக்கிய காட்சிகள்",              # Sangam literature scenes
    "தமிழ் நாட்டு பழமொழி கதைகள்",         # Tamil proverb stories
    "கோயில் புராண கதைகள்",                # Temple mythology stories
    "தமிழ் இயற்கை மற்றும் கடல் கதைகள்",  # Tamil nature & sea stories
    "பழந்தமிழ் வீர கதைகள்",               # Ancient Tamil heroic tales
    "தமிழ் காட்டு உயிரினக் கதைகள்",       # Tamil forest creature stories
    "குழந்தைகளுக்கான தமிழ் நைதிக கதைகள்", # Tamil moral tales for children
]

TOPIC_PROMPT = """நீங்கள் ஒரு Tamil Ghibli-style animated YouTube channel-க்கு story topic தேர்வு செய்கிறீர்கள்.

Channel style: Studio Ghibli போன்ற அழகான animation, 100% தமிழ் narration, 
இயற்கை, உணர்வு, நம்பிக்கை themes.

Category pool (randomly pick one to inspire):
{categories}

Already used topics (DO NOT repeat or closely resemble these):
{used_topics}

Today's date: {date}

Your task:
1. Pick one category above as inspiration
2. Create ONE specific original Tamil story topic in that spirit
3. The topic should be visual, emotional, suitable for Ghibli animation style
4. Must be fresh — not in the used list above

Return ONLY this JSON (no markdown, no explanation):
{{
  "topic": "கதை தலைப்பு (under 80 Tamil chars)",
  "category": "which category inspired this",
  "hook": "one Tamil sentence — why this story is emotionally compelling",
  "image_keywords": ["english keyword1", "english keyword2", "english keyword3"]
}}

image_keywords: 3 English words/phrases for generating Ghibli-style images (forest, shrine, river etc.)"""


def load_used_topics() -> List[str]:
    if USED_TOPICS_FILE.exists():
        data = json.loads(USED_TOPICS_FILE.read_text("utf-8"))
        return data.get("topics", [])
    return []


def save_used_topic(topic: str):
    USED_TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    used = load_used_topics()
    if topic not in used:
        used.append(topic)
    USED_TOPICS_FILE.write_text(
        json.dumps({"topics": used}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info(f"Saved topic to used list: {topic}")


def _parse_json(raw: str) -> Optional[Dict]:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return None


def pick_topic() -> Dict:
    """Pick a fresh Tamil Ghibli story topic using LLM."""
    used = load_used_topics()
    used_block = "\n".join(f"- {t}" for t in used[-40:]) if used else "(none yet)"
    categories_block = "\n".join(f"- {c}" for c in SEED_CATEGORIES)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    prompt = TOPIC_PROMPT.format(
        categories=categories_block,
        used_topics=used_block,
        date=date_str,
    )

    log.info("Asking LLM for topic...")
    raw = generate_text(prompt, max_tokens=512)
    data = _parse_json(raw)

    if not data or not data.get("topic"):
        # Fallback: pick a seed category + date-based title
        import hashlib
        idx = int(hashlib.md5(date_str.encode()).hexdigest()[:4], 16) % len(SEED_CATEGORIES)
        data = {
            "topic": f"{SEED_CATEGORIES[idx]} — இன்றைய கதை",
            "category": SEED_CATEGORIES[idx],
            "hook": "ஒரு அழகான தமிழ் கதை",
            "image_keywords": ["ancient forest", "temple", "misty morning"],
        }
        log.warning(f"LLM parse failed, using fallback topic: {data['topic']}")

    log.info(f"Topic: {data['topic']}")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = pick_topic()
    print(json.dumps(result, ensure_ascii=False, indent=2))
