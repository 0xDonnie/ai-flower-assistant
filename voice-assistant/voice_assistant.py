#!/usr/bin/env python3
"""Flower Voice Assistant — press a button, talk, get a response."""

import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

# --- Config ---

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_v3")
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TRANSCRIBE_LANGUAGE = os.getenv("OPENAI_TRANSCRIBE_LANGUAGE", "en")

STT_PROVIDER = os.getenv("STT_PROVIDER", "elevenlabs")
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
INPUT_DEVICE_HINT = os.getenv("INPUT_DEVICE_HINT", "USB")
OUTPUT_DEVICE_HINT = os.getenv("OUTPUT_DEVICE_HINT", "USB")

PICOCLAW_BIN = os.getenv("PICOCLAW_BIN", "/home/pi/picoclaw")
PICOCLAW_MODEL = os.getenv("PICOCLAW_MODEL", "kimi-turbo")
PICOCLAW_SESSION = os.getenv("PICOCLAW_SESSION", "voice:assistant")

SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.015"))
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "1.5"))
MIN_SPEECH_DURATION = float(os.getenv("MIN_SPEECH_DURATION", "0.5"))
MAX_RECORD_SECONDS = float(os.getenv("MAX_RECORD_SECONDS", "30"))

GPIO_BUTTON_PIN = int(os.getenv("GPIO_BUTTON_PIN", "17"))
INPUT_MODE = os.getenv("INPUT_MODE", "auto")  # "gpio", "keyboard", or "auto"
STARTUP_MESSAGE = os.getenv("STARTUP_MESSAGE", "")
IDLE_CHATTER = os.getenv("IDLE_CHATTER", "1").lower() not in ("0", "false", "no", "off")
IDLE_INTERVAL_MIN = int(os.getenv("IDLE_INTERVAL_MIN", "5"))
IDLE_INTERVAL_MAX = int(os.getenv("IDLE_INTERVAL_MAX", "15"))

HOLD_THRESHOLD = float(os.getenv("HOLD_THRESHOLD", "0.3"))
TAP_WINDOW = float(os.getenv("TAP_WINDOW", "0.4"))
QUIPS_DIR = Path(os.getenv("QUIPS_DIR", str(Path(__file__).resolve().parent / "sounds" / "quips")))
INDICATORS_DIR = Path(os.getenv("INDICATORS_DIR", str(Path(__file__).resolve().parent / "sounds" / "indicators")))

# --- Flower mode (offline WAV playback) ---
# When enabled, idle chatter / startup greeting / tap quip all play local WAVs
# from voice-assistant/sounds/ instead of calling ElevenLabs TTS. Zero-cost.
FLOWER_MODE = os.getenv("FLOWER_MODE", "1").lower() not in ("0", "false", "no", "off")
HOURLY_ANNOUNCE = os.getenv("HOURLY_ANNOUNCE", "1").lower() not in ("0", "false", "no", "off")

INPUT_FALLBACK_RATES = [16000, 48000, 44100, 32000, 8000]


# --- Audio Device Detection ---

def find_alsa_device_by_hint(hint, cmd="aplay"):
    """Find ALSA plughw device string by name hint. Survives reboots."""
    try:
        result = subprocess.run([cmd, "-l"], capture_output=True, text=True)
        for line in result.stdout.split("\n"):
            if "card" in line and hint.lower() in line.lower():
                card = line.split("card ")[1].split(":")[0].strip()
                device = line.split("device ")[1].split(":")[0].strip()
                return f"plughw:{card},{device}"
    except Exception:
        pass
    return None


def resolve_output_device():
    """Find the ALSA output device by hint, falling back to default."""
    dev = find_alsa_device_by_hint(OUTPUT_DEVICE_HINT, cmd="aplay")
    if dev:
        return dev
    return os.getenv("OUTPUT_DEVICE", "default")


def resolve_input_device():
    """Find sounddevice input index by hint."""
    devices = sd.query_devices()
    needle = INPUT_DEVICE_HINT.lower()
    for i, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0 and needle in dev["name"].lower():
            return i, dev["name"]
    for i, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            return i, dev["name"]
    raise RuntimeError("No input audio device found")


