# Guida Setup — Dalla microSD al Pi operativo

Questa guida ti porta dal **Raspberry Pi spento in scatola** al **Pi acceso, configurato, e raggiungibile via SSH** con il minimo numero di passi manuali. L'auto-install installa da solo tutte le dipendenze di sistema, configura I2S, ALSA, mic e silence streamer. Tu devi solo preparare la SD una volta, inserirla, aspettare.

## Indice

1. [Cosa ti serve](#cosa-ti-serve)
2. [Panoramica del flusso](#panoramica-del-flusso)
3. [Step 1 — Flash della SD con Raspberry Pi Imager](#step-1--flash-della-sd-con-raspberry-pi-imager)
4. [Step 2 — Drop di `flower_firstboot.sh` sulla SD](#step-2--drop-di-flower_firstbootsh-sulla-sd)
5. [Step 3 — Modifica `user-data` (cloud-init)](#step-3--modifica-user-data-cloud-init)
6. [Step 4 — Espulsione e primo boot del Pi](#step-4--espulsione-e-primo-boot-del-pi)
7. [Step 5 — Verifica che il Pi sia pronto](#step-5--verifica-che-il-pi-sia-pronto)
8. [Step 6 — Copia del progetto dal PC al Pi](#step-6--copia-del-progetto-dal-pc-al-pi)
9. [Step 7 — Install finale sul Pi](#step-7--install-finale-sul-pi)
10. [Step 8 — Personalizza USER.md](#step-8--personalizza-usermd)
11. [Step 9 — Start e test](#step-9--start-e-test)
12. [Troubleshooting](#troubleshooting)
13. [Cheat sheet comandi](#cheat-sheet-comandi)

---

## Cosa ti serve

- **Raspberry Pi Zero 2 WH** (con header pre-saldati)
- **MicroSD 32 GB** (o più)
- **Lettore microSD** collegato al PC
- **Alimentatore 5V micro USB** stabile (~2A)
- **WiFi di casa** (SSID + password)
- **PC** con questo repo clonato localmente, `.env` compilato con la tua API key ElevenLabs, e opzionalmente i WAV di supporto in `voice-assistant/sounds/`

## Panoramica del flusso

```
+------------------------------------------------------------------+
| 1. Flash SD con Pi Imager + preconfig (~5 min)                   |
| 2. Drop flower_firstboot.sh nella partizione bootfs (~1 min)     |
| 3. Modifica user-data con il blocco write_files + runcmd (~1 min)|
| 4. Espelli SD, inseriscila nel Pi, accendi (~1 min)              |
| 5. Aspetta ~30 min (auto-install in background)                  |
| 6. ssh pi@your-flower.local -> verifica                          |
| 7. scp -r /path/to/ai-flower-assistant pi@your-flower.local:~/   |
| 8. bash scripts/install_from_local.sh                            |
|                                                                  |
| Tempo manuale totale:   ~10 min distribuiti su 2 sessioni        |
| Tempo di attesa:        ~30-35 min in background                 |
+------------------------------------------------------------------+
```

> Nota: le versioni recenti di Raspberry Pi Imager (2024+) **non usano più `firstrun.sh`** per la preconfigurazione. Usano **cloud-init** con il file **`user-data`** (formato YAML). Questa guida è scritta per il meccanismo cloud-init. Se cerchi `firstrun.sh` sulla SD e non lo trovi — è normale.

---

## Step 1 — Flash della SD con Raspberry Pi Imager

### 1.1 Installa Pi Imager

Scarica da: https://www.raspberrypi.com/software/

### 1.2 Apri Pi Imager e scegli device/OS

1. Inserisci la microSD nel lettore del PC.
2. Apri **Raspberry Pi Imager**.
3. **CHOOSE DEVICE** → **Raspberry Pi Zero 2 W**.
4. **CHOOSE OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**.
   Deve essere **Lite** (senza GUI desktop) e **64-bit** (ARM64 è supportato dal Zero 2 W ed è più efficiente).
5. **CHOOSE STORAGE** → seleziona la tua microSD.

### 1.3 Preconfigurazione (EDIT SETTINGS)

Clicca **NEXT** → compare la finestra "Use OS customisation?".

Clicca **EDIT SETTINGS**.

**Scheda GENERAL**:
- Set hostname: `your-flower` (o il nome che preferisci)
- Set username and password:
  - Username: `pi`
  - Password: scegli una tua e **ricordala**
- Configure wireless LAN:
  - SSID: il nome esatto del tuo WiFi di casa
  - Password: la password del tuo WiFi
  - Wireless LAN country: il codice paese dove vivi (IT, DE, AT, ...)
- Set locale settings:
  - Time zone: es. `Europe/Rome`
  - Keyboard layout: es. `it`

**Scheda SERVICES**:
- Enable SSH → Use password authentication

**Scheda OPTIONS**: lascia default.

Clicca **SAVE** → **YES** per applicare → **YES** per confermare la scrittura.

### 1.4 Scrittura

Pi Imager scrive la SD (~5 min) e poi verifica (~3 min). Alla fine dice **"Write Successful"**.

**Non rimuovere ancora la SD** — dobbiamo aggiungere 2 cose.

---

## Step 2 — Drop di `flower_firstboot.sh` sulla SD

Dopo la scrittura, il SO monta **due partizioni** della SD:

- **bootfs** (FAT32, ~512 MB, visibile in Explorer/Finder)
- **rootfs** (ext4, non leggibile da Windows — se Windows propone di formattare, clicca **Annulla**)

### Copia lo script

1. Apri il file manager.
2. Apri la partizione `bootfs`.
3. Copia `scripts/flower_firstboot.sh` del repo dentro `bootfs` (drag and drop).

Ora `bootfs` contiene `flower_firstboot.sh` accanto agli altri file (`config.txt`, `cmdline.txt`, `user-data`, ecc.).

---

## Step 3 — Modifica `user-data` (cloud-init)

Il file `user-data` è un YAML che cloud-init legge al primo boot. Pi Imager lo ha riempito con la tua preconfig (hostname, user, WiFi, SSH). Noi aggiungiamo 2 sezioni: **`write_files:`** (crea il file di servizio systemd) e **`runcmd:`** (abilita il servizio al primo boot).

### Edita `user-data` in un editor che rispetta i fine riga Unix

1. Nella partizione `bootfs`, apri `user-data` con un editor tipo **Notepad++** / **VS Code** (preservano CRLF/LF correttamente). **Non usare WordPad o Word** — rompono i fine-riga e cloud-init fallisce.

2. Vedrai un contenuto con hostname, utente `pi`, password hash, WiFi, ecc.

3. **Alla fine del file, aggiungi esattamente** queste due sezioni (lascia una riga vuota prima):

   ```yaml
   write_files:
   - path: /etc/systemd/system/flower-firstboot.service
     content: |
       [Unit]
       Description=Flower first-boot setup
       After=network-online.target
       Wants=network-online.target

       [Service]
       Type=oneshot
       ExecStart=/bin/bash /boot/firmware/flower_firstboot.sh
       StandardOutput=journal
       StandardError=journal
       RemainAfterExit=yes

       [Install]
       WantedBy=multi-user.target

   runcmd:
   - systemctl enable flower-firstboot.service
   ```

   **YAML è sensibile all'indentazione:**
   - Usa solo spazi, mai TAB.
   - Ogni 2 spazi è un livello di nesting.
   - Non rimuovere né aggiungere spazi a inizio riga.

4. **Salva** (`Ctrl+S`) e chiudi.

### Verifica

Da PowerShell (sostituisci `E:` con la lettera della tua SD):

```powershell
Get-Content E:\user-data | Select-String -Pattern "write_files|runcmd|flower"
```

Dovresti vedere righe con `write_files:`, il path del `.service`, `Description=Flower first-boot setup`, `ExecStart=...`, `runcmd:`, `systemctl enable flower-firstboot.service`.

Se non le vedi, l'edit non è andato a buon fine — riapri e riprova.

---

## Step 4 — Espulsione e primo boot del Pi

### 4.1 Espelli la SD in sicurezza

Click destro su `bootfs` → **Espelli** → aspetta conferma → rimuovi la SD.

### 4.2 Inserisci nel Pi e alimenta

1. Infila la microSD nel Pi Zero 2 WH (slot sul retro del PCB).
2. Collega il cavo alla porta **PWR** (la più vicina all'angolo).
3. Connetti l'alimentatore alla presa.

Il LED verde sul Pi inizia a lampeggiare (attività disco).

### 4.3 Cosa succede (aspetta ~30 min)

**Boot 1 (~2 min)** — cloud-init applica la preconfig (hostname, utente `pi`, SSH, WiFi). Abilita il servizio `flower-firstboot.service`. Triggera un reboot per applicare la config.

**Boot 2 (~30 sec)** — WiFi si connette. Il servizio `flower-firstboot.service` parte (dopo `network-online.target`). Inizia l'auto-install di `flower_firstboot.sh`.

**Auto-install (~20-30 min)** — in background:
- `apt update` + installazione pacchetti (python, alsa-utils, mpg123, ffmpeg, ecc.)
- Enable I2S in `/boot/firmware/config.txt`
- Disabilita audio onboard BCM
- Scrive `~/.asoundrc` con dmixer + softvol
- Installa servizio `flower-mic-gain` (volume capture del mic USB + AGC)
- Installa servizio `flower-silence` (silence streamer per evitare pop dell'amp)
- Si auto-disabilita alla fine
- Schedula un reboot finale per attivare l'I2S

**Boot 3 (~1 min)** — sistema pronto con I2S attivo.

Totale: **~30-35 min dal power-on al sistema pronto**.

### 4.4 Monitoraggio in tempo reale (opzionale)

Dopo ~3 min dal power-on puoi collegarti via SSH e seguire il log:

```
ssh pi@your-flower.local
sudo tail -f /var/log/flower-firstboot.log
```

---

## Step 5 — Verifica che il Pi sia pronto

Dopo ~30 min:

```
ssh pi@your-flower.local
ls -la ~/.flower-firstboot-done
```

Se il file esiste → setup completato.

Verifica l'audio I2S:

```
aplay -l
```

Dovresti vedere card con USB Audio (C-Media) e MAX98357A.

---

## Step 6 — Copia del progetto dal PC al Pi

Dalla shell del tuo PC:

```
scp -r /path/to/ai-flower-assistant pi@your-flower.local:~/
```

---

## Step 7 — Install finale sul Pi

```
ssh pi@your-flower.local
cd ~/ai-flower-assistant
bash scripts/install_from_local.sh
```

Questo script:
1. Crea un Python venv in `voice-assistant/.venv/`.
2. `pip install` di: numpy, requests, python-dotenv, sounddevice, gpiozero, lgpio.
3. Scarica e installa PicoClaw.
4. Copia i file character (`SOUL.md`, `IDENTITY.md`, `AGENTS.md`) in `~/.picoclaw/workspace/`.
5. Crea `USER.md` dal template.
6. Installa i servizi systemd (`flower-voice`, `flower-silence`, `picoclaw-gateway`).
7. Health check finale.

Durata: ~3-5 min.

---

## Step 8 — Personalizza USER.md

```
nano ~/.picoclaw/workspace/USER.md
```

Sostituisci i placeholder con i tuoi dati (nome, città, fuso orario, interessi).

Salva: `Ctrl+O` → `Enter` → `Ctrl+X`.

---

## Step 9 — Start e test

### Test manuale

```
cd ~/ai-flower-assistant/voice-assistant
source .venv/bin/activate
python voice_assistant.py
```

Dovresti vedere:
```
=== Flower Voice Assistant ===
Input:  USB Audio Device (48000Hz)
Output: ...
Model:  kimi-turbo
STT:    elevenlabs (scribe_v1)
TTS:    eleven_v3

Ready.
```

`Ctrl+C` per uscire.

### Avvio automatico al boot

```
sudo systemctl enable --now picoclaw-gateway flower-voice flower-silence wifi-powersave-off
sudo systemctl status flower-voice
```

---

## Troubleshooting

### `ssh: connect to host your-flower.local: Connection refused` oppure host non trovato

- Il Pi non ha ancora finito il primo boot. Aspetta altri 5-10 min.
- Il Pi non si è connesso al WiFi. Controlla SSID/password.
- mDNS/avahi non attivo. Usa l'IP diretto:
  - Trova l'IP dal router
  - `ssh pi@192.168.x.y`

### `aplay -l` non mostra MAX98357A

- L'overlay I2S non si è applicato. Riavvia:
  ```
  sudo reboot
  ```
- Verifica `/boot/firmware/config.txt`:
  ```
  grep -E "i2s|max98357" /boot/firmware/config.txt
  ```
  Dovresti vedere `dtparam=i2s=on` e `dtoverlay=max98357a`.
- Se manca, `flower_firstboot.sh` non è stato eseguito. Controlla:
  ```
  systemctl status flower-firstboot.service
  cat /var/log/flower-firstboot.log
  ```

### Under-voltage warning (LED rosso lampeggia)

```
vcgencmd get_throttled
```

- `throttled=0x0` → OK.
- Altri valori → alimentatore insufficiente. Serve 5V 2.5A stabile.

### `voice_assistant.py` non trova il mic o lo speaker

- `aplay -l` e `arecord -l` — devono mostrare entrambe le card.
- Mic USB deve essere via OTG adapter sulla porta dati del Pi Zero.
- `sudo alsa force-reload`.
- Env var nel `.env`: `INPUT_DEVICE_HINT=USB`, `OUTPUT_DEVICE_HINT=MAX98357A`.

### cloud-init non ha processato `user-data`

Se dopo il primo boot hostname non è quello previsto, o SSH non è attivo, cloud-init ha fallito a leggere `user-data`.

Cause comuni:
- **Fine riga Windows (CRLF)** invece di Unix (LF) — Notepad++: **Edit** → **EOL Conversion** → **Unix (LF)** → Salva.
- **Indentazione mista TAB + spazi** — YAML rifiuta. Sempre solo spazi.
- **Encoding** — UTF-8 senza BOM.

---

## Cheat sheet comandi

### Dal PC

```
ssh pi@your-flower.local
scp -r /path/to/ai-flower-assistant pi@your-flower.local:~/
scp /path/to/ai-flower-assistant/voice-assistant/.env pi@your-flower.local:~/ai-flower-assistant/voice-assistant/
```

### Sul Pi

```bash
# Install iniziale
cd ~/ai-flower-assistant
bash scripts/install_from_local.sh

# Personalizza USER.md
nano ~/.picoclaw/workspace/USER.md

# Test manuale
cd voice-assistant && source .venv/bin/activate && python voice_assistant.py

# Avvio automatico
sudo systemctl enable --now picoclaw-gateway flower-voice flower-silence wifi-powersave-off
sudo systemctl status flower-voice
journalctl -u flower-voice -f

# Audio diagnostics
aplay -l
arecord -l
speaker-test -D plughw:CARD=MAX98357A,DEV=0 -c 1 -t sine

# Power diagnostics
vcgencmd get_throttled
vcgencmd measure_temp

# Reboot
sudo reboot
sudo shutdown now
```
