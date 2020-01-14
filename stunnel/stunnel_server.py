import os
import sys
import click
import asyncio
import zmq
import zmq.asyncio
import logging

from functools import partial
from collections import defaultdict, ChainMap
from zmq.auth.asyncio import AsyncioAuthenticator

from .utils import load_config
from .utils import show_config as _show_config

HEARTBEAT = b'\x00'
LOGON = b'\x01'
LOGOUT = b'\x02'
EXCEPTION = b'\x03'
RELAY = b'\x04'

logging.basicConfig(format='[%(asctime)s] %(levelname)s %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)


class StunnelServer:
    def __init__(self, config):
        self.port = config['port']
        self.bufsize = config['bufsize']
        self.heartbeat_liveness = config['heartbeat']['liveness']
        self.heartbeat_interval = config['heartbeat']['interval']
        self.public_keys_dir = config['client_keys_dir']
        self.secret_key = config['secret_key']
        self.public_key = config['public_key']
    
        self.context = zmq.asyncio.Context()
        self.sessions = defaultdict(dict)
        self.liveness = defaultdict(lambda: self.heartbeat_liveness)

    async def heartbeat(self, addr, server):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            self.liveness[addr] -= 1
            if self.liveness[addr] <= 0:
                logging.error(f'Connection from {addr.decode()} timeout, close service')
                server.close()
                await server.wait_closed()
                del self.liveness[addr]
                break

    async def monitor_certificates(self, authenticator, dir):
        """monitor client certificates dir, reload if there is any change"""
        last = 0
        while True:
            try:
                mtime = os.path.getmtime(dir)
            except OSError as e:
                logging.error(f'Monitor certificates failed: {e}')
            else:
                if mtime > last:
                    if last == 0:
                        logging.info('Load client certificates')
                    else:
                        logging.info('Certificate keys dir updated, reload')
                    authenticator.configure_curve(domain='*', location=self.public_keys_dir)
                    last = mtime
            await asyncio.sleep(1)

    async def run(self):
        authenticator = AsyncioAuthenticator(self.context)
        authenticator.start()
        asyncio.create_task(self.monitor_certificates(authenticator, self.public_keys_dir))

        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.curve_secretkey = self.secret_key
        self.socket.curve_publickey = self.public_key
        self.socket.curve_server = True
        self.socket.bind(f'tcp://0.0.0.0:{self.port}')
        logging.info(f'Listening on tunnel port {self.port}')

        while True:
            msg = await self.socket.recv_multipart()
            addr = msg[0]
            request = msg[2:]
            cmd = request[0]
            
            if addr not in self.liveness:
                asyncio.create_task(self.create_session(addr))

            if cmd == RELAY:
                asyncio.create_task(self.to_client(addr, *request[1:]))

            self.liveness[addr] = self.heartbeat_liveness

        authenticator.stop()

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
            logging.info(f'Tunnel endpoint {peer} Connected, Listening on {port}')
            asyncio.create_task(self.heartbeat(addr, server))
            async with server:
                await server.serve_forever()       

    async def handle_connection(self, addr, reader, writer):
        client_addr = f'{writer.get_extra_info("peername")}'.encode()
        #client_addr = f'{client_addr}'.encode()
        self.sessions[addr][client_addr] = reader, writer
        logging.info(f'Client connected from {client_addr.decode()}')
        asyncio.create_task(self.from_client(addr, client_addr))

    async def from_client(self, addr, client_addr):
        reader, writer = self.sessions[addr][client_addr]
        while True:
            data = await reader.read(self.bufsize)
            if data:
                await self.socket.send_multipart([addr, b'', RELAY, client_addr, data])
            else:
                logging.info(f'Client {client_addr.decode()} closed session')
                break
        del self.sessions[addr][client_addr]
        writer.close()
        await writer.wait_closed()

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
@click.option('-c', '--config', default=os.path.join(os.path.expanduser('~'), '.config', 'stunnel', 'config.yaml'))
@click.option('-p', '--port', type=int)
@click.option('-s', '--show-config', is_flag=True)
def main(config, port, show_config):
    loop = asyncio.get_event_loop()

    role = 'server'

    if show_config:
        _show_config(role, config)

    config = load_config(role, config)
    if port:
        config['port'] = port

    if 'port' not in config:
        print('Error: Server listening port is not configured')
        sys.exit(1)

    server = StunnelServer(config)
    loop.create_task(server.run())
    loop.run_forever()


if __name__ == '__main__':
    main()
