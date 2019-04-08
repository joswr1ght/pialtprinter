# pialtprinter
Raspberry Pi Alternative Printing Control

This code is used for controlling a Raspberry Pi for the purposes of alternative printing (Cyanotype, Platinum/Palladium, Argyrotype, etc.)

The `pialtprinterio.py` script is the _controlling_ function, interacting using a relay to control AC power for banks of UV lights, as well
as reading from two data-logging peripherals:

  + DHT11 temperature and humidity sensor
  + VEML6075 UV light sensor

Using these peripherals, `pialtprinterio.py` controls one or more fans to provide cooling for consistency in UV exposure, and logs the
amount of cumulative UV light in a file (default: `/tmp/pialtprinter-time.txt`). By creating an initial exposure using the time-based function,
you can identify the total UV light generated during that time and produce subsequent exposures with consistency using the UV light target 
(which will be more accurate for subsequent exposures due to fluxuations in the UV light source).

The `app.py` code is the web UI to control the printing process, interacting with `pialtprointerio.py` using a local socket and JSON
messages.
