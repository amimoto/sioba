from unittest import IsolatedAsyncioTestCase
import json
from sioba import (
    interface_from_uri,
    SocketInterface,
    SecureSocketInterface,
)
import asyncio
from utils.server import (
    create_server,
    CERT_DIR,
    SingleRequestServer,
    SSLSingleRequestServer,
)

class TestInterfaces(IsolatedAsyncioTestCase):

    servers: list[SingleRequestServer] = []

    def setUp(self):
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.shutdown()

    async def test_plaintext_socket_interface(self):
        # Start the test server
        server = create_server(SingleRequestServer)
        self.servers.append(server)

        # Now connect to the test server
        uri = f"tcp://localhost:{server.port}"
        sock = await interface_from_uri(uri).start()
        self.assertIsInstance(sock, SocketInterface)

        # Setup the interface for the control
        send_data = []
        def send_callback(interface, data):
            send_data.append(data)
        sock.on_send_to_frontend(send_callback)

        # Let's connect to the plaintext server
        await sock.start()
        await asyncio.sleep(0.1)

        # Send a simple request
        await sock.receive_from_frontend(b"HELLO\n")
        await asyncio.sleep(0.1)

        # Check if we received a response
        response = json.loads(send_data[1])
        self.assertEqual(response['data'], "HELLO")

        # Request the server to stop
        await sock.receive_from_frontend(b"quit\n")

        await sock.shutdown()
        server.shutdown()

    async def test_ssl_socket_interface(self):
        # Start the test server
        certfile = CERT_DIR / "future/certificate.crt"
        keyfile = CERT_DIR / "future/private.key"
        server = create_server(
            SSLSingleRequestServer,
            certfile=certfile.resolve(),
            keyfile=keyfile.resolve(),
        )
        self.servers.append(server)


        import ssl
        ssl_ctx = ssl._create_unverified_context()
        sslsock = await interface_from_uri(
                            f"ssl://localhost:{server.port}",
                            create_ssl_context=lambda _: ssl_ctx
                        ).start()
        self.assertIsInstance(sslsock, SecureSocketInterface)

        # Setup the interface for the control
        send_data = []
        def send_callback(interface, data):
            send_data.append(data)
        sslsock.on_send_to_frontend(send_callback)

        # Let's connect to the plaintext server
        await sslsock.start()
        await asyncio.sleep(0.1)

        # Send a simple request
        await sslsock.receive_from_frontend(b"HELLO\n")
        await asyncio.sleep(0.1)

        # Check if we received a response
        response = json.loads(send_data[1])
        self.assertEqual(response['data'], "HELLO")

        # Request the server to stop
        await sslsock.receive_from_frontend(b"quit\n")

        await sslsock.shutdown()
        server.shutdown()



