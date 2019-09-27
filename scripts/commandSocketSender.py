import socket
import sys
import time
from threading import Thread

HOST = '127.0.0.1'
PORT = 5570

s = socket.socket()
s.connect((HOST, PORT))
connection = True

def listener(s):
    global connection
    while 1:
        message = s.recv(4096).decode('utf-8')
        if message == "":
            print("INFO: server closed connection.")
            connection = False
            return
        print("{}".format(message))

def sender(s):
    global connection
    while 1:
        msg = input()
        if msg == "close":
            s.close()
            connection = False
            return
        s.send(msg.encode('utf-8'))


try:
    listenerThread = Thread(target=listener, args=(s,))
    listenerThread.daemon = True
    senderThread = Thread(target=sender, args=(s,))
    senderThread.daemon = True
    listenerThread.start()
    senderThread.start()

    while connection:
        time.sleep(1)

    sys.exit(0)

except KeyboardInterrupt:
    s.close()
    sys.exit(0)
