#!/usr/bin/env python3
"""
Video builder — assembles final Tamil Ghibli video from scenes.

Per scene:
  image (jpg) → Ken Burns zoom clip (ffmpeg)
  tamil_text  → TTS audio (edge-tts, ta-IN-PallaviNeural)
  clip + audio → extend clip to audio length → scene.mp4

Final:
  concat all scene clips → fade in/out → final.mp4
"""

import asyncio
import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Dict

log = logging.getLogger(__name__)

TTS_VOICE   = "ta-IN-PallaviNeural"   # clear Tamil female voice
TTS_RATE    = "+0%"                    # normal speed
TTS_PITCH   = "+0Hz"

VIDEO_WIDTH  = 768
VIDEO_HEIGHT = 432
FPS          = 8
FADE_DUR     = 0.8   # seconds


# ── TTS ───────────────────────────────────────────────────────────────────────

async def _tts_async(text: str, path: str):
    import edge_tts
    comm = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await comm.save(path)


def generate_tts(text: str, path: str) -> bool:
    try:
        asyncio.run(_tts_async(text, path))
        log.info(f"TTS ({get_duration(path):.1f}s) → {path}")
        return True
    except ImportError:
        log.error("edge-tts not installed. Run: pip install edge-tts")
        return False
    except Exception as e:
        log.warning(f"TTS failed: {e}")
        return False


# ── FFMPEG UTILS ──────────────────────────────────────────────────────────────

def get_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def ken_burns_clip(image_path: str, output_path: str,
                   duration: float = 5.0) -> str:
    """Ken Burns zoom/pan effect on a still image."""
    h      = int(hashlib.md5(image_path.encode()).hexdigest()[:4], 16)
    frames = int(duration * FPS)
    w, ht  = VIDEO_WIDTH, VIDEO_HEIGHT

    # 4 zoom variations for visual variety
    zooms = [
        "z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "z='if(lte(zoom,1.0),1.15,max(1.0,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)+zoom*3':y='ih/2-(ih/zoom/2)'",
        "z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-zoom*2'",
    ]
    zoom_expr = zooms[h % len(zooms)]

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", (
            f"scale={w*2}:{ht*2},"
            f"zoompan={zoom_expr}:d={frames}:s={w}x{ht}:fps={FPS}"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg ken burns error: {r.stderr.decode()[:300]}")
    return output_path


def extend_to_audio(video_path: str, audio_path: str, output_path: str):
    """Loop video to match audio duration."""
    dur = get_duration(audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264", "-c:a", "aac",
        "-t", str(dur), "-pix_fmt", "yuv420p",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    log.info(f"Scene clip ({dur:.1f}s) → {output_path}")


def silent_clip(video_path: str, duration: float, output_path: str):
    """Add silent audio track."""
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-c:a", "aac",
        "-t", str(duration), "-pix_fmt", "yuv420p",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def concat_clips(clip_paths: List[str], output_path: str, tmp_dir: str):
    list_file = Path(tmp_dir) / "concat.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    log.info(f"Concatenated {len(clip_paths)} clips → {output_path}")


def add_fades(input_path: str, output_path: str):
    total = get_duration(input_path)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",  f"fade=t=in:st=0:d={FADE_DUR},fade=t=out:st={total-FADE_DUR}:d={FADE_DUR}",
        "-af",  f"afade=t=in:st=0:d={FADE_DUR},afade=t=out:st={total-FADE_DUR}:d={FADE_DUR}",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    log.info(f"Fades added → {output_path}")


# ── MAIN BUILD ────────────────────────────────────────────────────────────────

def build_video(scenes: List[Dict], image_paths: List[str],
                output_path: str, tmp_dir: str) -> str:
    """
    Build final video from scenes + pre-fetched images.

    scenes      : list of scene dicts (must have tamil_text, scene number)
    image_paths : list of image file paths in scene order
    output_path : final output .mp4
    tmp_dir     : temp working directory
    """
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    final_clips = []

    for i, scene in enumerate(scenes):
        log.info(f"\n── Scene {i+1}/{len(scenes)} ──")
        img_path   = image_paths[i]
        clip_raw   = str(Path(tmp_dir) / f"s{i:03d}_raw.mp4")
        audio_path = str(Path(tmp_dir) / f"s{i:03d}.mp3")
        clip_final = str(Path(tmp_dir) / f"s{i:03d}_final.mp4")

        # 1. Ken Burns clip (base 5s, extended to TTS length)
        ken_burns_clip(img_path, clip_raw, duration=5.0)

        # 2. TTS narration
        has_audio = generate_tts(scene["tamil_text"], audio_path)

        # 3. Sync clip to audio
        if has_audio and os.path.exists(audio_path) and get_duration(audio_path) > 0.5:
            extend_to_audio(clip_raw, audio_path, clip_final)
        else:
            silent_clip(clip_raw, 5.0, clip_final)

        final_clips.append(clip_final)

    # 4. Concat all scenes
    pre_final = str(Path(tmp_dir) / "pre_final.mp4")
    concat_clips(final_clips, pre_final, tmp_dir)

    # 5. Fade in/out
    add_fades(pre_final, output_path)

    total = get_duration(output_path)
    log.info(f"\n✅ Video ready: {output_path} ({total:.1f}s)")
    return output_path
