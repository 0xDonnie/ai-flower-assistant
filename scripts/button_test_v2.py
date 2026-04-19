#!/usr/bin/env python3
"""
Identifica la coppia di cavetti del bottone del fiore.
Versione 2: richiede cambio di stato esplicito (HIGH -> LOW durante pressione),
quindi non ha falsi positivi con pin floating o rumore.

Setup:
  ARANCIO -> Pi pin 11 (GPIO17)
  ROSSO   -> Pi pin 13 (GPIO27)
  GIALLO  -> Pi pin 15 (GPIO22)
  MARRONE -> Pi pin 16 (GPIO23)
  NERO    -> Pi pin 18 (GPIO24)
"""
from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep, time

COLORS = {17: 'ARANCIO', 27: 'ROSSO', 22: 'GIALLO', 23: 'BIANCO', 24: 'MARRONE'}

print("\n=== IDENTIFICAZIONE BOTTONE v2 ===\n")
print("Per ogni giro:")
print("  1. NON premere il bottone (verifichiamo che sia rilasciato)")
print("  2. Quando dice 'PREMI', premi e tieni per 3 secondi")
print("  3. Rilascia quando dice 'RILASCIA'\n")
input("Premi ENTER per iniziare...")

found_pair = None

for out_pin, out_color in COLORS.items():
    out_dev = DigitalOutputDevice(out_pin, initial_value=False)
    in_devs = {p: (COLORS[p], DigitalInputDevice(p, pull_up=True)) for p in COLORS if p != out_pin}

    print(f"\n--- Giro con {out_color} ---")
    sleep(0.5)

    # Step 1: verify all inputs read HIGH (not pressed)
    print("  Verifica stato riposo (NON premere)...")
    already_low = []
    for pin, (color, dev) in in_devs.items():
        if not dev.value:
            already_low.append(color)

    if already_low:
        print(f"  ATTENZIONE: {', '.join(already_low)} gia' LOW senza pressione -> corto fisico o cavo staccato")

    # Step 2: wait for user to press
    print("  PREMI il bottone per 3 secondi")
    sleep(3)

    # Step 3: check which input went LOW after press (and wasn't low already)
    pressed_low = []
    for pin, (color, dev) in in_devs.items():
        if not dev.value and color not in already_low:
            pressed_low.append(color)

    if pressed_low:
        print(f"  DURANTE PRESSIONE: {', '.join(pressed_low)} e' diventato LOW")
    else:
        print(f"  Nessun cambio di stato rilevato")

    print("  RILASCIA il bottone")
    sleep(1)

    out_dev.close()
    for _, dev in in_devs.values():
        dev.close()

    # Match only if a cable went LOW during press and wasn't already low
    if pressed_low:
        found_pair = (out_color, pressed_low[0])
        break

print("\n================================")
if found_pair:
    print(f"BOTTONE VERO = {found_pair[0]} + {found_pair[1]}")
else:
    print("NESSUNA COPPIA VALIDA TROVATA.")
    print("Possibili cause: bottone staccato dalle tracce, PCB rotta, o dome")
    print("rubber assente/malposizionato.")
print("================================\n")
