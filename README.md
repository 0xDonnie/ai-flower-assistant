# AI Flower Voice Assistant

An AI-powered voice assistant shaped like a potted flower, running on a Raspberry Pi Zero 2 W with ElevenLabs TTS/STT and a pluggable LLM backend via [PicoClaw](https://github.com/sipeed/picoclaw).

Press the button on the flower, speak, and it answers in character — as a sarcastic, jealous, attention-hungry talking plant with petals and attitude. Italian by default; the character personality is defined in plain Markdown files under [`character/`](character/) and is easy to swap.

## Features

- **Hold-to-talk voice interaction** — hold the button, release, speak, get a response via STT → LLM → TTS
- **Six button gestures** — tap / 2x / 3x / 4x / 5x / hold each trigger a different behavior
- **Idle chatter** — the flower talks to itself at random intervals (toggleable with double-tap)
- **Hourly time announcements** — plays a voiced WAV each hour (supply your own)
- **Quiet hours** — configurable WAKE / SLEEP window with bedtime + morning greetings
- **Music mode** — drop WAV files in `voice-assistant/sounds/music/` and toggle with quadruple-tap
- **Conversation memory** — session-based via PicoClaw, reset with triple-tap
- **Auto-start on boot** — four systemd services (voice app, LLM gateway, silence streamer, Wi-Fi power-save)
- **Welcome greeting on boot** — plays a time-appropriate WAV on startup (outside quiet hours)
- **Vocal confirmations** — TTS feedback when toggling chatter, in the same cloned voice
- **Remote control** — file-watcher on `/tmp/flower-command` lets you trigger any gesture from a remote shell, plus a tiny PowerShell GUI for Windows
- **SSH always reachable** — systemd service disables the Pi Zero 2 W's aggressive Wi-Fi power-save
- **Robust ALSA config** — uses card *names* (`CARD=MAX98357A`) not numbers, survives boot-order flips
- **VAD tuned for real rooms** — background music or room noise doesn't trigger endless recording
- **Character in Markdown** — personality defined in four Markdown files, drop-in replaceable

## How it works

```
Button hold → release → Record audio (VAD stops on silence)
   → ElevenLabs Scribe STT (Italian)
   → PicoClaw → LLM of your choice (OpenAI, Groq, DeepSeek, OpenRouter, …)
   → ElevenLabs v3 TTS (your cloned voice)
   → MAX98357A I2S amp
   → toy speaker
```

End-to-end latency with OpenAI gpt-4o-mini: typically **~2-4 seconds**.

## Hardware

Any flower-shaped enclosure with a button and a speaker can be used. The original build repurposes a commercial plant-shaped toy, tapping into its existing dome-switch button and speaker while bypassing the factory electronics.

| Component | Notes |
|-----------|-------|
| Raspberry Pi Zero 2 **WH** | Pre-soldered headers required |
| microSD 32 GB | 2.4 GHz Wi-Fi (Pi Zero 2 W doesn't do 5 GHz) |
| 5V 2A micro-USB power supply | Avoid fast chargers; check for under-voltage |
| MAX98357A I2S amp breakout | 7-pin header + 2-pin screw terminal for speaker |
| USB microphone | Any C-Media / CM108-based PnP USB mic works |
| Micro-USB OTG to USB-A cable | 15 cm flexible — rigid adapters foul the power port |
| Dupont jumpers (F-F, M-F, M-M) | Elegoo 120-pc kit is plenty |
| Any enclosure with a button + speaker | See the build guide for wiring a typical toy |

## Six button gestures

| Gesture | Effect |
|---------|--------|
| **Hold** (> 0.3s) | Push-to-talk — release, speak, silence stops recording, you get a reply |
| **Tap** | Random quip WAV from `sounds/quips/` |
| **Double tap** | Toggle idle chatter on/off, with vocal confirmation |
| **Triple tap** | Reset conversation memory (new LLM session) |
| **Quadruple tap** | Toggle music mode — plays WAVs from `sounds/music/` |
| **Quintuple tap** | Play a "special message" WAV from `sounds/special/` |

**PTT quirk:** recording starts *after* button release, not during hold. Sequence is press-hold → release → *then* speak → silence → answer. Counter-intuitive, document it for anyone new.

## LLM provider choice

PicoClaw acts as an LLM gateway, so any OpenAI-compatible API works. Default suggested: **OpenAI gpt-4o-mini** (~\$0.0006 per turn — a few € per month for personal use, no rate limits).

Tested alternatives:
- **Groq** free tier — fast but per-minute rate-limited
- **OpenRouter** free models — availability varies, hit-or-miss
- **DeepSeek V3** — extremely cheap pay-as-you-go
- **Google Gemini** via AI Studio — generous free tier

Switch providers by editing `model_list` in `~/.picoclaw/config.json` (see [`picoclaw-config.example.json`](picoclaw-config.example.json)).

## Repository layout

```
ai-flower-assistant/
├── character/              # Personality in Markdown — edit to change the persona
├── voice-assistant/        # Main Python app
│   ├── voice_assistant.py
│   ├── idle_chatter.py
│   ├── .env.example
│   └── sounds/             # Supply your own WAVs (see README.md inside each subfolder)
├── scripts/
│   ├── flower_firstboot.sh       # First-boot auto-install (apt + I2S + ALSA + services)
│   ├── install_from_local.sh     # App-level install once the repo is scp'd onto the Pi
│   ├── flower_remote.ps1         # PowerShell GUI for remote control
│   ├── flower_shutdown.bat       # Quick shutdown helper
│   ├── disable_wifi_powersave.sh # Post-install helper
│   ├── button_test.py            # Wiring diagnostic — identify which wires go to the button
│   ├── button_test_v2.py
│   ├── button_live_test.py
│   └── generate_icon.ps1         # Convert SVG/PNG into multi-size .ico
├── systemd/
│   ├── flower-voice.service
│   ├── flower-silence.service
│   └── picoclaw-gateway.service
├── docs/
│   ├── hardware.md               # Wiring, ALSA, audio tuning
│   ├── guida-completa.md         # Full setup walkthrough (Italian)
│   └── sd_card_setup.md          # SD flashing + cloud-init first-boot
├── asoundrc-flower               # ALSA config template
├── picoclaw-config.example.json
├── picoclaw-security.example.yml
├── flower_remote.bat             # Launcher for the GUI
└── flower_shutdown.bat           # Quick-shutdown helper
```

## Audio assets

**No audio is redistributed with this repo.** Sound folders (`sounds/quips/`, `sounds/indicators/`, `sounds/morning/`, `sounds/bedtime/`, `sounds/hourly/`, `sounds/special/`, `sounds/music/`) contain only a `README.md` describing what goes where. You supply your own, typically by:

1. **Generating them with TTS** — render short Italian phrases with your ElevenLabs cloned voice.
2. **Recording your own voice** into WAV.
3. **Royalty-free SFX** for indicator / thinking sounds.

The app degrades gracefully when a folder is empty: the corresponding gesture just plays nothing.

## Remote control

### File trigger

The app polls `/tmp/flower-command` every 200 ms. Write one of `tap`, `tap2`, `tap3`, `tap4`, `tap5`, `hold` into it and the gesture fires:

```bash
ssh pi@FLOWER_HOST "echo tap > /tmp/flower-command"       # quip
ssh pi@FLOWER_HOST "echo tap2 > /tmp/flower-command"      # toggle chatter
ssh pi@FLOWER_HOST "echo tap3 > /tmp/flower-command"      # reset memory
ssh pi@FLOWER_HOST "echo tap4 > /tmp/flower-command"      # music mode
ssh pi@FLOWER_HOST "echo tap5 > /tmp/flower-command"      # special
ssh pi@FLOWER_HOST "echo hold > /tmp/flower-command"      # PTT (physical mic)
```

### PowerShell GUI (Windows)

Small WPF window with 6 gesture buttons + a red shutdown button. Launch with `flower_remote.bat` or directly:

```
powershell -ExecutionPolicy Bypass -File scripts\flower_remote.ps1
```

Before first use, edit `scripts/flower_remote.ps1` and set `$PI_HOST` to your Pi's `user@hostname-or-ip`. SSH key auth must be set up.

For the shutdown button to work non-interactively, allow passwordless shutdown for the `pi` user (the first-boot script does this automatically; existing installs can do it once with):

```
echo 'pi ALL=(ALL) NOPASSWD: /sbin/shutdown, /usr/sbin/shutdown' | sudo tee /etc/sudoers.d/flower-shutdown
sudo chmod 0440 /etc/sudoers.d/flower-shutdown
```

## Quick start

Full walkthrough in [`docs/guida-completa.md`](docs/guida-completa.md). Short version:

```bash
# 1. Flash Raspberry Pi OS Lite (64-bit) via Pi Imager. Set hostname / user /
#    Wi-Fi + enable SSH in the advanced settings.
# 2. Before ejecting the SD, drop scripts/flower_firstboot.sh and the
#    cloud-init snippet on the bootfs partition (see docs/sd_card_setup.md).
# 3. Boot the Pi — first-boot apt install takes ~20-30 min. Wait.

# 4. From your laptop:
scp -r /path/to/repo pi@FLOWER_HOST:~/ai-flower-assistant
ssh pi@FLOWER_HOST "cd ~/ai-flower-assistant && bash scripts/install_from_local.sh"

# 5. Install the PicoClaw binary (arm64):
ssh pi@FLOWER_HOST "curl -L https://github.com/sipeed/picoclaw/releases/download/v0.2.6/picoclaw_Linux_arm64.tar.gz | tar xz -C /tmp && sudo mv /tmp/picoclaw /home/pi/ && sudo chmod +x /home/pi/picoclaw"

# 6. Configure PicoClaw (LLM):
scp picoclaw-config.example.json pi@FLOWER_HOST:~/.picoclaw/config.json
scp picoclaw-security.example.yml pi@FLOWER_HOST:~/.picoclaw/.security.yml
ssh pi@FLOWER_HOST "nano ~/.picoclaw/.security.yml"   # paste your LLM API key

# 7. Configure the voice assistant:
scp voice-assistant/.env.example pi@FLOWER_HOST:~/ai-flower-assistant/voice-assistant/.env
ssh pi@FLOWER_HOST "nano ~/ai-flower-assistant/voice-assistant/.env"
# set ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, etc.

# 8. Start:
ssh pi@FLOWER_HOST "sudo systemctl enable --now picoclaw-gateway flower-voice flower-silence wifi-powersave-off"
```

## Troubleshooting

The final section of [`docs/guida-completa.md`](docs/guida-completa.md) covers common issues: button not detected, audio distortion, ALSA card-number flips, Wi-Fi power-save, rate-limited LLM, PTT timing surprises, under-voltage from cheap cables, etc.

## Acknowledgements

- [PicoClaw](https://github.com/sipeed/picoclaw) by Sipeed — the LLM gateway in Go
- [ElevenLabs](https://elevenlabs.io) — Scribe STT + v3 TTS with voice cloning
- Original inspiration from an upstream talking-flower project ([`manaporkun/talking-flower`](https://github.com/manaporkun/talking-flower)). This fork is a heavy refactor: different PCB revision, different wiring, different LLM stack, different install flow, ALSA / systemd / Wi-Fi fixes, remote-control GUI, original personality.

## License

MIT.

**Third-party assets:** this repo does not include, reference, or redistribute any audio samples, images, trademarks, or character designs owned by third parties. All character personality, code, and documentation are original. The hardware is a generic toy; no specific commercial product is endorsed or affiliated.
