#!/usr/bin/env python3
import time
import board
import busio
import adafruit_veml6075
import sys

try:
    i2c = busio.I2C(board.SCL, board.SDA)
except ValueError:
    print("Cannot read from I2C device. Did you try sudo rmmod i2c_bcm2835 && sudo modprobe i2c_bcm2835")
    sys.exit(1)

veml = adafruit_veml6075.VEML6075(i2c, integration_time=100)

print("Integration time: %d ms" % veml.integration_time)

while True:
    print(veml.uv_index)
    print(veml.uva)
    time.sleep(1)
