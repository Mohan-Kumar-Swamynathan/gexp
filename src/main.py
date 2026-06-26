#!/usr/bin/env python3
"""
Tamil Ghibli Video Pipeline — main entry point.

Usage:
  # Auto-pick topic via LLM:
  python src/main.py

  # Override with a specific topic:
  python src/main.py --topic "காட்டில் வாழும் மந்திர நரி"

  # Skip image fetch (use cached images in tmp/):
  python src/main.py --skip-images

Output:
  output/YYYY-MM-DD_<slug>/
    ├── topic.json       topic metadata
    ├── script.json      8-scene script
    ├── images/          scene images
    └── final.mp4        ← the video
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Allow running from repo root or src/
sys.path.insert(0, str(Path(__file__).parent))

from topic_finder    import pick_topic, save_used_topic
from script_generator import generate_script
from image_generator  import fetch_all_scenes
from video_builder    import build_video

log = logging.getLogger(__name__)

OUTPUT_ROOT = Path(__file__).parent.parent / "output"


def slugify(text: str) -> str:
    """Convert Tamil/Unicode title to a safe directory name."""
    ascii_only = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    slug = re.sub(r"[\s_-]+", "_", ascii_only).strip("_")
    return slug[:40] if slug else "ghibli_story"


def run(topic_override: str = None, skip_images: bool = False):
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # ── 1. Topic ──────────────────────────────────────────────────────────────
    log.info("=" * 50)
    log.info("STEP 1: Topic")
    log.info("=" * 50)

    if topic_override:
        topic = {
            "topic": topic_override,
            "category": "manual",
            "hook": "மேலும் அறிய கதையை கவனியுங்கள்",
            "image_keywords": ["forest", "temple", "nature"],
        }
        log.info(f"Using override topic: {topic_override}")
    else:
        topic = pick_topic()

    # ── 2. Output directory ───────────────────────────────────────────────────
    slug      = slugify(topic["topic"])
    out_dir   = OUTPUT_ROOT / f"{date_str}_{slug}"
    img_dir   = out_dir / "images"
    tmp_dir   = out_dir / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(exist_ok=True)
    tmp_dir.mkdir(exist_ok=True)

    topic_file  = out_dir / "topic.json"
    script_file = out_dir / "script.json"
    video_path  = str(out_dir / "final.mp4")

    topic_file.write_text(
        json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"Output dir: {out_dir}")
    log.info(f"Topic: {topic['topic']}")

    # ── 3. Script ─────────────────────────────────────────────────────────────
    log.info("=" * 50)
    log.info("STEP 2: Script generation")
    log.info("=" * 50)

    scenes = generate_script(topic)
    script_file.write_text(
        json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for s in scenes:
        log.info(f"  Scene {s['scene']}: {s['tamil_text'][:60]}...")

    # ── 4. Images ─────────────────────────────────────────────────────────────
    log.info("=" * 50)
    log.info("STEP 3: Image generation")
    log.info("=" * 50)

    if skip_images:
        # Use already-fetched images from img_dir
        image_paths = sorted(img_dir.glob("scene_*.jpg"))
        image_paths = [str(p) for p in image_paths]
        if len(image_paths) < len(scenes):
            log.warning("Not enough cached images, fetching missing ones...")
            skip_images = False

    if not skip_images:
        image_paths = fetch_all_scenes(scenes, str(img_dir))

    log.info(f"Images ready: {len(image_paths)}")

    # ── 5. Video ──────────────────────────────────────────────────────────────
    log.info("=" * 50)
    log.info("STEP 4: Video assembly")
    log.info("=" * 50)

    build_video(scenes, image_paths, video_path, str(tmp_dir))

    # ── 6. Save topic to used list (dedup for next run) ───────────────────────
    if not topic_override:
        save_used_topic(topic["topic"])

    log.info("=" * 50)
    log.info(f"✅ DONE")
    log.info(f"   Topic  : {topic['topic']}")
    log.info(f"   Video  : {video_path}")
    log.info(f"   Scenes : {len(scenes)}")
    log.info("=" * 50)

    return video_path


def main():
    parser = argparse.ArgumentParser(
        description="Tamil Ghibli video pipeline"
    )
    parser.add_argument("--topic", type=str, default=None,
                        help="Override auto topic with a specific Tamil title")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip image fetch, use cached images")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    run(topic_override=args.topic, skip_images=args.skip_images)


if __name__ == "__main__":
    main()
