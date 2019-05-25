import click
import asyncio
import zmq
import zmq.asyncio
import logging

from functools import partial
from collections import defaultdict

#from .protocol import HEARTBEAT, LOGON, LOGOUT, RELAY
HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'

logging.basicConfig(format='[%(asctime)s] %(levelname)s %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)


class StunnelServer:
    def __init__(self, port, bufsize=32768):
        self.port = port
        self.bufsize = bufsize
    
        self.context = zmq.asyncio.Context()
        self.sessions = defaultdict(dict)

    async def run(self):
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(f'tcp://0.0.0.0:{self.port}')

        while True:
            msg = await self.socket.recv_multipart()
            addr = msg[0]
            request = msg[2:]
            cmd = request[0]
            
            if addr not in self.sessions:
                asyncio.create_task(self.create_session(addr))

            if cmd == RELAY:
                asyncio.create_task(self.to_client(addr, *request[1:]))

    async def create_session(self, addr):
        peer, port = addr.decode().split(':')
        try:
            server = await asyncio.start_server(
                partial(self.handle_connection, addr), '0.0.0.0', port
            )
        except Exception as e:
            logging.error(e)
            self.socket.send_multipart([addr, b'', EXCEPTION, str(e).encode()])
        else:
            logging.info(f'{peer} Connected, Listening on {port}')
            async with server:
                await server.serve_forever()       

    async def handle_connection(self, addr, reader, writer):
        client_addr = writer.get_extra_info('peername')
        client_addr = f'{client_addr}'.encode()
        self.sessions[addr][client_addr] = reader, writer
        logging.info(f'Client connected from {client_addr}')
        asyncio.create_task(self.from_client(addr, client_addr, reader))

    async def from_client(self, addr, client_addr, reader):
        while True:
            data = await reader.read(self.bufsize)
            if data:
                await self.socket.send_multipart([addr, b'', RELAY, client_addr, data])
            else:
                logging.info(f'Client {client_addr} closed session')
                break
        del self.sessions[addr][client_addr]

    async def to_client(self, addr, client_addr, data):
        try:
            _, writer = self.sessions[addr][client_addr]
        except KeyError:
            # session closed, ignore
            pass
        else:
            writer.write(data)
            await writer.drain()


@click.command()
@click.option('-p', '--port', type=int)
def main(port):
    loop = asyncio.get_event_loop()
    server = StunnelServer(port)
    loop.create_task(server.run())
    loop.run_forever()


if __name__ == '__main__':
    main()