def find_working_rate(device_idx):
    for rate in INPUT_FALLBACK_RATES:
        try:
            test = sd.InputStream(device=device_idx, samplerate=rate,
                                  channels=1, dtype="float32")
            test.close()
            return rate
        except Exception:
            continue
    raise RuntimeError("No supported sample rate found")


OUTPUT_DEVICE = resolve_output_device()


# --- Recording ---

def record_until_silence(device_idx, rate):
    """Record audio, auto-stop after silence following speech."""
    q = queue.Queue()
    frames = []
    speech_detected = False
    silence_start = None

    def callback(indata, frame_count, time_info, status):
        q.put(indata.copy())

    stream = sd.InputStream(device=device_idx, samplerate=rate,
                            channels=1, dtype="float32", callback=callback)
    stream.start()

    start_time = time.monotonic()
    chunk_samples = int(rate * 0.1)
    buf = np.array([], dtype=np.float32)

    try:
        while True:
            if time.monotonic() - start_time > MAX_RECORD_SECONDS:
                print(f"\r\033[K Max duration reached.", flush=True)
                break

            try:
                chunk = q.get(timeout=0.05)
                frames.append(chunk)
                buf = np.concatenate([buf, chunk.squeeze()])
            except queue.Empty:
                continue

            while buf.size >= chunk_samples:
                segment = buf[:chunk_samples]
                buf = buf[chunk_samples:]
                rms = float(np.sqrt(np.mean(np.square(segment))))

                if rms > SILENCE_THRESHOLD:
                    speech_detected = True
                    silence_start = None
                    bar = "#" * min(40, int(rms * 400))
                    print(f"\r\033[K [{bar:<40}]", end="", flush=True)
                elif speech_detected:
                    if silence_start is None:
                        silence_start = time.monotonic()
                    elif time.monotonic() - silence_start >= SILENCE_DURATION:
                        print(f"\r\033[K Processing...", flush=True)
                        while not q.empty():
                            frames.append(q.get_nowait())
                        stream.stop()
                        stream.close()
                        if not frames:
                            return np.array([], dtype=np.float32), rate
                        audio = np.concatenate(frames, axis=0).squeeze()
                        trim = int(SILENCE_DURATION * rate)
                        if audio.size > trim:
                            audio = audio[:-trim]
                        return audio, rate
                else:
                    print(f"\r\033[K Listening...", end="", flush=True)

    except KeyboardInterrupt:
        pass

    stream.stop()
    stream.close()
    while not q.empty():
        frames.append(q.get_nowait())
    if not frames:
        return np.array([], dtype=np.float32), rate
    return np.concatenate(frames, axis=0).squeeze(), rate


# --- Audio Helpers ---

def resample(audio, src_rate, dst_rate):
    if src_rate == dst_rate or audio.size == 0:
        return audio
    duration = audio.shape[0] / float(src_rate)
    dst_len = max(1, int(round(duration * dst_rate)))
    src_x = np.linspace(0, duration, num=audio.shape[0], endpoint=False)
    dst_x = np.linspace(0, duration, num=dst_len, endpoint=False)
    return np.interp(dst_x, src_x, audio).astype(np.float32)


def save_wav(path, audio, rate):
    audio16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(audio16.tobytes())


# --- STT ---

def transcribe_elevenlabs(wav_path):
    with open(wav_path, "rb") as f:
        r = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            files={"file": (Path(wav_path).name, f, "audio/wav")},
            data={"model_id": ELEVENLABS_STT_MODEL, "language_code": "it"},
            timeout=120,
        )
    if not r.ok:
        raise RuntimeError(f"ElevenLabs STT: {r.status_code} {r.text}")
    return r.json().get("text", "").strip()


