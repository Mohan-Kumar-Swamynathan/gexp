# Tamil Ghibli Video Generator

Automated Tamil Ghibli-style story video pipeline.  
**100% free** — Gemini free tier + Groq free tier + pollinations.ai + edge-tts.

## Pipeline

```
LLM (Gemini/Groq) → topic
LLM               → 8-scene Tamil script
pollinations.ai   → 1 Ghibli AI image per scene (free, no key)
edge-tts          → Tamil TTS narration (ta-IN-PallaviNeural)
ffmpeg            → Ken Burns zoom + concat + fade → final.mp4
```

## Local setup

```bash
git clone https://github.com/Mohan-Kumar-Swamynathan/gexp
cd gexp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg   # macOS

cp .env.example .env
# Add your GEMINI_KEY and GROQ_API_KEY

# Auto-pick topic
python src/main.py

# Override topic
python src/main.py --topic "காட்டில் வாழும் மந்திர நரி"
```

## GitHub Actions

Add secrets:
- `GEMINI_KEY` — from https://aistudio.google.com/app/apikey (free)
- `GROQ_API_KEY` — from https://console.groq.com/keys (free)

Runs daily at 9:30am IST. Video uploads as artifact for 7 days.  
Manual trigger: Actions → Generate Tamil Ghibli Video → Run workflow.

## Output

```
output/YYYY-MM-DD_<slug>/
  ├── topic.json    # topic metadata
  ├── script.json   # 8-scene script
  ├── images/       # scene images
  └── final.mp4     # ← watch this
```
