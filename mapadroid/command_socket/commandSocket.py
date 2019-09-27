import logging
import socket
from threading import Thread
from mapadroid.command_socket.commandSocketSession import CommandSocketSession
from loguru import logger


class CommandSocket(object):

    def __init__(self, ws_server, args):
        self.port = args.commandsocket_port
        self.host = args.commandsocket_ip
        self.max_length = 4096
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ws_server = ws_server
        self.connection_count = 0

    def run(self):
        bound = False
        while not bound:
            try:
                self.serversocket.bind((self.host, self.port))
                bound = True
            except OSError:
                continue
        self.serversocket.listen(10)
        logger.info("Waiting for connections on port {}".format(self.port))

        while 1:
            self.connection_count += 1
            clientsocket = self.serversocket.accept()
            session = CommandSocketSession(clientsocket, self)
            sessionThread = Thread(name="cs_session_{}".format(self.connection_count), 
                                   target=session.run)
            sessionThread.daemon = True
            sessionThread.start()
