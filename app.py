#!/usr/bin/env python3
from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import socket  
from time import sleep
import pdb

PIN=40
sock = None
app = Flask(__name__)

# Write to the socket a time for delay
def senddelaytime(sock, delay):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv = ("127.0.0.1", 23457)
    sock.connect(serv)
    sock.sendall(bytes(delay, 'UTF-8'))
    sock.close()

@app.route('/')
def index():
    shutter=request.args.get('shutter')
    if (shutter != None):
        senddelaytime(sock, shutter)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
