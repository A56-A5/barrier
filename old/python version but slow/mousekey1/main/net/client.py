# net/client.py
import socket
from net.network import NetworkConnection

class Client:
    def __init__(self, server_ip='127.0.0.1', port=5051):
        self.server_ip = server_ip
        self.port = port
        self.conn = None

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.server_ip, self.port))
        self.conn = NetworkConnection(sock)
        print(f"[Client] Connected to server at {self.server_ip}:{self.port}")

    def send(self, data: bytes):
        if self.conn:
            self.conn.send(data)

    def receive(self) -> bytes:
        if self.conn:
            return self.conn.receive()
        return b''

    def close(self):
        if self.conn:
            self.conn.close()