def transcribe_openai(wav_path):
    with open(wav_path, "rb") as f:
        data = {"model": OPENAI_TRANSCRIBE_MODEL}
        if OPENAI_TRANSCRIBE_LANGUAGE:
            data["language"] = OPENAI_TRANSCRIBE_LANGUAGE
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (Path(wav_path).name, f, "audio/wav")},
            data=data, timeout=120,
        )
    if not r.ok:
        raise RuntimeError(f"OpenAI STT: {r.status_code} {r.text}")
    return r.json().get("text", "").strip()


def transcribe(wav_path):
    if STT_PROVIDER == "elevenlabs":
        return transcribe_elevenlabs(wav_path)
    return transcribe_openai(wav_path)


# --- LLM ---

def ask_picoclaw(message):
    result = subprocess.run(
        [PICOCLAW_BIN, "agent", "-m", message,
         "--model", PICOCLAW_MODEL, "-s", PICOCLAW_SESSION],
        capture_output=True, text=True, timeout=120,
    )
    output = result.stdout + result.stderr
    lines = output.split("\n")
    collecting = False
    response_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\U0001f99e"):
            collecting = True
            first = stripped.lstrip("\U0001f99e").strip()
            if first:
                response_lines.append(first)
            continue
        if collecting:
            response_lines.append(line)
    if response_lines:
        return "\n".join(response_lines).strip()
    for line in lines:
        if "Response:" in line:
            idx = line.index("Response:") + len("Response:")
            return line[idx:].strip()
    return output.strip().split("\n")[-1] if output.strip() else "[no response]"


# --- TTS ---

def split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    for part in parts:
        clean = re.sub(r'\*\*|__|\*|_|#{1,6}\s*|`{1,3}', '', part.strip())
        clean = re.sub(r'^\s*[-*]\s+', '', clean).strip()
        if not clean:
            continue
        # Skip chunks that become empty after removing bracketed/parenthetical speaker tags
        text_only = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', clean).strip()
        if not text_only:
            continue
        if chunks and len(chunks[-1]) < 40:
            chunks[-1] += " " + clean
        else:
            chunks.append(clean)
    return chunks if chunks else [text.strip()]


def tts_chunk(text):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    if not r.ok:
        raise RuntimeError(f"ElevenLabs TTS: {r.status_code} {r.text}")
    return r.content


def play_audio_file(path):
    if shutil.which("mpg123") and path.endswith(".mp3"):
        subprocess.run(["mpg123", "-q", "-a", OUTPUT_DEVICE, path])
    elif shutil.which("aplay"):
        wav_path = path.replace(".mp3", ".wav")
        if path.endswith(".mp3") and shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-i", path, wav_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            path = wav_path
        subprocess.run(["aplay", "-D", OUTPUT_DEVICE, path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("ffplay"):
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path])


def speak_and_play(text):
    chunks = split_sentences(text)

    if len(chunks) == 1:
        mp3_data = tts_chunk(chunks[0])
        with open("response_0.mp3", "wb") as f:
            f.write(mp3_data)
        play_audio_file("response_0.mp3")
        return

    audio_queue = queue.Queue()
    gen_done = threading.Event()

    def generate_worker():
        for i, chunk in enumerate(chunks):
            try:
                mp3_data = tts_chunk(chunk)
                path = f"response_{i}.mp3"
                with open(path, "wb") as f:
                    f.write(mp3_data)
                audio_queue.put(path)
            except Exception as e:
                print(f"\n  TTS error on chunk {i}: {e}", flush=True)
        gen_done.set()

    threading.Thread(target=generate_worker, daemon=True).start()

    while True:
        try:
            play_audio_file(audio_queue.get(timeout=0.1))
        except queue.Empty:
            if gen_done.is_set() and audio_queue.empty():
                break


def speak(text):
    """Convenience: TTS and play a single string."""
    mp3_data = tts_chunk(text)
    with open("speak_tmp.mp3", "wb") as f:
        f.write(mp3_data)
    play_audio_file("speak_tmp.mp3")


# --- Idle Chatter ---

def get_idle_line():
    """Get a random idle chatter line (English TTS fallback mode)."""
    try:
        from idle_chatter import get_idle_line as _get
        return _get()
    except ImportError:
        return None


