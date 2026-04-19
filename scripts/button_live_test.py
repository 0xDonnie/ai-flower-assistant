#!/usr/bin/env python3
"""Test live del bottone del fiore. GPIO17 (pin 11) + GND.
Stampa 'PREMUTO' quando il bottone è schiacciato, 'idle' altrimenti."""
from gpiozero import Button
import time

b = Button(17, pull_up=True)
print("Test bottone GPIO17. Premi Ctrl+C per uscire.\n")
while True:
    print('PREMUTO' if b.is_pressed else 'idle')
    time.sleep(0.3)
