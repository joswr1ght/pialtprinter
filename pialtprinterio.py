#!/usr/bin/env python3
import RPi.GPIO as GPIO
import socket
import signal
import sys
import time
import json
import Adafruit_DHT
import time
import board
import busio
import adafruit_veml6075
import threading
import queue
import traceback

PORT = 23456
DHTPIN = 24  # GPIO 24, Pi pin 18
FANPIN = 20  # GPIO 20, Pi pin 38
BALLASTPIN = 26  # GPIO 26, Pi pin 37
TARGETTEMP = 84  # Fahrenheit
exposurein_queue = None
statusout_queue = None
veml = None

PRINTEREXPOSETYPE_NONE = 0  # e.g. off
PRINTEREXPOSETYPE_TIME = 1
PRINTEREXPOSETYPE_UV = 2
PRINTEREXPOSETYPE_FIXED = 3
PRINTEREXPOSETYPES = ["none", "time", "UV", "fixed"]
PRINTEREXPOSETYPE = PRINTEREXPOSETYPE_NONE
FANSTATUS = 0  # off

sock = None  # TCP network socket server
i2c = None  # I2C interface for UV VEML6075 sensor


def gettemp():
    try:
        # Adafruit_DHT.read_retry() returns a tuple (humidity, temperature)
        temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHTPIN)[1]
    except:
        return json.dumps({"error": "gettemp: error reading sensor"})

    if temperature is None:
        return json.dumps({"error": "gettemp: temperature read returns None"})

    # Convert to Fahrenheit
    tempf = ((temperature*9)/5)+32
    return json.dumps({0: '{:.2f}'.format(tempf)})


def gethumidity():
    try:
        # Adafruit_DHT.read_retry() returns a tuple (humidity, temperature)
        humidity = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHTPIN)[0]
    except:
        return json.dumps({"error": "gettemp: error reading sensor"})

    if humidity is None:
        return json.dumps({"error": "gettemp: humidity read returns None"})

    return json.dumps({0: '{:.2f}'.format(humidity)})


def gettemphumidity():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(
            Adafruit_DHT.DHT22, DHTPIN)
    except:
        return json.dumps({"error": "gettemphumidity: error reading temp/humidity sensor"})

    if temperature is None:
        return json.dumps({"error": "gettemphumidity: temperature read returns None"})

    if humidity is None:
        return json.dumps({"error": "gettemphumidity: humidity read returns None"})

    # Convert to Fahrenheit
    tempf = ((temperature*9)/5)+32
    return json.dumps({0: ('{:.2f}'.format(tempf), '{:.2f}'.format(humidity))})


def settargettemp(target):
    global TARGETTEMP, targettempin_queue
    TARGETTEMP = target
    # Send new target temp to fan control thread
    targettempin_queue.put(target)
    return json.dumps({0: "OK"})


def gettargettemp():
    global TARGETTEMP
    return json.dumps({0: TARGETTEMP})


def getuv():
    global veml
    uva = veml.uva
    uvb = veml.uvb
    #print("UVA %f, UVB %f" % (uva, uvb))
    return json.dumps({0: (uva, uvb)})


def getexposuretype():
    global PRINTEREXPOSETYPE
    return json.dumps({0: PRINTEREXPOSETYPES[PRINTEREXPOSETYPE]})


def printeron(exposuretype=PRINTEREXPOSETYPE_FIXED):
    global GPIO, PRINTEREXPOSETYPE
    # Fan is controlled using the relay board channel 2
    GPIO.output(BALLASTPIN, GPIO.HIGH)
    PRINTEREXPOSETYPE = exposuretype
    return json.dumps({0: "OK"})


def printeroff():
    global GPIO, PRINTEREXPOSETYPE
    # Fan is controlled using the relay board channel 2
    GPIO.output(BALLASTPIN, GPIO.LOW)
    PRINTEREXPOSETYPE = PRINTEREXPOSETYPE_NONE
    return json.dumps({0: "OK"})