def get_time_greeting():
    """Get a time-aware greeting (English TTS fallback mode)."""
    try:
        from idle_chatter import get_time_greeting as _get
        return _get()
    except ImportError:
        return None


def _is_quiet_time() -> bool:
    try:
        from idle_chatter import is_quiet_time
        return is_quiet_time()
    except ImportError:
        return False


def play_idle_chatter():
    """Play one idle chatter sound, respecting quiet hours and mode."""
    if _is_quiet_time():
        return
    if FLOWER_MODE:
        try:
            from idle_chatter import get_idle_wav
            wav = get_idle_wav()
        except ImportError:
            wav = None
        if wav:
            play_audio_file(wav)
        return
    line = get_idle_line()
    if line:
        speak(line)


def play_startup_greeting():
    """Play startup greeting: a local startup WAV, or English TTS fallback."""
    if _is_quiet_time():
        return
    if FLOWER_MODE:
        try:
            from idle_chatter import get_startup_wav
            wav = get_startup_wav()
        except ImportError:
            wav = None
        if wav:
            play_audio_file(wav)
            return
    greeting = STARTUP_MESSAGE or get_time_greeting()
    if greeting:
        try:
            speak(greeting)
        except Exception as e:
            print(f"Startup speak error: {e}")


def play_tap_quip():
    """Play a short reaction when the button is tapped."""
    if FLOWER_MODE:
        try:
            from idle_chatter import get_quip_wav
            wav = get_quip_wav()
        except ImportError:
            wav = None
        if wav:
            play_audio_file(wav)
            return
    play_random_sound(QUIPS_DIR)


class IdleChatterTimer:
    """Speaks random lines when idle. Resets on any interaction."""

    def __init__(self, play_fn):
        """play_fn: no-arg callable that plays one idle chatter sound."""
        self._play = play_fn
        self._stop = threading.Event()
        self._reset = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._reset.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def reset(self):
        self._reset.set()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            wait = random.randint(IDLE_INTERVAL_MIN * 60, IDLE_INTERVAL_MAX * 60)
            for _ in range(wait):
                if self._stop.is_set():
                    return
                if self._reset.is_set():
                    self._reset.clear()
                    break
                time.sleep(1)
            else:
                try:
                    self._play()
                except Exception:
                    pass


class HourlyAnnouncer:
    """Announces the hour on every :00 by playing sono_le_HH.wav."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        from datetime import datetime, timedelta
        while not self._stop.is_set():
            now = datetime.now()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_s = (next_hour - now).total_seconds()
            if self._stop.wait(wait_s):
                return
            if _is_quiet_time():
                continue
            try:
                from idle_chatter import get_hourly_wav
                wav = get_hourly_wav(next_hour.hour)
            except ImportError:
                wav = None
            if wav:
                try:
                    play_audio_file(wav)
                except Exception:
                    pass


class QuietHoursWatcher:
    """Fires a callback when crossing the [WAKE..SLEEP] window boundary.

    Plays a 'keep_quiet' phrase at SLEEP_TIME and a 'psst' phrase at WAKE_TIME.
    """

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._last_quiet: bool | None = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                from idle_chatter import (
                    is_quiet_time,
                    get_status_keep_quiet_wav,
                    get_status_psst_wav,
                )
            except ImportError:
                return
            current = is_quiet_time()
            if self._last_quiet is not None and current != self._last_quiet:
                try:
                    wav = get_status_keep_quiet_wav() if current else get_status_psst_wav()
                    if wav:
                        play_audio_file(wav)
                except Exception:
                    pass
            self._last_quiet = current
            if self._stop.wait(30):
                return


class MusicMode:
    """Toggle on 4x tap. Plays 'MERAVIGLIAAAA!' then a random track from sounds/music/."""

    def __init__(self):
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def toggle(self) -> bool:
        if self._active:
            self._active = False
            print(" Music mode OFF")
            return False
        self._active = True
        print(" Music mode ON — MERAVIGLIAAAA!")
        try:
            from idle_chatter import get_music_entry_wav
            wav = get_music_entry_wav()
        except ImportError:
            wav = None
        if wav:
            try:
                play_audio_file(wav)
            except Exception:
                pass

        music_dir = Path(__file__).resolve().parent / "sounds" / "music"
        if music_dir.exists():
            tracks = list(music_dir.glob("*.wav")) + list(music_dir.glob("*.mp3"))
            if tracks:
                track = random.choice(tracks)
                print(f" Playing music: {track.name}")
                try:
                    play_audio_file(str(track))
                except Exception as e:
                    print(f" Music playback error: {e}")
            else:
                print(" No music files in sounds/music/ — add .wav/.mp3 files to play.")
        else:
            print(" sounds/music/ not found — create it and drop tracks there.")

        self._active = False
        return True


def play_special_message():
    """5x tap reward — plays one of the toy's 'thanks for being here' special phrases."""
    if FLOWER_MODE:
        try:
            from idle_chatter import get_special_message_wav
            wav = get_special_message_wav()
        except ImportError:
            wav = None
        if wav:
            play_audio_file(wav)


