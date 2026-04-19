# Hardware Guide

This guide describes the reference build: a Raspberry Pi Zero 2 WH driving a MAX98357A I2S amp, a C-Media USB mic, and a single-button flower-shaped enclosure. Any enclosure with a similar button + speaker arrangement will work.

## Bill of Materials

| Item | Purpose | Notes |
|------|---------|-------|
| Flower-shaped enclosure with button + speaker | Physical toy body | Any toy/case with a mono speaker and a momentary button |
| Raspberry Pi Zero 2 WH (512 MB, 1 GHz) | Brain (pre-soldered headers) | WH variant saves you soldering pins |
| Dupont jumper wires (M-F, M-M, F-F) | Connecting components | Elegoo 120pc kit is plenty |
| Soldering iron set | Solder wires to the toy's sub-board | 30-80W, LCD-controlled |
| Multimeter | Identify pins with continuity, check speaker impedance | Any cheap DMM |
| Micro-USB OTG adapter | USB devices to Pi | 15 cm flexible is ideal |
| MAX98357A I2S amp breakout | Speaker output | 7-pin header + 2-pin screw terminal |
| USB mic (C-Media / CM108) | Mic input | Any C-Media PnP USB mic works |

## Architecture

Speaker output via I2S (MAX98357A), mic input via USB:

```
USB C-Media mic -(USB)-> Pi -(I2S)-> MAX98357A -> toy speaker
                          |
                     Button (GPIO17)
                     (dome switch on the toy's sub-board)
```

## Toy PCB details (reference build)

The reference toy has two PCBs connected by a 6-wire ribbon cable. We bypass the main board (which contains the factory audio/MCU) and tap directly into the sub-board — which carries the button and the speaker.

### Main board — BYPASSED

- Main processor IC, memory/audio codec, passives.
- Ribbon cable desoldered from this board. It is no longer used.

### Sub-board — KEEPING

- **Button:** NOT a tactile push switch. It's a **cross-shaped open contact pad** (dome switch) — two concentric contact areas bridged by a conductive rubber dome inside the toy's plastic housing when pressed.
- **Speaker wires:** Red (+) and black (-) soldered to board pads. They are independent of the ribbon cable but connect through PCB traces to the ribbon cable pads.
- **Row of gold pads** along the bottom edge — purpose unconfirmed (possibly LEDs or battery contacts).
- **Ribbon cable:** original 6-wire cable desoldered from the main board. 5 Dupont wires are soldered to the ribbon cable pads on the sub-board.

## Wire map (confirmed by multimeter)

| Dupont wire color | Function | How confirmed |
|-------------------|----------|---------------|
| **Black** | Button (side 1) | Continuity with button contact pad |
| **White** | Button (side 2) | Continuity with button contact pad |
| **Purple** | Speaker (one side) | Resistance: purple+gray reads ~8 ohm (speaker coil) |
| **Gray** | Speaker (other side) | Same as above |
| **Blue** | Battery (likely) | Not button, not speaker |

**Key findings:**
- The speaker IS routed through the ribbon cable via purple and gray wires.
- The red/black wires on the board connect through PCB traces to purple/gray Dupont wires.
- Button press bridges Black and White wires together.
- Speaker impedance: ~8 ohm.

> Your toy's board will almost certainly have a different wire-color scheme. Always identify wires with continuity tests before wiring anything to the Pi.

## Current wiring

### Button -> Pi GPIO

- **Black** Dupont wire -> **GPIO17** (physical pin 11)
- **White** Dupont wire -> **GND** (physical pin 9)
- Software uses internal pull-up. Button press shorts Black+White, pulling GPIO17 to GND.
- Tested and working with gpiozero.

### MAX98357A (Speaker Output) -> Pi GPIO

| MAX98357A Pin | Pi Pin |
|---------------|--------|
| BCLK | GPIO18 (pin 12) |
| LRC | GPIO19 (pin 35) |
| DIN | GPIO21 (pin 40) |
| GND | GND (pin 6) |
| VIN | 5V (pin 2) |
| GAIN | GND (pin 14) via jumper — selects max hardware gain (15 dB) |