def printerontime(seconds):
    global exposurein_queue
    exposurein_queue.put({"targettime": seconds})
    return json.dumps({0: "OK"})


def printeronuv(uv):
    global exposurein_queue
    #print("DEBUG: Setting target UV to %d"%uv)
    exposurein_queue.put({"targetuv": uv})
    return json.dumps({0: "OK"})


def getprinterstatus():
    if PRINTEREXPOSETYPE == PRINTEREXPOSETYPE_NONE:
        return json.dumps({0: "off"})
    else:
        return json.dumps({0: "on"})


def getprinterexposetype():
    return json.dumps({0: PRINTEREXPOSETYPES[PRINTEREXPOSETYPE]})


def getprintertimeremaining():
    global statusout_queue
    try:
        status = statusout_queue.get_nowait()
    except queue.Empty:
        return json.dumps({"error": "no printer status information available"})

    try:
        return json.dumps({0: round(status["timeremaining"])})
    except KeyError:
        return json.dumps({"error": "no time remaining value set"})


def getprinteruvremaining():
    global statusout_queue
    try:
        status = statusout_queue.get_nowait()
    except queue.Empty:
        return json.dumps({"error": "no printer status information available"})
    
    print(status)
    try:
        return json.dumps({0: round(status["uvaremaining"])})
    except KeyError:
        return json.dumps({"error": "no UV-A remaining value set"})


### Methods not part of the API for socket access

# Same as getuv(), but return as list not JSON
def getuvraw():
    try:
        uvread = json.loads(getuv())
        if "error" in uvread.keys():
            return (0, 0)  # ERROR
    except:
        traceback.print_exc()
        return (0, 0)  # ERROR
    return (uvread['0'][0], uvread['0'][1])


# Process inbound data, returning JSON response
def parsedata(data):

    # Parse and validate data
    try:
        data = json.loads(data.decode('utf-8'))
    except json.decoder.JSONDecodeError:
        return json.dumps({"error": "JSON decode error"})


    if type(data) != dict:
        return json.dumps({"error": "Invalid data type"})

    if len(data) != 1:
        return json.dumps({"error": "Invalid record length"})

    # Process verb in request

    if "gettemp" in data.keys():
        return gettemp()

    if "gethumidity" in data.keys():
        return gethumidity()

    if "gettemphumidity" in data.keys():
        return gettemphumidity()

    if "gettargettemp" in data.keys():
        return gettargettemp()

    if "settargettemp" in data.keys():
        return settargettemp(data.get("settargettemp"))

    if "getuv" in data.keys():
        return getuv()

    if "getexposuretype" in data.keys():
        return getexposuretype()

    if "printeron" in data.keys():
        return printeron()

    if "printeroff" in data.keys():
        return printeroff()

    if "printerontime" in data.keys():
        return printerontime(data.get("printerontime"))

    if "printeronuv" in data.keys():
        return printeronuv(data.get("printeronuv"))

    if "getprinterstatus" in data.keys():
        return getprinterstatus()

    if "getprinterexposetype" in data.keys():
        return getprinterexposetype()

    if "getprintertimeremaining" in data.keys():
        return getprintertimeremaining()

    if "getprinteruvremaining" in data.keys():
        return getprinteruvremaining()

    return json.dumps({"error": "unsupported command"})


def fanon():
    GPIO.output(FANPIN, GPIO.HIGH)


def fanoff():
    GPIO.output(FANPIN, GPIO.LOW)


class SignalHandler:
    global sock
    #: The stop event that's shared by this handler and threads.
    stopper = None

    #: The pool of worker threads
    workers = None

    def __init__(self, stopper, workers):
        self.stopper = stopper
        self.workers = workers

    def __call__(self, signum, frame):
        """
        This will be called by the python signal module

        https://docs.python.org/3/library/signal.html#signal.signal
        """

        print("SignalHandler: exiting thread(s)")
        self.stopper.set()

        # for worker in self.workers:
        #    worker.join()

        # print("DEBUG: GPIO cleanup")
        # GPIO.cleanup()
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

        sys.exit(0)


