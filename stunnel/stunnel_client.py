import click
import asyncio
import zmq
import zmq.asyncio
import logging
import msgpack

#from .protocol import *

HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'
class StunnelClient:
    def __init__(self, service_addr, service_port, server_addr, server_port, bind_port, bufsize=4096):
        self.service_addr = service_addr
        self.service_port = service_port
        self.server_addr = server_addr
        self.server_port = server_port
        self.bind_port = bind_port
        self.bufsize = bufsize

        self.context = zmq.asyncio.Context()
        self.sessions = {}

    async def run(self):
        socket = self.context.socket(zmq.DEALER)
        socket.connect(f'tcp://{self.server_addr}:{self.server_port}')

        #init
        await socket.send_multipart([b'', LOGON, msgpack.packb(self.bind_port)])

        while True:
            msg = await socket.recv_multipart()
            print(msg)
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
                asyncio.create_task(self.to_service(client_addr, msgpack.unpackb(respond[2])))

    async def from_service(self, addr, socket):
        reader, writer = self.sessions[addr]
        while not reader.at_eof():
            data = await reader.read(self.bufsize)
            print(data)
            if data:
                await socket.send_multipart([b'', RELAY, addr, msgpack.packb(data)])
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
