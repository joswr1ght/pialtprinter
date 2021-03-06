#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import RPi.GPIO as GPIO
import socket  
import json

PORT = 23456
app = Flask(__name__)

def getremaining():
    try:
        exposuretypejson = json.loads(sendmessage('{"getexposuretype": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return dict(printerstatus="Error decoding printer response")
    
    if "error" in exposuretypejson.keys():
        return dict(printerstatus="No current exposure")

    #print(exposuretypejson)
    exposuretype = exposuretypejson["0"]
    if exposuretype == "time":
        return dict(printerstatus=gettimeremaining())
    elif exposuretype == "UV":
        return dict(printerstatus=getuvremaining())
    elif exposuretype == "none":
        return dict(printerstatus="Printer is OFF")
    else:
        return dict(printerstatus="Unrecognized exposure type: %s"%exposuretypejson)

def isprinteron():
    try:
        exposuretypejson = json.loads(sendmessage('{"getexposuretype": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return dict(printerstatus="Error decoding printer response")
    
    if "error" in exposuretypejson.keys():
        return dict(printerstatus="No current exposure")

    return not (exposuretypejson["0"] == "none")

def gettimeremaining():
    try:
        response = json.loads(sendmessage('{"getprintertimeremaining": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return "Error decoding printer response"

    if "error" in response.keys():
        return "Error reading printer status: %s"%response["error"]
    remaining = response["0"]
    seconds = remaining%60
    minutes = int(remaining/60)

    return "%d min, %d sec remaining"%(minutes, seconds)

# Returns temp in Fahrenheit
def gettemperature():
    try:
        response = json.loads(sendmessage('{"gettemp": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return "Error decoding printer response"

    if "error" in response.keys():
        return "Error reading temperature: %s"%response["error"]
    return response["0"]

# Returns temp in Fahrenheit
def gettargettemperature():
    try:
        response = json.loads(sendmessage('{"gettargettemp": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return "Error decoding printer response"

    if "error" in response.keys():
        return "Error reading target temperature: %s"%response["error"]
    return response["0"]

# Returns current humidity
def gethumidity():
    try:
        response = json.loads(sendmessage('{"gethumidity": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return "Error decoding printer response"

    if "error" in response.keys():
        return "Error reading humidity: %s"%response["error"]

    return response["0"]


def getuvremaining():
    try:
        response = json.loads(sendmessage('{"getprinteruvremaining": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return "Error decoding printer response"

    if "error" in response.keys():
        return "Error reading printer status: %s"%response["error"]

    return "%d UV units remaining"%response["0"]

def printtime(time):
    timeval = time.split(":")
    if len(timeval) == 3:   # Submitted as HH:MM:SS
        printtime = int(timeval[0])*3600 + int(timeval[1])*60 + int(timeval[2])
    elif len(timeval) == 2: # Submitted as MM:SS
        printtime = int(timeval[0])*60 + int(timeval[1])
    else:                   # Submitted as SS
        printtime = int(timeval[0])

    try:
        message = '{"printerontime": %d}'%printtime
        #print("DEBUG: %s"%message)
        response = json.loads(sendmessage(message).decode('UTF-8'))
    except json.JSONDecodeError:
        return -1

    if "error" in response.keys():
        return -2

    return 0

def printuv(uv):
    try:
        message = '{"printeronuv": %d}'%int(uv)
        #print("DEBUG: %s"%message)
        response = json.loads(sendmessage(message).decode('UTF-8'))
    except json.JSONDecodeError:
        return -1

    if "error" in response.keys():
        return -2

    return 0

def stopprinter():
    try:
        exposuretypejson = json.loads(sendmessage('{"printeroff": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return dict(printerstatus="Error decoding printer response for stopprinter")
    if "error" in exposuretypejson.keys():
        return dict(printerstatus="Stop command returned an error: " + exposuretypejson["error"])
    return 0

def sendmessage(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = ("127.0.0.1", PORT)
    sock.connect(serv)
    sock.sendall(bytes(message, 'UTF-8'))
    data = sock.recv(1024)
    sock.close()
    return data



@app.route('/')
def index():
    if (request.args.get('time') != None):
        if (not isprinteron()):
            printtime(request.args.get('time'))
    elif (request.args.get('uv') != None):
        if (not isprinteron()):
            printuv(request.args.get('uv'))
        
    return render_template('index.html')

@app.route('/stop')
def stop():
    stopprinter()
    return render_template('stop.html')

@app.route('/printerstatus')
def printerstatus():
    return jsonify([getremaining(), gettemperature(), gettargettemperature(), gethumidity()])

if __name__ == '__main__':
    app.run(debug=False, threaded=True, host='0.0.0.0')
    