class FanControl(threading.Thread):
    def __init__(self, targettempin_queue, fanstatusout_queue, stopper):
        super().__init__()
        self.fanstatusout_queue = fanstatusout_queue
        self.targettempin_queue = targettempin_queue
        self.stopper = stopper
        self.fanstatus = 0

    def run(self):
        targettemp = self.targettempin_queue.get()
        # print("DEBUG: target temp is %f"%(targettemp))

        while not self.stopper.is_set():
            # print("DEBUG: stopper.is_set() returns %d"%(self.stopper.is_set()))
            try:
                # get temp
                temp = float(json.loads(gettemp())['0'])
                # print("DEBUG: temp is %f"%(temp))

                try:
                    targettemp = self.targettempin_queue.get(False)
                except queue.Empty:
                    # print("Empty queue")
                    pass  # target temp has not changed

                if (temp > targettemp and self.fanstatus == 0):
                    fanon()
                    self.fanstatus = 1
                    self.fanstatusout_queue.put(self.fanstatus)
                elif (temp <= TARGETTEMP and self.fanstatus == 1):
                    fanoff()
                    self.fanstatus = 0
                    self.fanstatusout_queue.put(self.fanstatus)
            except:
                traceback.print_exc()
                continue
            finally:
                # print("DEBUG: Sleeping")
                time.sleep(3)

        print("## FanControl: Stopper is set, exiting.")
        fanoff()

# exposurein_queue is a dictionary: { "targettime" : N, "targetuv" : N } (set one or the other)
class PrinterControl(threading.Thread):
    def __init__(self, exposurein_queue, statusout_queue, stopper):
        super().__init__()
        self.exposurein_queue = exposurein_queue
        self.statusout_queue = statusout_queue  # LIFO queue
        self.stopper = stopper
        self.printerstatus = 0  # off

    def run(self):
        while not self.stopper.is_set():
            try:
                exposurein = self.exposurein_queue.get_nowait()
            except queue.Empty:
                time.sleep(1)
                continue

            # Check queue dictionary for time-based or UV-based exposure type, process accordingly
            if ("targettime" in exposurein.keys() and exposurein["targettime"] > 0):
                # Run the printer for the specified time in seconds
                print("DEBUG: printing time-based for %d seconds" % exposurein["targettime"])
                self.printtime(exposurein["targettime"])
            elif ("targetuv" in exposurein.keys() and exposurein["targetuv"] > 0):
                # Run the printer for the specified UV measurement total
                print("DEBUG: printing UV unit-based for %d units" % exposurein["targetuv"])
                self.printuv(exposurein["targetuv"])
            else:
                self.statusout_queue.put({"error": "target time and target UV cannot both be zero"})

        print("## PrinterControl: Stopper is set, exiting.")
        printeroff()

    def printtime(self, seconds):
        printeron(PRINTEREXPOSETYPE_TIME)
        starttime = time.time()
        cumulativeuva = 0
        cumulativeuvb = 0

        while (starttime+seconds > time.time()) and not self.stopper.is_set():
            # Populate the statusout_queue (LIFO) with time remaining
            uv = getuvraw()
            cumulativeuva += uv[0]
            cumulativeuvb += uv[1]

            # Clear the queue. This seems stupid, but I don't want a huge memory hog of unnecessary data in the LIFO.
            self.clearqueue()
            
            # Queue is a dictionary consisting of timeremaining, cumulativeuva, and cumulativeuvb keys and values
            self.statusout_queue.put({"timeremaining": starttime+seconds - time.time(),
                                      "cumulativeuva": cumulativeuva,
                                      "cumulativeuvb": cumulativeuvb,
                                      })
            time.sleep(.5)
        
        printeroff()
        self.clearqueue()
        # Queue is a dictionary consisting of timeremaining, cumulativeuva, and cumulativeuvb keys and values
        self.statusout_queue.put({"timeremaining": 0,
                                "cumulativeuva": cumulativeuva,
                                "cumulativeuvb": cumulativeuvb,
                                })

    # Expose for the target exposure value in UVA units
    def printuv(self, targetexposureuva):
        cumulativeuva = 0
        cumulativeuvb = 0
        starttime = time.time()

        print("DEBUG: turning printer on for UV exposure of %d"%targetexposureuva)
        printeron(PRINTEREXPOSETYPE_UV)

        while (targetexposureuva > cumulativeuva) and not self.stopper.is_set():
            # Populate the statusout_queue (LIFO) with time remaining
            uv = getuvraw()
            cumulativeuva += uv[0]
            cumulativeuvb += uv[1]
            #print("DEBUG: UV printing status -- target %d, cumulative %d"%(targetexposureuva, cumulativeuva))

            # Clear the queue. This seems stupid, but I don't want a huge memory hog of unnecessary data in the LIFO.
            self.clearqueue()

            # Queue is a dictionary consisting of timeremaining, cumulativeuva, and cumulativeuvb keys and values
            self.statusout_queue.put({"uvaremaining": targetexposureuva-cumulativeuva,
                                          "cumulativeuva": cumulativeuva,
                                          "cumulativeuvb": cumulativeuvb,
                                          "targetexposureuva": targetexposureuva,
                                          "cumulativetime": time.time() - starttime
                                          })
            time.sleep(.5)
        print("DEBUG: UV printing complete (%d units)"%cumulativeuva)
        printeroff()

    def clearqueue(self):
        # CLear the statusout queue
        while True:
            try:
                self.statusout_queue.get_nowait()
            except queue.Empty:
                break

