from unittest import IsolatedAsyncioTestCase
import re
from sioba import (
    interface_from_uri,
    SocketInterface,
    SecureSocketInterface,
)
import asyncio

class TestInterfaces(IsolatedAsyncioTestCase):

    async def test_plaintext_socket_interface(self):
        sock = await interface_from_uri("tcp://host:80").start()
        self.assertIsInstance(sock, SocketInterface)

        # Setup the interface for the control
        send_data = []
        def send_callback(interface, data):
            send_data.append(data)
        sock.on_send_to_frontend(send_callback)

        # Let's connect to the plaintext HTTP server
        await sock.start()
        await asyncio.sleep(0.1)

        # Send a simple HTTP request
        await sock.receive_from_frontend(b"GET / HTTP/1.1\r\nHost: host\r\n\r\n")
        await asyncio.sleep(0.1)

        # Check if we received a response
        headers, body = send_data[1].split(b"\r\n\r\n", maxsplit=1)
        self.assertEqual(body, b"HELLO")
        self.assertIn("200 OK", headers.decode())

        await sock.shutdown()

    async def test_ssl_socket_interface(self):

        import ssl
        ssl_ctx = ssl._create_unverified_context()
        sslsock = await interface_from_uri(
                            "ssl://host:443",
                            create_ssl_context=lambda _: ssl_ctx
                        ).start()
        self.assertIsInstance(sslsock, SecureSocketInterface)

        # Setup the interface for the control
        send_data = []
        def send_callback(interface, data):
            send_data.append(data)
        sslsock.on_send_to_frontend(send_callback)

        # Let's connect to the plaintext HTTP server
        await sslsock.start()
        await asyncio.sleep(0.1)

        # Send a simple HTTP request
        await sslsock.receive_from_frontend(b"GET / HTTP/1.1\r\nHost: host\r\n\r\n")
        await asyncio.sleep(0.1)

        # Check if we received a response
        headers, body = send_data[1].split(b"\r\n\r\n", maxsplit=1)
        self.assertEqual(body, b"HELLO")
        self.assertIn("200 OK", headers.decode())
