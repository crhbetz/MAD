import logging
import socket
import select
import json
import sys
import ast
from threading import Thread
from loguru import logger


class CommandSocketSession(object):

    def __init__(self, clientsocket, commandsocket):
        (self.client, self.address) = clientsocket
        self.ws_server = commandsocket.ws_server
        self.ws_current_users = self.ws_server.get_reg_origins()
        self.max_length = commandsocket.max_length

    def _is_good_json(self, string):
        logger.debug("Testing for valid command json: {}".format(string))
        try:
            json_object = json.loads(string)
        except ValueError as e:
            return False
        if "device" in json_object and "command" in json_object:
            return True
        else:
            return False

    def _is_json(self, string):
        try:
            json_object = json.loads(string)
        except ValueError as e:
            return False
        return True

    def wait_for_message(self, timeout=False):
        resp = None
        while not resp:
            try:
                if not timeout:
                    resp = self.client.recv(self.max_length).decode('utf-8').rstrip()
                else:
                    ready = select.select([self.client], [], [], timeout)
                    if ready[0]:
                        resp = self.client.recv(self.max_length).decode('utf-8').rstrip()
                    else:
                        return False
            except UnicodeDecodeError as e:
                logger.error("Received invalid message!")
                self.send_message("Invalid message, try again!")
                continue
        if resp == '':
            logger.debug("Connection from {} closed.".format(self.address))
            self.client = False
            return False
        logger.debug("Received message: " + resp)
        return resp

    def send_message(self, message):
        if message:
            try:
                messagestr = message.rstrip() + "\r\n"
                messagestr = messagestr.encode('utf-8')
                self.client.send(messagestr)
                return True
            except TypeError:
                self.client.send(message)
                return True
            except Exception as e:
                logger.error("Exception during send_message!")
                logger.exception(e)
                return False
        else:
            logger.warning("Tried sending invalid (False / None) message.")
            return False

    def close_connection(self, message=False):
        if self.client:
            if message:
                self.send_message(message)
            self.client.close()
        sys.exit(0)

    def run(self):
        logger.debug("New connection from {}".format(self.address))
        worker = False
        command = self.wait_for_message(1) or None
        if command and self._is_good_json(command):
            command = json.loads(command)
            if command['device'] in self.ws_server.list_workers():
                workerRef = self.ws_current_users.get(command["device"], None)[1]
                logger.debug("ref: {}".format(workerRef))
                if command["command"] == "block":
                    logger.info("try to block worker {}".format(command["device"]))
                    workerRef._communicator.forceBlock(60)
                    logger.info("worker {} block released.".format(command["device"]))
                else:
                    result = self.ws_server.send_and_wait(command["device"], workerRef,
                                                          command["command"], 30)
                    logger.debug("Command {} on worker {} resulted in: {}"
                        .format(command["command"], command["device"], result))
                    logger.debug("Command {} on device {} finished."
                        .format(command["command"], command["device"]))
                    if result:
                        message = {"result": result.rstrip()}
                    else:
                        message = {"result": None}
                    try:
                        self.send_message(json.dumps(message))
                    except TypeError:
                        self.send_message(result)
            else:
                msg = "Device '{}' not available".format(command["device"])
                logger.debug(msg)
                self.send_message(msg)
            self.close_connection()
        elif command:
            self.send_message("Invalid JSON. Non-interactive mode requires " +
                              "valid JSON input containing 'device' and " +
                              "'command' strings")
            self.close_connection()
        while self.client:
            while not worker:
                availableWorkers=self.ws_server.dict_workers()
                logger.debug("No worker selected. Available workers: {}".format(availableWorkers))
                self.send_message("Hello! Choose from {}".format(availableWorkers))
                response = self.wait_for_message()
                if response in availableWorkers:
                    worker = availableWorkers[response]
                    workerRef = self.ws_current_users.get(worker, None)[1]
                    logger.debug("ref: {}".format(workerRef))
            while worker:
                logger.debug("Using worker {}".format(worker))
                self.send_message("You chose {}. Now send command (return to choose another device, exit to exit)".format(worker))
                command = self.wait_for_message()
                if command == "exit":
                    self.close_connection("You said exit. Bye!")
                elif command == "return":
                    worker = False
                    break
                elif command == "block":
                    logger.info("try to block worker {}".format(worker))
                    workerRef._communicator.forceBlock(60)
                    logger.info("worker {} block released.".format(worker))
                    continue
                elif command == "stop":
                    logger.info("try to stop worker {}".format(worker))
                    self.send_message("Will try to stop worker - return to device selection")
                    workerRef.stop_worker()
                    workerRef._internal_cleanup()
                    worker = False
                    break
                result = self.ws_server.send_and_wait(worker, workerRef, command, 30)
                logger.debug("Command resulted in: {}".format(result))
                logger.debug("Command {} for device {} finished.".format(command, worker))

                try:
                    listResult = ast.literal_eval(result)
                except Exception:
                    listResult = result
                if isinstance(listResult, list):
                    builtMessage = ("Command {} on worker {} resulted in: \n".format(command, worker))
                    for line in listResult:
                        line = str(line)
                        line += "\n"
                        builtMessage += line
                    self.send_message(builtMessage)
                else:
                    if result[0] == "[":
                        result = result.replace(", ", "\n")
                        result = result.replace("[", "")
                        result = result.replace("]", "")
                    self.send_message("Command {} on worker {} resulted in: \n{}".format(command, worker, result)) or self.send_message("Invalid result. Please retry.")
        self.close_connection()
        return
