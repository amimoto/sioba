import ssl
import socket
import json
from typing import Optional
from enum import Enum
from threading import Thread
import pathlib
import os
import random

# Get the current module directory
CERT_DIR: pathlib.Path = pathlib.Path(__file__).parent / 'certs'

class ServerStatus(Enum):
    INITIALIZED = 'initialized'
    STARTING = 'starting'
    RUNNING = 'running'
    STOPPED = 'stopped'

class SingleRequestServer():

    def __init__(
            self,
            port: int = 0,
            host: str = 'localhost',
        ):
        self.port: int = port
        self.host: str = host
        self.thread: Optional[Thread] = None
        self.state: ServerStatus = ServerStatus.INITIALIZED
        self.connection: Optional[socket.socket] = None

    def create_socket(self, host: str, port: int) -> socket.socket:
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.bind((host, port))
        return serversocket

    def connect(self, host: str, port: int) -> socket.socket:
        serversocket = self.create_socket(host, port)
        self.port = serversocket.getsockname()[1]
        return serversocket

    def _start(self, serversocket):
        self.state = ServerStatus.RUNNING
        serversocket.listen(1)
        try:
            connection, _ = serversocket.accept()
            self.connection = connection
            while True:
                buf = connection.recv(64)
                if len(buf) <= 0:
                    continue
                if isinstance(buf, bytes):
                    data = buf.decode('utf-8').strip()
                connection.sendall(
                    json.dumps({
                        'status': 'ok',
                        'data': data
                    }).encode('utf-8')
                )
                if buf.strip() == b'quit':
                    connection.close()
                    self.state = ServerStatus.STOPPED
                    break
        except ssl.SSLEOFError:
            print("SSL connection closed by client")

    def start(self):
        serversocket = self.connect(self.host, self.port)
        self.state = ServerStatus.STARTING
        self.thread = Thread(target=self._start, args=(serversocket,), daemon=True)
        self.thread.start()

    def shutdown(self):
        if self.connection:
            self.connection.close()
            if self.thread is not None:
                self.thread.join()
                self.thread = None
            self.state = ServerStatus.STOPPED

class SSLSingleRequestServer(SingleRequestServer):
    def __init__(
            self,
            certfile: str,
            keyfile: str,
            password: Optional[str] = None,
            **kwargs
        ):
        super().__init__(**kwargs)
        self.certfile: str = certfile
        self.keyfile: str = keyfile
        self.password: Optional[str] = password

    def connect(self, host: str, port: int) -> socket.socket:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            certfile=self.certfile,
            keyfile=self.keyfile,
            password=self.password,
        )

        serversocket = super().connect(host, port)
        sslserversocket = context.wrap_socket(serversocket, server_side=True)
        return sslserversocket

def create_server(cls, **kwargs):
    server = cls(**kwargs)
    server.start()
    return server