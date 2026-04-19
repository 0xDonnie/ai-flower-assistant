# Sound assets

This directory holds all the WAV files the app plays. **Nothing is shipped in this repo** — every subfolder is empty by default. You supply your own audio.

## Subfolders

| Folder | Played when |
|--------|-------------|
| `quips/` | Single-tap — random short reaction |
| `indicators/` | UI-ish feedback (fallback when TTS isn't available) |
| `thinking/` | Optional filler while the LLM is processing |
| `morning/` | Startup greeting when the Pi boots between 06:00 and 10:59 |
| `bedtime/` | Startup greeting when the Pi boots between 21:00 and 23:59 |
| `startup/` | Startup greeting fallback outside the morning/bedtime windows |
| `smalltalk/` | Idle chatter lines played at random intervals |
| `hourly/` | Hourly time announcements — one file per hour, named `sono_le_HH_NN.wav` or similar |
| `status/` | `keep_quiet.wav`, `psst.wav`, `battery_low.wav` — played on quiet-hours boundaries |
| `special/` | Quintuple-tap reward messages |
| `music/` | Quadruple-tap music mode — drop any `.wav` you want to loop |

## How to populate

1. **TTS generation** — render short Italian phrases with your ElevenLabs cloned voice (or any TTS). Save as 16-bit 48 kHz mono WAV.
2. **Record your own voice** and export from any audio editor.
3. **Royalty-free SFX** for indicators / thinking sounds (e.g. freesound.org under CC0).

The app degrades gracefully when a folder is empty: the corresponding gesture just plays silence.

## Format

- `.wav` — Signed 16-bit Little-Endian, 48 kHz, mono, is ideal (native to the MAX98357A at this config)
- Other rates and channel counts work too — ALSA `plug` will convert on the fly — but native avoids resampling artifacts.
