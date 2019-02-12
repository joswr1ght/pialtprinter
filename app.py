#!/usr/bin/env python3
from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import socket  
from time import sleep
import pdb
import json

PORT = 23456

sock = None
app = Flask(__name__)

def sendmessage(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = ("127.0.0.1", PORT)
    sock.connect(serv)
    sock.sendall(bytes(message, 'UTF-8'))
    data = sock.recv(1024)
    sock.close()
    return data

def getremaining():
    exposuretype = ""
    try:
        exposuretypejson = json.loads(sendmessage('{"getexposuretype": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return -2
    
    if "error" in exposuretypejson.keys():
        return "No current exposure"

    exposuretype = exposuretypejson["0"]
    if exposuretype == "time":
        return gettimeremaining()
    elif exposuretype == "UV":
        return getuvremaining()
    else:
        return "Unrecognized exposure type"

def gettimeremaining():
    try:
        response = json.loads(sendmessage('{"getprintertimeremaining": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return -2

    if "error" in response.keys():
        return -1

    return response["0"] + " seconds remaining"

def getuvremaining():
    try:
        response = json.loads(sendmessage('{"getprinteruvremaining": 0}').decode('UTF-8'))
    except json.JSONDecodeError:
        return -2

    if "error" in response.keys():
        return -1

    return response["0"] + " UV units remaining"


@app.route('/')
def index():
    #shutter=request.args.get('shutter')
    #if (shutter != None):
    #    senddelaytime(sock, shutter)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
    