# --- Button Sounds ---

def play_random_sound(directory):
    """Play a random WAV from a directory."""
    import glob as _glob
    sounds = _glob.glob(str(Path(directory) / "*.wav"))
    if sounds:
        play_audio_file(random.choice(sounds))


def play_indicator(name):
    """Play a named indicator sound (e.g. 'chatter_on', 'memory_cleared')."""
    path = INDICATORS_DIR / f"{name}.wav"
    if path.exists():
        play_audio_file(str(path))


# --- Conversation Turn ---

def handle_turn(dev_idx, rate):
    """One full conversation turn: record → transcribe → LLM → speak."""
    audio, actual_rate = record_until_silence(dev_idx, rate)

    if audio.size == 0:
        print(" No audio captured.")
        return

    duration = audio.size / actual_rate
    peak = float(np.max(np.abs(audio)))
    print(f" Captured {duration:.1f}s (peak={peak:.3f})")

    if duration < MIN_SPEECH_DURATION:
        print(" Too short, skipping.")
        return
    if peak < 0.01:
        print(" Too quiet, skipping.")
        return

    if actual_rate != SAMPLE_RATE:
        audio = resample(audio, actual_rate, SAMPLE_RATE)
    save_wav("last_input.wav", audio, SAMPLE_RATE)

    print(" Transcribing...", end=" ", flush=True)
    try:
        text = transcribe("last_input.wav")
    except Exception as e:
        print(f"error: {e}")
        return
    print(f'You: "{text}"')

    if not text or len(text) < 2:
        print(" Empty transcript, skipping.")
        return

    print(" Thinking...", end=" ", flush=True)
    try:
        reply = ask_picoclaw(text)
    except Exception as e:
        print(f"error: {e}")
        return
    print(f'Flower: "{reply}"')

    if not reply or reply == "[no response]":
        print(" No response.")
        return

    print(" Speaking...", flush=True)
    try:
        speak_and_play(reply)
    except Exception as e:
        print(f" TTS error: {e}")


# --- Input Modes ---

def count_taps(button):
    """After a tap is detected, count additional taps within TAP_WINDOW."""
    taps = 1
    deadline = time.monotonic() + TAP_WINDOW
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if button.wait_for_press(timeout=remaining):
            button.wait_for_release()
            taps += 1
            deadline = time.monotonic() + TAP_WINDOW
        else:
            break
    return taps


