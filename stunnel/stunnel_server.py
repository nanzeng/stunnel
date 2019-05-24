import click
import asyncio
import zmq
import zmq.asyncio
import logging
import msgpack

from functools import partial
from collections import defaultdict

#from .protocol import HEARTBEAT, LOGON, LOGOUT, RELAY
HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'

class StunnelServer:
    def __init__(self, port, bufsize=4096):
        self.port = port
        self.bufsize = bufsize
    
        self.context = zmq.asyncio.Context()
        self.sessions = defaultdict(dict)

    async def run(self):
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(f'tcp://0.0.0.0:{self.port}')

        while True:
            msg = await self.socket.recv_multipart()
            print(msg)
            addr = msg[0]
            request = msg[2:]
            cmd = request[0]
            if addr not in self.sessions:
                port = int(addr.split(b':')[-1])
                asyncio.create_task(self.create_session(addr, port))
            if cmd == RELAY:
                asyncio.create_task(self.to_client(addr, *request[1:]))

    async def create_session(self, addr, port):
        try:
            server = await asyncio.start_server(
                partial(self.handle_connection, addr), '0.0.0.0', port
            )
        except Exception as e:
            logging.error(e)
            self.socket.send_multipart([addr, b'', EXCEPTION, msgpack.packb(e)])
        else:
            logging.info(f'Listening on {port}')
            async with server:
                await server.serve_forever()       

    async def handle_connection(self, addr, reader, writer):
        print(writer)
        client_addr = writer.get_extra_info('peername')
        client_addr = f'{client_addr}'.encode()
        self.sessions[addr][client_addr] = reader, writer
        logging.info(f'client connected from {client_addr}')
        asyncio.create_task(self.from_client(addr, client_addr, reader))

    async def from_client(self, addr, client_addr, reader):
        while not reader.at_eof():
            data = await reader.read(self.bufsize)
            print(data)
            if data:
                await self.socket.send_multipart([addr, b'', RELAY, client_addr, msgpack.packb(data)])
        print('client closed')
        del self.sessions[addr]
        print(f'{addr} writer clean up')

    async def to_client(self, addr, client_addr, data):
        _, writer = self.sessions[addr][client_addr]
        writer.write(msgpack.unpackb(data))
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