if __name__ == "__main__":

    print("# PiAltPrinter Command Handler v0.1\n")

    # Stopper for the fan control thread upon SIGINT
    stopper = threading.Event()

    # Queues to influence the FANSTATUS on/off variable
    targettempin_queue = queue.Queue()
    fanstatusout_queue = queue.Queue()

    # Queue to manage the printer
    exposurein_queue = queue.Queue()
    statusout_queue = queue.LifoQueue()  # LIFO YO

    # Set the target temp in the queue
    targettempin_queue.put(TARGETTEMP)

    # Create fan control worker
    fanworker = FanControl(targettempin_queue, fanstatusout_queue, stopper)

    # Create printer control worker
    printerworker = PrinterControl(exposurein_queue, statusout_queue, stopper)

    # create the signal handler and connect it to worker threads
    handler = SignalHandler(stopper, [fanworker, printerworker])
    signal.signal(signal.SIGINT, handler)

    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BALLASTPIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(FANPIN, GPIO.OUT, initial=GPIO.LOW)

    print("## Starting fan control worker")
    fanworker.start()

    print("## Starting print control worker")
    printerworker.start()

    i2c = busio.I2C(board.SCL, board.SDA)
    try:
        veml = adafruit_veml6075.VEML6075(i2c, integration_time=800)
    except:
        sys.stderr.write("\n\nCannot read from VEML6075 device over I2C bus.\n")
        sys.stderr.write("Maybe try: sudo rmmod i2c_bcm2835 && sudo modprobe i2c_bcm2835\n")
        sys.stderr.write("Because reasons.\n\n")
        traceback.print_exc()
        sys.exit(-1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = ("127.0.0.1", PORT)
    sock.bind(serv)

    sock.listen(1)
    while True:
        print('## Waiting for a connection')
        connection, client_address = sock.accept()

        try:
            print('### Connection from', client_address)

            while True:
                data = connection.recv(64)
                if data:
                    #print("Data: %s" % data)
                    connection.send(parsedata(data).encode())
                else:
                    #print("no more data.")
                    break
        finally:
            connection.close()
