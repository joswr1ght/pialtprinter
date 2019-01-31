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


DHTPIN=24 # GPIO 24, Pi pin 18
FANPIN=20 # GPIO 20, Pi pin 38
BALLASTPIN=26 # GPIO 26, Pi pin 37
TARGETTEMP=84 # Fahrenheit
targettempin_queue = None

PRINTEREXPOSETYPE_NONE=0 # e.g. off
PRINTEREXPOSETYPE_TIME=1
PRINTEREXPOSETYPE_UV=2
PRINTEREXPOSETYPE_FIXED=3
PRINTEREXPOSETYPES = [ "none", "time", "UV", "fixed" ]
PRINTEREXPOSETYPE=None
FANSTATUS=0 # off

sock = None # TCP network socket server
i2c = None # I2C interface for UV VEML6075 sensor


def gettemp():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHTPIN)
    except:
        return json.dumps({"error":"gettemp: error reading sensor"})
    
    if temperature is None:
        return json.dumps({"error":"gettemp: temperature read returns None"})

    # Convert to Fahrenheit
    tempf = ((temperature*9)/5)+32
    return json.dumps({0: '{:.2f}'.format(tempf)})

def gethumidity():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHTPIN)
    except:
        return json.dumps({"error":"gettemp: error reading sensor"})
    
    if humidity is None:
        return json.dumps({"error":"gettemp: humidity read returns None"})

    return json.dumps({0: '{:.2f}'.format(humidity)})

def gettemphumidity():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, DHTPIN)
    except:
        return json.dumps({"error":"gettemp: error reading temp/humidity sensor"})
    
    if temperature is None:
        return json.dumps({"error":"gettemp: temperature read returns None"})

    # Convert to Fahrenheit
    tempf = ((temperature*9)/5)+32
    return json.dumps({ 0: ('{:.2f}'.format(tempf), '{:.2f}'.format(humidity))})
    

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
    try:
        veml = adafruit_veml6075.VEML6075(i2c, integration_time=500)
    except:
        return json.dumps({"error":"getuv: error reading UV sensor"})
    return json.dumps({0: (veml.uva, veml.uvb)})

def printeron():
    global GPIO, PRINTEREXPOSETYPE
    # Fan is controlled using the relay board channel 2
    GPIO.output(FANPIN, GPIO.HIGH)
    PRINTEREXPOSETYPE=PRINTEREXPOSETYPE_FIXED
    return json.dumps({0: "OK"})

def printeroff():
    global GPIO, PRINTEREXPOSETYPE
    # Fan is controlled using the relay board channel 2
    GPIO.output(FANPIN, GPIO.LOW)
    PRINTEREXPOSETYPE=PRINTEREXPOSETYPE_FIXED
    return json.dumps({0: "OK"})

def printerontime(seconds):
    return json.dumps({0: "NYI"})

def printeronexposure(uv):
    return json.dumps({0: "NYI"})

def getprinterstatus():
    if PRINTEREXPOSETYPE == PRINTEREXPOSETYPE_NONE:
        return json.dumps({0: "off"})
    else:
        return json.dumps({0: "on"})

def getprinterexposetype():
    return json.dumps({0: PRINTEREXPOSETYPES[PRINTEREXPOSETYPE]})

def getprinterontimeremaining():
    return json.dumps({0: "NYI"})

def getprinteruvremaining():
    return json.dumps({0: "NYI"})



### Methods not part of the API for socket access

# Process inbound data, returning JSON response
def parsedata(data):
    
    # Parse and validate data
    try:
        data = json.loads(data.decode('utf-8'))
    except json.decoder.JSONDecodeError:
        return json.dumps({"error":"JSON decode error"})
    
    if type(data) != dict:
        return json.dumps({"error":"Invalid data type"})
    
    if len(data) != 1:
        return json.dumps({"error":"Invalid record length"})
    
    ### Process verb in request

    if "gettemp" in data.keys():
        return gettemp()
    
    if "gethumidity" in data.keys():
        return gethumidity()

    # XXX
    if "gettemphumidity" in data.keys():
        return gettemphumidity()

    if "gettargettemp" in data.keys():
        return gettargettemp()

    if "settargettemp" in data.keys():
        return settargettemp(data.get("settargettemp"))

    # XXX
    if "getuv" in data.keys():
        return getuv()
    # XXX
    if "printeron" in data.keys():
        return printeron()
    # XXX
    if "printeroff" in data.keys():
        return printeroff()
    # XXX    
    if "printerontime" in data.keys():
        return printerontime(data.get("printerontime"))
    # XXX    
    if "printeronuv" in data.keys():
        return printeronexposure(data.get("printeronuv"))
     # XXX   
    if "getprinterstatus" in data.keys():
        return getprinterstatus()
    # XXX    
    if "getprinterexposetype" in data.keys():
        return getprinterexposetype()
   # XXX
    if "getprinterontimeremaining" in data.keys():
        return getprinterontimeremaining()
    # XXX        
    if "getprinteruvremaining" in data.keys():
        return getprinteruvremaining()

    return json.dumps({"error":"unsupported command"})    

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

        #for worker in self.workers:
        #    worker.join()
        
        #print("DEBUG: GPIO cleanup")
        #GPIO.cleanup()
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
        print("DEBUG: target temp is %f"%(targettemp))
        
        while not self.stopper.is_set():
            #print("DEBUG: stopper.is_set() returns %d"%(self.stopper.is_set()))
            try:
                # get temp
                temp = float(json.loads(gettemp())['0'])
                print("DEBUG: temp is %f"%(temp))
                
                try:
                    targettemp = self.targettempin_queue.get(False)
                except queue.Empty:
                    #print("Empty queue")
                    pass # target temp has not changed
                
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
                #print("DEBUG: Sleeping")
                time.sleep(3)
        
        print("FanControl: Stopper is set, exiting.")


if __name__ == "__main__":    

    # Stopper for the fan control thread upon SIGINT
    stopper = threading.Event()

    # Queues to influence the FANSTATUS on/off variable
    targettempin_queue = queue.Queue()
    fanstatusout_queue = queue.Queue()

    # Set the target temp in the queue
    targettempin_queue.put(TARGETTEMP)

    # Create fan contorl worker
    fanworker = FanControl(targettempin_queue, fanstatusout_queue, stopper)
    
    # create the signal handler and connect it. worker is a list in case I add other threads in the future.
    handler = SignalHandler(stopper, [fanworker])
    signal.signal(signal.SIGINT, handler)

    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BALLASTPIN, GPIO.OUT, initial = GPIO.LOW)
    GPIO.setup(FANPIN, GPIO.OUT, initial = GPIO.LOW)
    

    print("Starting fan control worker")
    fanworker.start()

    #i2c = busio.I2C(board.SCL, board.SDA)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = ("127.0.0.1", 23457)
    sock.bind(serv)

    sock.listen(1)
    while True:
        print ('waiting for a connection')
        connection, client_address = sock.accept()

        try:
            print ('connection from', client_address)

            while True:
                data = connection.recv(64)
                if data:
                    print ("Data: %s" % data)
                    connection.send(parsedata(data).encode())
                else:
                    print ("no more data.")
                    break
        finally:
            connection.close()
