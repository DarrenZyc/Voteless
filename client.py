import argparse


class Client:
    def __init__(self, id, addr, port):
        self.id = id
        self.addr = addr
        self.port = port
        print(f"Client initialized with id {self.id} at {self.addr}:{self.port}")


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
    if args.file:
        f = open(args.file, "r")
        for line in f.read().split("\n"):
            if int(line.split()[0]) == args.id:
                my_addr = line.split()[1]
                my_port = line.split()[2]

    if my_port != "" and my_addr != -1:
        Client(args.id, my_addr, my_port)


if __name__ == "__main__":
    main()
