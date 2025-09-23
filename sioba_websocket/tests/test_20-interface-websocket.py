from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    Interface,
)
import threading
import asyncio
import json

import websockets.sync.server

def setup_websocket_server(host:str = "localhost", port:int=4506):

    def echo(websocket):
        for message in websocket:
            json_data = json.dumps({
                "message": message.decode(),
            })
            print(f"--------------------------")
            import pprint
            pprint.pprint(json_data)
            print(f"--------------------------")
            websocket.send(json_data)

    server = websockets.sync.server.serve(echo, host, port)

    return server

class TestImportWebsocket(IsolatedAsyncioTestCase):

    async def test_websocket_invoke_minimal(self):

        server = setup_websocket_server()
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        websocket_uri = "ws://localhost:4506/"

        # Construct the websocket URI for the websocket interface
        websocket_interface = interface_from_uri(websocket_uri)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)
        websocket_interface.on_send_to_frontend(on_send_to_frontend)

        from sioba_websocket.interface import WebsocketInterface
        self.assertIsInstance(websocket_interface, WebsocketInterface)

        await websocket_interface.start()
        await asyncio.sleep(0.2)

        # Send some data along
        test_message = b"Hello, WebSocket!"
        await websocket_interface.receive_from_frontend(test_message)

        await asyncio.sleep(0.2)
        self.assertTrue(len(frontend_buffer) > 0)
        data = json.loads(frontend_buffer[0].decode())
        self.assertEqual(data["message"], test_message.decode())