def run_gpio_mode(dev_idx, rate):
    """Use a physical button on GPIO with multi-press gestures.

    Hold:        Push-to-talk recording
    Single tap:  Play random quip
    Double tap:  Toggle idle chatter on/off
    Triple tap:  Clear conversation memory (new session)
    """
    from gpiozero import Button as GPIOButton

    button = GPIOButton(GPIO_BUTTON_PIN, pull_up=True, bounce_time=0.05)
    print(f"GPIO mode: pin {GPIO_BUTTON_PIN}")
    print(f"  Hold=speak | Tap=quip | 2x=toggle chatter | 3x=reset memory | 4x=music | 5x=special\n")

    session = PICOCLAW_SESSION
    idle_chatter_on = IDLE_CHATTER

    play_startup_greeting()

    # Start idle chatter
    chatter = None
    if idle_chatter_on:
        chatter = IdleChatterTimer(play_idle_chatter)
        chatter.start()

    # Start hourly announcer
    hourly = None
    if HOURLY_ANNOUNCE:
        hourly = HourlyAnnouncer()
        hourly.start()

    # Start quiet-hours watcher (fires "keep quiet" / "psst" on boundary crossings)
    quiet_watcher = QuietHoursWatcher()
    quiet_watcher.start()

    music = MusicMode()

    # Remote trigger: write to /tmp/flower-command from PowerShell via SSH
    # to simulate button gestures without pressing the physical button.
    # Supported values: tap, tap2, tap3, tap4, tap5, hold
    trigger_file = Path("/tmp/flower-command")
    trigger_action = {"value": None, "lock": threading.Lock()}

    def trigger_watcher():
        while True:
            try:
                if trigger_file.exists():
                    action = trigger_file.read_text().strip().lower()
                    trigger_file.unlink(missing_ok=True)
                    with trigger_action["lock"]:
                        trigger_action["value"] = action
                    print(f" [remote trigger] {action}", flush=True)
            except Exception:
                pass
            time.sleep(0.2)

    threading.Thread(target=trigger_watcher, daemon=True).start()

    def pop_trigger():
        with trigger_action["lock"]:
            v = trigger_action["value"]
            trigger_action["value"] = None
            return v

    print("Ready.")

    while True:
        try:
            # Either wait for physical button press OR for a remote trigger
            pressed = False
            while not pressed:
                if button.is_pressed:
                    pressed = True
                    break
                action = pop_trigger()
                if action:
                    # Simulate the gesture directly
                    if action == "tap":
                        print(" [remote] Tap — quip")
                        if chatter: chatter.reset()
                        play_tap_quip()
                    elif action == "tap2":
                        print(" [remote] Double-tap — idle chatter toggle")
                        if chatter: chatter.reset()
                        idle_chatter_on = not idle_chatter_on
                        state = "ON" if idle_chatter_on else "OFF"
                        print(f"  idle chatter {state}")
                        if idle_chatter_on:
                            if not chatter:
                                chatter = IdleChatterTimer(play_idle_chatter)
                            chatter.start()
                        else:
                            if chatter:
                                chatter.stop()
                                chatter = None
                        try:
                            speak("[excited] Parlerò da solo!" if idle_chatter_on else "[whispers] Va bene, starò in silenzio.")
                        except Exception:
                            play_indicator("chatter_on" if idle_chatter_on else "chatter_off")
                    elif action == "tap3":
                        print(" [remote] Triple-tap — reset memory")
                        if chatter: chatter.reset()
                        session = f"voice:{int(time.time())}"
                        print(f"  new session: {session}")
                        play_indicator("memory_cleared")
                    elif action == "tap4":
                        print(" [remote] Quadruple-tap — music mode")
                        if chatter: chatter.reset()
                        music.toggle()
                    elif action == "tap5":
                        print(" [remote] Quintuple-tap — special message")
                        if chatter: chatter.reset()
                        play_special_message()
                    elif action == "hold":
                        print(" [remote] Hold — start recording")
                        if chatter: chatter.reset()
                        print("\n--- Recording ---")
                        handle_turn(dev_idx, rate)
                        print("\nReady.")
                    else:
                        print(f" [remote] unknown action: {action}")
                    break
                time.sleep(0.05)
            if not button.is_pressed:
                continue
            # Physical button path continues below
            pass
        except KeyboardInterrupt:
            if chatter:
                chatter.stop()
            if hourly:
                hourly.stop()
            quiet_watcher.stop()
            print("\nBye!")
            return

        press_time = time.monotonic()
        button.wait_for_release()
        hold_duration = time.monotonic() - press_time

        if chatter:
            chatter.reset()

        if hold_duration < HOLD_THRESHOLD:
            # --- Tap gesture ---
            taps = count_taps(button)

            if taps == 1:
                print(" Tap — quip")
                play_tap_quip()
            elif taps == 2:
                idle_chatter_on = not idle_chatter_on
                state = "ON" if idle_chatter_on else "OFF"
                print(f" Double-tap — idle chatter {state}")
                if idle_chatter_on:
                    if not chatter:
                        chatter = IdleChatterTimer(play_idle_chatter)
                    chatter.start()
                else:
                    if chatter:
                        chatter.stop()
                        chatter = None
                # Vocal confirmation via TTS
                try:
                    speak("[excited] Parlerò da solo!" if idle_chatter_on else "[whispers] Va bene, starò in silenzio.")
                except Exception:
                    play_indicator("chatter_on" if idle_chatter_on else "chatter_off")
            elif taps == 3:
                session = f"voice:{int(time.time())}"
                print(f" Triple-tap — memory cleared (new session: {session})")
                play_indicator("memory_cleared")
            elif taps == 4:
                print(" Quadruple-tap — music mode")
                music.toggle()
            elif taps >= 5:
                print(" Quintuple-tap — special message")
                play_special_message()
            continue

        # --- PTT hold — record and process ---
        # Recording already missed (we waited for release), so re-record
        # Actually: for the local version with VAD, just run a normal turn
        print("\n--- Recording ---")
        handle_turn(dev_idx, rate)
        print("\nReady.")


