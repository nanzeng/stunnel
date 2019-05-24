import click
import asyncio
import zmq
import zmq.asyncio
import logging
import socket

#from .protocol import *

HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'

logging.basicConfig(format='[%(asctime)s] %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)


class StunnelClient:
    def __init__(self, service_addr, service_port, server_addr, server_port, bind_port, bufsize=32768):
        self.service_addr = service_addr
        self.service_port = service_port
        self.server_addr = server_addr
        self.server_port = server_port
        self.bind_port = bind_port
        self.bufsize = bufsize

        self.context = zmq.asyncio.Context()
        self.sessions = {}

    def identity(self):
        return f'{socket.gethostname()}:{self.bind_port}'.encode()

    async def heartbeat(self, socket):
        while True:
            await socket.send_multipart([b'', HEARTBEAT])
            await asyncio.sleep(10)

    async def run(self):
        socket = self.context.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY, self.identity())
        socket.connect(f'tcp://{self.server_addr}:{self.server_port}')

        asyncio.create_task(self.heartbeat(socket))

        while True:
            msg = await socket.recv_multipart()
            respond = msg[1:]
            cmd = respond[0]
            if cmd == RELAY:
                client_addr = respond[1]
                if client_addr not in self.sessions:
                    try:
                        reader, writer = await asyncio.open_connection(
                            host=self.service_addr,
                            port=self.service_port
                        )
                    except Exception as e:
                        logging.error(f"Can't connect to server: {e}")
                        continue
                    else:
                        logging.info('connected to {writer.get_extra_info("peername")}')
                        self.sessions[client_addr] = reader, writer
                        asyncio.create_task(self.from_service(client_addr, socket))
                asyncio.create_task(self.to_service(client_addr, respond[2]))
            elif cmd == EXCEPTION:
                logging.error(respond[1].decode())

    async def from_service(self, addr, socket):
        reader, writer = self.sessions[addr]
        while not reader.at_eof():
            data = await reader.read(self.bufsize)
            if data:
                await socket.send_multipart([b'', RELAY, addr, data])
        print('EOF received from service, Exit')
        del self.sessions[addr]
        writer.close()
        await writer.wait_closed()

    async def to_service(self, addr, data):
        _, writer = self.sessions[addr]
        writer.write(data)
        await writer.drain()


@click.command()
@click.option('--service-addr', default='127.0.0.1')
@click.option('--service-port', type=int)
@click.option('--peer-addr')
@click.option('--peer-port', type=int)
@click.option('--bind-port', type=int)
def main(service_addr, service_port, peer_addr, peer_port, bind_port):
    loop = asyncio.get_event_loop()
    client = StunnelClient(service_addr, service_port, peer_addr, peer_port, bind_port)

    loop.create_task(client.run())
    loop.run_forever()


if __name__ == '__main__':
    main()
