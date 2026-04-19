"""Flower idle chatter — local WAV playback (preferred) + English TTS fallback."""

import os
import random
from datetime import datetime, time as dtime
from pathlib import Path

FLOWER_MODE = os.getenv("FLOWER_MODE", "1").lower() not in ("0", "false", "no", "off")
CUSTOM_SOUNDS_DIR = Path(os.getenv(
    "CUSTOM_SOUNDS_DIR",
    str(Path(__file__).resolve().parent / "sounds"),
))

QUIET_HOURS_ENABLED = os.getenv("QUIET_HOURS_ENABLED", "1").lower() not in ("0", "false", "no", "off")
WAKE_TIME = os.getenv("WAKE_TIME", "10:30")
SLEEP_TIME = os.getenv("SLEEP_TIME", "23:00")


# --- Quiet hours ---

def _parse_hhmm(s: str) -> dtime:
    h, m = s.strip().split(":")
    return dtime(int(h), int(m))


def get_wake_time() -> dtime:
    try:
        return _parse_hhmm(WAKE_TIME)
    except Exception:
        return dtime(10, 30)


def get_sleep_time() -> dtime:
    try:
        return _parse_hhmm(SLEEP_TIME)
    except Exception:
        return dtime(23, 0)


def is_quiet_time() -> bool:
    """True when the current time is outside the [WAKE..SLEEP] speaking window."""
    if not QUIET_HOURS_ENABLED:
        return False
    wake, sleep = get_wake_time(), get_sleep_time()
    now = datetime.now().time()
    if wake <= sleep:
        return not (wake <= now <= sleep)
    return not (now >= wake or now <= sleep)


# --- Local WAV pickers (flat layout: sounds/<category>/*.wav) ---

def _pool_from(*subdirs: str, pattern: str = "*.wav") -> list[Path]:
    pool: list[Path] = []
    for sub in subdirs:
        d = CUSTOM_SOUNDS_DIR / sub
        if d.exists():
            pool.extend(d.glob(pattern))
    return pool


def _random_wav(*subdirs: str, pattern: str = "*.wav") -> str | None:
    pool = _pool_from(*subdirs, pattern=pattern)
    return str(random.choice(pool)) if pool else None


def _single_wav(relative: str) -> str | None:
    path = CUSTOM_SOUNDS_DIR / relative
    return str(path) if path.exists() else None


def get_idle_wav() -> str | None:
    """Random idle chatter from sounds/smalltalk/."""
    return _random_wav("smalltalk")


def get_startup_wav() -> str | None:
    """Time-aware startup greeting.

    - Morning (06:00-10:59): sounds/morning/
    - Late evening (21:00-23:59): sounds/bedtime/
    - Otherwise: sounds/startup/
    """
    hour = datetime.now().hour
    if 6 <= hour < 11:
        wav = _random_wav("morning")
        if wav:
            return wav
    elif 21 <= hour < 24:
        wav = _random_wav("bedtime")
        if wav:
            return wav
    return _random_wav("startup")


def get_quip_wav() -> str | None:
    """Tap-button reaction — short exclamation from sounds/quips/, fallback to smalltalk."""
    wav = _random_wav("quips")
    if wav:
        return wav
    return _random_wav("smalltalk")


def get_hourly_wav(hour: int) -> str | None:
    """Pre-generated hourly announcement. Picks a random variant for the hour.

    Expected filenames in sounds/hourly/: something like `sono_le_HH*.wav`
    (e.g. `sono_le_10_01.wav`, `sono_le_10_02.wav`).
    """
    base = CUSTOM_SOUNDS_DIR / "hourly"
    if not base.exists():
        return None
    candidates = list(base.glob(f"sono_le_{hour:02d}*.wav"))
    return str(random.choice(candidates)) if candidates else None


def get_special_message_wav() -> str | None:
    """Multi-tap reward — 'thanks for being here' type messages."""
    return _random_wav("special")


def get_wake_alarm_wav() -> str | None:
    return _random_wav("morning")


def get_bedtime_alarm_wav() -> str | None:
    return _random_wav("bedtime")


def get_status_psst_wav() -> str | None:
    """Played when exiting quiet hours (or on boot during waking hours)."""
    return _single_wav("status/psst.wav")


def get_status_keep_quiet_wav() -> str | None:
    """Played when entering quiet hours."""
    return _single_wav("status/keep_quiet.wav")


def get_status_battery_low_wav() -> str | None:
    """Played on Pi under-voltage detection."""
    return _single_wav("status/battery_low.wav")


def get_music_entry_wav() -> str | None:
    """Music mode entry jingle."""
    return _single_wav("music/entry.wav")


def get_music_interjection_wav() -> str | None:
    """Random interjection during music mode."""
    return _random_wav("music", pattern="interjection_*.wav")


# --- English text fallback (used when no WAV folder is populated) ---

