# S2S Chat Explorer

A small Panel-based web app for browsing large collections of text-to-speech (TTS) dialogues with synchronous audio playback.

## Features

* Filter conversations by number of turns and total duration.
* Paginated list (25 per page) – handles manifests with 100 k+ entries.
* Inline playback of whole-dialogue audio **and** per-turn snippets (if available).
* Hover over any bubble for full turn metadata.

## Quick start

```bash
# 1. Clone / enter this repo then install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Serve the explorer (replace manifest_14.json with yours)
panel serve explore.py --autoreload --args meta_manifest.json
```

Then open the printed URL (e.g. http://localhost:5006/tts_chat_explorer) in your browser.

## Manifest format

The app expects a **meta-manifest**: a JSON-lines (one object per line) file where each object at minimum contains:

```jsonc
{
  "metadata_path": "ultrachat_1.json",   // relative path to per-conversation manifest
  "wav_path": "ultrachat_1.wav",        // (optional) full-dialogue audio
  "conversation_id": "ultrachat_1",
  "num_turns": 2,
  "total_duration": 24.92,
  "agent_speaker": "gpt",
  "user_speaker": "human"
}
```

The *per-conversation* manifest referenced by `metadata_path` should itself contain a `turns` list with optional `audio_filepath` for each turn.

## Tips for very large datasets

* Use the sliders to narrow down the visible set – it further reduces rendering overhead.
* The page slider in the sidebar lets you navigate through batches of conversations without overwhelming the browser.

---
© 2025 S2S Chat Explorer 
