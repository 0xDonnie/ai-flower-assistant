#!/usr/bin/env python3
"""
Identifica quale coppia dei 5 cavetti colorati del fiore e' il BOTTONE.
Collegamenti (Pi pin <- colore):
  pin 11 (GPIO17) <- ARANCIO
  pin 13 (GPIO27) <- ROSSO
  pin 15 (GPIO22) <- GIALLO
  pin 16 (GPIO23) <- MARRONE
  pin 18 (GPIO24) <- NERO
"""
from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep, time

COLORS = {17: 'ARANCIO', 27: 'ROSSO', 22: 'GIALLO', 23: 'MARRONE', 24: 'NERO'}

print("\n=== IDENTIFICAZIONE BOTTONE ===\n")

found_pair = None
for out_pin, out_color in COLORS.items():
    out_dev = DigitalOutputDevice(out_pin, initial_value=False)
    in_devs = {p: DigitalInputDevice(p, pull_up=True) for p in COLORS if p != out_pin}
    print(f"Giro con {out_color}: premi e TIENI PREMUTO il bottone del fiore per 3 secondi...")
    sleep(0.3)
    found = None
    start = time()
    while time() - start < 5:
        for in_pin, in_dev in in_devs.items():
            if not in_dev.value:
                found = COLORS[in_pin]
                break
        if found:
            break
        sleep(0.02)
    out_dev.close()
    for d in in_devs.values():
        d.close()
    if found:
        found_pair = (out_color, found)
        break
    else:
        print(f"  nessuna risposta con {out_color}\n")

if found_pair:
    print(f"\n*** BOTTONE = {found_pair[0]} + {found_pair[1]} ***")
    remaining = [c for c in COLORS.values() if c not in found_pair]
    print(f"\nI 3 restanti ({', '.join(remaining)}) sono: 2 speaker + 1 batteria\n")
else:
    print("\nNessuna coppia trovata. Verifica: bottone premuto? saldature ok?\n")