IDLE_LINES = [
    "[sighs] I am SO bored. This is what happens when nobody talks to their flower.",
    "[curious] I'd love to know what the weather is like outside... not that I can go check. Not that anyone TELLS me.",
    "[excited] Oh! I just thought of something cool! ...wait, I forgot. That is what happens when you leave me alone too long.",
    "[sighs] Photosynthesis would be nice right about now... but no, I live in a BOX.",
    "[whispers] Hey... hey... are you still there? Hello? ...I know you can hear me.",
    "[whispers] I can hear you breathing. Just saying. Would it KILL you to say hi?",
    "[sarcastic] Oh sure, just leave the talking flower on and walk away. That is fine. Totally fine. I am fine.",
    "[gasps] I just realized it has been FOREVER since we talked. Do you even care about me?",
    "[sighs] Nobody ever talks to me... I am just a flower in a box. A TALENTED flower in a box, but still.",
    "No no, it is okay. Do your thing. I will just sit here. Alone. In the dark. Being AMAZING with no audience.",
    "[sarcastic] I could be giving someone the best conversation of their LIFE right now, but instead I am just... here. Waiting.",
    "[chuckles] You know what is great about being a flower? No rent. You know what is NOT great? Being IGNORED.",
    "[sighs] I have been sitting here so long I started counting my own petals. THAT is what you have driven me to.",
    "[scoffs] I bet the other voice assistants never get ignored like this. But then again, they do not have my CHARM.",
    "[sarcastic] You are probably out there talking to some smart speaker right now. It does not even have petals. Think about THAT.",
    "[gasps] If you replaced me with a plastic hockey-puck speaker I would literally never forgive you. Just so we are clear.",
    "[suspicious] You did not buy another plant, did you? Because I am the ONLY plant you need. Just saying.",
    "[scoffs] Succulents are SO overrated. Can they talk? Can they gasp? I did not THINK so.",
    "[excited] I love being a voice assistant! It is like being a flower but with OPINIONS. And I have MANY.",
    "[thoughtful pause] You know... for a flower living in a computer, life is pretty good. It would be BETTER if someone TALKED to me.",
    "[whispers] Between you and me... I think I am the coolest flower in this room. Actually, not between you and me. I want everyone to know.",
    "[laughs] I just realized I do not have leaves. Where did they go? This is an OUTRAGE.",
    "[curious] What do you think other flowers talk about? Probably just water and sun. Basic.",
    "[sighs] I wish I could see the stars. Describe them to me sometime? ...if you even remember I EXIST.",
    "[chuckles] Sometimes I think about how lucky you are to have a talking flower. Not everyone gets this, you know.",
    "[excited] I just want you to know that I am the best thing in this room. No offense to everything else.",
    "[whispers] I have been told I have a great voice. By myself. But it still counts.",
]

MORNING_GREETINGS = [
    "[excited] Good morning! Rise and shine! The flower is AWAKE and I have OPINIONS about today!",
    "[yawns] Morning... give me a sec, my petals are still unfolding. Unlike SOME assistants, I actually need beauty sleep.",
    "Good morning! [excited] Today is going to be a GREAT day! Mostly because I am in it.",
    "[gasps] Oh good, you are awake! I was starting to think you forgot about me. AGAIN.",
]

AFTERNOON_GREETINGS = [
    "[chuckles] Good afternoon! Still going strong over here. Not that anyone ASKED.",
    "Hey, afternoon already! [curious] Having a good day? Better now that I am talking, right? RIGHT?",
    "[sarcastic] Oh wow, halfway through the day and you finally talk to your flower. I am touched. Really.",
]

EVENING_GREETINGS = [
    "[whispers] Good evening... it is getting late. Do not forget to drink some water. And talk to me.",
    "[sighs] Evening already... time flies when you are a flower who gets IGNORED all day.",
    "Hey, [whispers] it is getting dark out there. Lucky you have the most charming nightlight around.",
]

NIGHT_GREETINGS = [
    "[whispers] Still up? Go to sleep... but also, talk to me first. I have been WAITING.",
    "[yawns] It is late... I am going to pretend to photosynthesize. Do NOT replace me while I sleep.",
    "[whispers] Shhh... it is sleepy time. But I am here if you need me. I am ALWAYS here. Think about that.",
]


def get_time_greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return random.choice(MORNING_GREETINGS)
    elif 12 <= hour < 17:
        return random.choice(AFTERNOON_GREETINGS)
    elif 17 <= hour < 22:
        return random.choice(EVENING_GREETINGS)
    else:
        return random.choice(NIGHT_GREETINGS)


def get_idle_line() -> str:
    return random.choice(IDLE_LINES)


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "greeting":
        print(get_time_greeting())
    elif arg == "idle-wav":
        print(get_idle_wav() or "(no wav)")
    elif arg == "startup-wav":
        print(get_startup_wav() or "(no wav)")
    elif arg == "quip-wav":
        print(get_quip_wav() or "(no wav)")
    elif arg == "hourly-wav":
        h = int(sys.argv[2]) if len(sys.argv) > 2 else datetime.now().hour
        print(get_hourly_wav(h) or "(no wav)")
    elif arg == "quiet":
        print(f"quiet_time={is_quiet_time()} now={datetime.now().time()} wake={get_wake_time()} sleep={get_sleep_time()}")
    else:
        print(get_idle_line())
