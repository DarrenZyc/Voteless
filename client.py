import argparse
import socket
import threading


class Client:
    def __init__(self, id, addr, port, addr_book):
        self.id = id
        self.addr = addr
        self.port = port
        self.peers = addr_book
        self.threads = list()
        print(f"Client initialized with id {self.id} at {self.addr}:{self.port}")
        t1 = threading.Thread(target=self.console)
        self.threads.append(t1)
        t1.start()

        t2 = threading.Thread(target=self.tcp_listener)
        t2.daemon = True
        self.threads.append(t2)
        t2.start()

    def console(self):
        while True:
            command = input("> ")
            if command == "":
                continue
            command = command.split()
            if command[0] == "vote":
                self.vote(command[1:])

    def vote(self, content):
        content = " ".join(content)
        print(f'Vote for "{content}"')
        self.sendToPeers(content)

    def sendToPeers(self, message):
       

        for peer in self.peers:
            if int(peer.split()[0]) != self.id:
                ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print(f"--connect to {peer.split()[1]} : {int(peer.split()[2])}")
                ss.connect((peer.split()[1], int(peer.split()[2])))
                content = f"[vote] {message}"
                ss.send(content.encode())
                ss.close()

    def tcp_listener(self):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.bind((self.addr, int(self.port)))
        ss.listen(1)

        while True:
            conn, addr = ss.accept()
            thread = threading.Thread(target=self.tcp_handler, args=(conn, addr))
            thread.start()

    def tcp_handler(self, ssocket, senderaddr):
        message = ssocket.recv(1024)
        if not message:
            return
        message_decode = message.decode()
        # message_split = message_decode.split()
        print(message_decode)
        ssocket.close()


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
        Client(args.id, my_addr, my_port, addr_book)


if __name__ == "__main__":
    main()

# python client.py -f address.txt -i 0
