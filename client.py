import argparse
from pprint import pprint
import socket
import threading
import tkinter.messagebox
from tkinter import *
from tkinter import scrolledtext
import hashlib
import datetime
import json
import time
import random
import sys

GUI_RUNNING = False
LOG = None
DECISIONS = None
KEY_TYPE = "type"
KEY_PAYLOAD = "payload"
KEY_HASH = "hash"
KEY_ADDRESS = "address"
KEY_PORT = "port"
TYPE_VOTE = "vote"
TYPE_RESPONSE = "response"
TYPE_FINALIZED = "finalized"
TYPE_AWARDS = "awards"
VOTE_YES = "y"
VOTE_NO = "N"
RES_DRAW = "D"


def myprint(message):
    if GUI_RUNNING and LOG != None:
        LOG.insert(INSERT, "\n" + message)
    print(message)


class Client:
    def __init__(self, id, addr, port, addr_book, mode):
        self.mode = mode
        self.id = id
        self.addr = addr
        self.port = port
        self.peers = addr_book
        self.threads = list()
        self.balance = 100
        self.vote_decisions = []
        self.my_final_decision = None
        self.final_decisions = []
        self.initial_sender = None
        self.gui_response = None
        myprint(
            f"[Info] Client initialized with id {self.id} at {self.addr}:{self.port}"
        )

        t1 = threading.Thread(target=self.console)
        self.threads.append(t1)
        t1.start()

        t2 = threading.Thread(target=self.tcp_listener)
        t2.daemon = True
        self.threads.append(t2)
        t2.start()

        t3 = threading.Thread(target=self.gui)
        t3.daemon = True
        self.threads.append(t3)
        t3.start()

    def console(self):
        while True:
            command = input("> ")
            if command == "":
                continue
            command = command.split()
            if command[0] == "quit":
                sys.exit(0)
            elif command[0] == "vote":
                self.vote(" ".join(command[1:]))
            elif command[0] == "hash":
                print(self.time_hash(" ".join(command[1:])))
            elif command[0] == "status":
                print("==================")
                print(self.vote_decisions)
                print(self.my_final_decision)
                print(self.final_decisions)
                print(self.initial_sender)
            else:
                print(f"Unknown command: {command}")

    def gui(self):
        global GUI_RUNNING, LOG, DECISIONS
        window = Tk()
        window.title(f"id: {self.id} at {self.addr}:{self.port}")
        window.geometry("450x350")

        self.voteEntry = Entry(window, width=50)
        self.voteEntry.grid(row=0, column=0)
        btn = Button(window, text="Vote", command=self.gui_vote)
        btn.grid(row=0, column=1)
        self.label0 = Label(window, text="<Content>", width=30)
        self.label0.grid(row=1, column=0)
        btnY = Button(window, text="Y", command=self.gui_Y)
        btnY.grid(row=2, column=0)
        btnN = Button(window, text="N", command=self.gui_N)
        btnN.grid(row=2, column=1)

        label1 = Label(window, text="Log:")
        label1.grid(row=3, column=0)
        LOG = scrolledtext.ScrolledText(window, width=45, height=5)
        LOG.grid(row=4, column=0, columnspan=3, pady=5, padx=5)
        label2 = Label(window, text="Results:")
        label2.grid(row=5, column=0)
        DECISIONS = scrolledtext.ScrolledText(window, width=45, height=6)
        DECISIONS.grid(row=6, column=0, columnspan=3, pady=5, padx=5)

        GUI_RUNNING = True
        window.mainloop()

    def gui_vote(self):
        self.gui_response = None
        self.vote(self.voteEntry.get())

    def gui_Y(self):
        self.gui_response = "y"

    def gui_N(self):
        self.gui_response = "N"

    def vote(self, message):
        content = {}
        content[KEY_TYPE] = TYPE_VOTE
        content[KEY_PAYLOAD] = message
        content[KEY_HASH] = self.time_hash()
        content[KEY_ADDRESS] = self.addr
        content[KEY_PORT] = self.port
        self.initial_sender = None
        myprint(f"[Info] Vote: " + message)
        self.sendToPeers(json.dumps(content))

    def sendToPeers(self, message):
        for peer in self.peers:
            if int(peer.split()[0]) != self.id:
                try:
                    ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ss.connect((peer.split()[1], int(peer.split()[2])))
                    # print(f"--connected to {peer.split()[1]} : {int(peer.split()[2])}")
                    ss.send(message.encode())
                    ss.close()
                except ConnectionRefusedError:
                    myprint(f"[Info] Abort with peer {int(peer.split()[2])}")

    def gui_wait_for_response(self):
        if self.mode:
            dec = random.choice(["y", "N"])
            print("DECISON: ", dec)
            return dec
        while self.gui_response is None:
            time.sleep(0.5)
        return self.gui_response

    def tcp_listener(self):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.bind((self.addr, int(self.port)))
        ss.listen(1)

        while True:
            conn, addr = ss.accept()
            thread = threading.Thread(target=self.tcp_handler, args=(conn, addr))
            thread.start()

    def helper_check_for_generate_result(self, hash):
        # generate result
        # TODO: check each peer before sending
        global DECISIONS
        content = {}
        content[KEY_TYPE] = TYPE_FINALIZED
        my_decision = self.generate_result()
        # self.vote_decisions.append(my_decision)
        self.final_decisions.append(my_decision)
        DECISIONS.insert(INSERT, "\n" + json.dumps({"hash": hash[0:5], "decision": my_decision}))
        # print(f"-- my decision is {my_decision}, send back to org voter")
        content[KEY_PAYLOAD] = my_decision
        content[KEY_HASH] = hash

        try:
            ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ss.connect((self.initial_sender[0], self.initial_sender[1]))
            ss.send(json.dumps(content).encode())
            message = ss.recv(1024).decode()
            # print("[DEBUG] " + message)
            message = json.loads(message)

            if message[KEY_TYPE] == TYPE_AWARDS:
                myprint(f"[Info] Completed")
                self.balance += int(message[KEY_PAYLOAD])
            ss.close()
        except json.JSONDecodeError:
            print(f"[DECODE] {message}")
        except ConnectionRefusedError:
            print(
                f"-- original sender not available {(self.initial_sender[0], self.initial_sender[1])}"
            )

    def tcp_handler(self, ssocket, sender_addr):
        global GUI_RUNNING
        message = ssocket.recv(1024)
        if not message:
            return
        message = message.decode()
        message = json.loads(message)
        if message[KEY_TYPE] == TYPE_VOTE:
            # print("-- vote")
            self.initial_sender = (message[KEY_ADDRESS], int(message[KEY_PORT]))
            # make my decision here
            if self.label0 != None and GUI_RUNNING:
                self.label0.config(text=message[KEY_PAYLOAD])
                response = self.gui_wait_for_response()
            else:
                response = input(
                    f'For question "{message[KEY_PAYLOAD]}" my answer is: (y/N) > '
                )
            content = {}
            content[KEY_TYPE] = TYPE_RESPONSE
            my_decision = VOTE_YES if response == VOTE_YES else VOTE_NO
            content[KEY_PAYLOAD] = my_decision
            # keep track of decisions
            self.vote_decisions.append(my_decision)
            #     {"hash": message[KEY_HASH], "decision": my_decision}
            # )
            # DECISIONS.insert(INSERT, "\n" + json.dumps({"hash": message[KEY_HASH][0:5], "decision": my_decision}))
            content[KEY_HASH] = message[KEY_HASH]
            # boardcast to others
            # print("VOTE RESPD CONTENT: " + json.dumps(content))
            self.sendToPeers(json.dumps(content))

            if (
                len(self.vote_decisions) == len(self.peers) - 1
                and self.initial_sender != None
            ):
                self.helper_check_for_generate_result(message[KEY_HASH])

        elif message[KEY_TYPE] == TYPE_RESPONSE:
            # print("-- resp")
            # print(f"I reced resp: {message}")
            self.vote_decisions.append(message[KEY_PAYLOAD])

            if len(self.vote_decisions) == len(self.peers) - 1:
                if self.initial_sender == None:
                    self.my_final_decision = self.generate_result()
                    print(f"+ Final decision is {self.my_final_decision}")
                    self.final_decisions.append(self.my_final_decision)
                    DECISIONS.insert(INSERT, "\n" + json.dumps({"hash": message[KEY_HASH][0:5], "decision": self.my_final_decision}))
                else:
                    self.helper_check_for_generate_result(message[KEY_HASH])

        elif message[KEY_TYPE] == TYPE_FINALIZED:
            if self.my_final_decision == message[KEY_PAYLOAD]:
                # TODO: check each peer before sending
                content = {}
                content[KEY_TYPE] = TYPE_AWARDS
                # store to my result book
                payload = "10"
                content[KEY_PAYLOAD] = payload
                content[KEY_HASH] = self.hash(message[KEY_HASH], payload)
                # self.sendToPeers(json.dumps(content))
                # print("-- SEND REWD ", payload)
                ssocket.send((json.dumps(content)).encode())
                myprint(f"[Info] Completed with this peer")

        ssocket.close()

    def generate_result(self):
        count_yes = self.vote_decisions.count(VOTE_YES)
        count_no = len(self.vote_decisions) - count_yes
        self.vote_decisions = []
        res = ""
        if count_yes == count_no:
            res = RES_DRAW
        else:
            res = VOTE_YES if count_yes > count_no else VOTE_NO
        # print(f"I've got result! the result is {res}")
        return res

    # Generate a hash of current time stamp
    def time_hash(self, payload=""):
        payload = payload.strip()
        time = datetime.datetime.now()
        time = str(time)
        hash = hashlib.sha256()
        hash.update(bytes(time, "utf-8"))
        if payload != "":
            hash.update(bytes(payload, "utf-8"))
        # print(f"[info] from time {time} and {payload} to {hash.hexdigest()}")
        return hash.hexdigest()

    def hash(self, prev_hash, payload=""):
        if type(payload) == "string":
            payload = payload.strip()
        hash = hashlib.sha256()
        hash.update(bytes(prev_hash, "utf-8"))
        if payload != "":
            hash.update(bytes(payload, "utf-8"))
        # generate
        # print("=========== generate hash ==========")
        # print(prev_hash)
        # print(payload)
        # print(hash.hexdigest())
        # print("=========== end generate hash ==========")
        # print(f"[info] from hash {prev_hash} and {payload} to {hash.hexdigest()}")
        return hash.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id", type=int, help="client id")
    parser.add_argument("-f", "--file", help="address book file name")
    parser.add_argument("-a", "--auto", help="auto mode", action="store_true")

    args = parser.parse_args()
    if args.id is None:
        print("You must specify a client id")
        return
    my_addr = ""
    my_port = -1
    addr_book = None
    if args.file:
        f = open(args.file, "r")
        addr_book = f.read().split("\n")
        for line in addr_book:
            if int(line.split()[0]) == args.id:
                my_addr = line.split()[1]
                my_port = line.split()[2]

    if my_port != "" and my_addr != -1:
        Client(args.id, my_addr, my_port, addr_book, args.auto)


if __name__ == "__main__":
    main()

# python client.py -f address.txt -i 0
