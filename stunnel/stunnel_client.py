import os
import click
import asyncio
import zmq
import zmq.asyncio
import logging
import socket

from .utils import load_config
from .utils import show_config as _show_config

HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'

logging.basicConfig(format='[%(asctime)s] %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)


class StunnelClient:
    def __init__(self, config, server, service):
        self.server = server
        self.service = service

        self.bufsize = config['bufsize']
        self.heartbeat_interval = config['heartbeat']['interval']
        self.secret_key = config['secret_key']
        self.public_key = config['public_key']
        self.server_key = server['public_key']

        self.context = zmq.asyncio.Context()
        self.sessions = {}

    def identity(self):
        return f'{socket.gethostname()}:{self.service["bind_port"]}'.encode()

    async def heartbeat(self, socket):
        while True:
            await socket.send_multipart([b'', HEARTBEAT])
            await asyncio.sleep(self.heartbeat_interval)

    async def run(self):
        socket = self.context.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY, self.identity())
        socket.curve_secretkey = self.secret_key
        socket.curve_publickey = self.public_key
        socket.curve_serverkey = self.server_key
        socket.connect(f'tcp://{self.server["addr"]}:{self.server["port"]}')

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
                            host=self.service["addr"],
                            port=self.service["port"]
                        )
                    except Exception as e:
                        logging.error(f"Can't connect to server: {e}")
                        continue
                    else:
                        logging.info(f'connected to {writer.get_extra_info("peername")}')
                        self.sessions[client_addr] = reader, writer
                        asyncio.create_task(self.from_service(client_addr, socket))
                asyncio.create_task(self.to_service(client_addr, respond[2]))
            elif cmd == EXCEPTION:
                logging.error(respond[1].decode())

    async def from_service(self, addr, socket):
        reader, writer = self.sessions[addr]
        while True:
            data = await reader.read(self.bufsize)
            if data:
                await socket.send_multipart([b'', RELAY, addr, data])
            else:
                logging.info('EOF received from service, Exit')
                break
        del self.sessions[addr]
        writer.close()
        await writer.wait_closed()

    async def to_service(self, addr, data):
        try:
            _, writer = self.sessions[addr]
        except KeyError:
            # session closed, ignore
            pass
        else:
            writer.write(data)
            await writer.drain()


@click.command()
@click.option('-c', '--config', default=os.path.join(os.path.expanduser('~'), '.config', 'stunnel', 'config.yaml'))
@click.option('-s', '--show-config', is_flag=True)
def main(config, show_config):
    loop = asyncio.get_event_loop()

    role = 'client'

    if show_config:
        _show_config(role, config)

    config = load_config(role, config)
    for server in config['servers']:
        for service in config['services']:
            client = StunnelClient(config, server, service)
            loop.create_task(client.run())

    loop.run_forever()


if __name__ == '__main__':
    main()