Then connect MAX98357A speaker output (+/-) to the two speaker wires (purple/gray in the reference build — use whatever your toy uses).

### Enabling I2S on the Pi

```bash
# /boot/firmware/config.txt
dtparam=i2s=on
dtoverlay=max98357a
```

**IMPORTANT:** Do NOT use `dtoverlay=googlevoicehat-soundcard`. The VoiceHAT-style driver has its own amp enable/disable codec that causes cracking and popping. The clean `max98357a` overlay drives the same hardware without the codec overhead.

### ALSA configuration (~/.asoundrc)

The Pi Zero 2 W has a known over-amplification bug with MAX98357A — audio is pushed too hot at the I2S level. The fix is a `softvol` ALSA layer to attenuate the signal:

```
pcm.dmixer {
    type dmix
    ipc_key 1024
    slave {
        pcm "hw:CARD=MAX98357A,DEV=0"
        period_size 2048
        buffer_size 16384
        rate 48000
        channels 1
        format S32_LE
    }
}

pcm.softvol {
    type softvol
    slave.pcm "dmixer"
    control { name "SoftMaster"; card MAX98357A }
    min_dB -20.0
    max_dB 0.0
}

pcm.speaker {
    type plug
    slave.pcm "softvol"
}

pcm.!default {
    type asym
    playback.pcm "speaker"
    capture.pcm "plughw:CARD=Device,DEV=0"
}
```

Key points:
- **dmix** allows multiple audio streams (silence streamer + actual audio) to share the device.
- **softvol** at ~90% tames the Pi Zero 2 W over-amplification.
- **channels 1** is critical — the toy has a single mono speaker; sending stereo causes artifacts.
- A background silence streamer (`aplay -D speaker -f S16_LE -r 48000 -c 1 /dev/zero`) keeps the I2S clock running so the amp never powers off (prevents power-on/off pop).
- Using `CARD=<name>` references instead of `hw:0,0` / `hw:1,0` survives card-number flips between boots.

### USB Mic (C-Media) settings

```bash
# Max capture volume (+23 dB) — the default is too quiet
amixer -c 0 cset numid=8 35

# Enable Auto Gain Control
amixer -c 0 cset numid=9 1

# Persist across reboots
sudo alsactl store
```

The voice pipeline also applies: highpass filter (200 Hz, removes hum) + noise gate + normalization before sending to STT.

### Audio card numbers after reboot

Card numbers are assigned by the kernel at boot and may change if USB devices are unplugged/replugged. Typical layout:

| Card | Device | Used for |
|------|--------|----------|
| 0 | USB Audio Device (C-Media) | Mic input |
| 1 | MAX98357A | Speaker output (I2S) |
| 2 | vc4-hdmi | HDMI audio (unused) |

Because the app (and `.asoundrc`) reference cards by NAME (`CARD=MAX98357A`, `CARD=Device`), card number flips don't matter.

## Key warnings

1. **The button is NOT a tactile switch** in many toy builds — it's often open contact pads (cross-shaped dome switch). A rubber dome in the housing bridges the contacts when pressed.
2. **The speaker IS routed through the ribbon cable** via specific Dupont wires, not directly from the board-soldered red/black wires.
3. **Pi Zero 2 WH has pre-soldered headers** — no Pi-side soldering is required; use Dupont wires.
4. **Pi Zero 2 W has only 512 MB RAM (~416 MB usable)** — don't run multiple heavy processes simultaneously.
5. **Do NOT use `googlevoicehat-soundcard` overlay** — causes cracking. Use `max98357a` instead.
6. **Toy speakers are mono** — always output mono audio (channels=1). Sending stereo to a single speaker causes crackling artifacts.
7. **Pi Zero 2 W over-amplifies I2S** — use ALSA softvol to attenuate. Without it, audio is distorted.
8. **USB mic needs max capture volume** — default is too quiet. Set numid=8 to 35 and enable AGC.
9. **Card numbers change** — always verify with `aplay -l` / `arecord -l` after hardware changes. Prefer `CARD=<name>` references in ALSA configs.