def run_keyboard_mode(dev_idx, rate):
    """Use Space key to trigger recording (for development/testing)."""
    import termios
    import tty

    print("Keyboard mode: press SPACE to talk, 'q' to quit.\n")

    play_startup_greeting()

    # Start idle chatter
    chatter = None
    if IDLE_CHATTER:
        chatter = IdleChatterTimer(play_idle_chatter)
        chatter.start()

    hourly = None
    if HOURLY_ANNOUNCE:
        hourly = HourlyAnnouncer()
        hourly.start()

    quiet_watcher = QuietHoursWatcher()
    quiet_watcher.start()

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            key = sys.stdin.read(1)
            if key in ('q', 'Q', '\x03'):
                break
            if key == ' ':
                if chatter:
                    chatter.reset()
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                handle_turn(dev_idx, rate)
                print("\n[SPACE] to speak, [q] to quit\n")
                tty.setraw(sys.stdin.fileno())
    except KeyboardInterrupt:
        pass
    finally:
        if chatter:
            chatter.stop()
        if hourly:
            hourly.stop()
        quiet_watcher.stop()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("\nBye!")


def has_gpio():
    """Check if we're running on a Pi with GPIO available."""
    try:
        from gpiozero import Button as GPIOButton
        GPIOButton(GPIO_BUTTON_PIN, pull_up=True).close()
        return True
    except Exception:
        return False


# --- Main ---

def main():
    dev_idx, dev_name = resolve_input_device()
    rate = find_working_rate(dev_idx)

    print("=== Flower Voice Assistant ===")
    print(f"Input:  {dev_name} ({rate}Hz)")
    print(f"Output: {OUTPUT_DEVICE}")
    print(f"Model:  {PICOCLAW_MODEL}")
    print(f"STT:    {STT_PROVIDER} ({ELEVENLABS_STT_MODEL if STT_PROVIDER == 'elevenlabs' else OPENAI_TRANSCRIBE_MODEL})")
    print(f"TTS:    {ELEVENLABS_MODEL_ID}")
    print()

    if INPUT_MODE == "gpio":
        run_gpio_mode(dev_idx, rate)
    elif INPUT_MODE == "keyboard":
        run_keyboard_mode(dev_idx, rate)
    else:  # auto
        if has_gpio():
            print("GPIO detected, using button input.")
            run_gpio_mode(dev_idx, rate)
        else:
            print("No GPIO, using keyboard input.")
            run_keyboard_mode(dev_idx, rate)


if __name__ == "__main__":
    main()
