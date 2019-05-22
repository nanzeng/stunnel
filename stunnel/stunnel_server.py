import click
import asyncio
import zmq
import zmq.asyncio
import logging


class StunnelServer:
    def __init__(self, public_port, private_port, bufsize=1024):
        self.public_port = public_port
        self.private_port = private_port
        self.bufsize = bufsize
    
        self.context = zmq.asyncio.Context()
        self.sessions = {}

    async def run(self):
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.bind(f'tcp://0.0.0.0:{self.private_port}')

        server = await asyncio.start_server(
                self.handle_connection, '0.0.0.0', self.public_port)
        
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f'client connected from {addr}')

        addr = f'{addr[0]}:{addr[1]}'.encode()
        print(f'Sessions {self.sessions}')
        self.sessions[addr] = reader, writer

        asyncio.create_task(self.from_client(addr))
        asyncio.create_task(self.from_service(addr))

    async def from_client(self, addr):
        reader, writer = self.sessions[addr]
        while not reader.at_eof():
            data = await reader.read(self.bufsize)
            print(data)
            if data:
                await self.socket.send_multipart([b'', addr, data])
        print('client closed')
        del self.sessions[addr]
        #writer.close()
        #await writer.wait_closed()
        print(f'{addr} writer clean up')


    async def from_service(self, addr):
        _, writer = self.sessions[addr]
        print(f'Writer: {writer}')
        while True:
            _, _, data = await self.socket.recv_multipart()
            if data: 
                print(f'Data size is {len(data)}')
                writer.write(data)
                await writer.drain()
            #else:
                #writer.close()
                #await writer.wait_closed()
            #    break
        print('close service connection')


@click.command()
@click.option('--service-port', type=int)
@click.option('--tunnel-port', type=int)
def main(service_port, tunnel_port):
    loop = asyncio.get_event_loop()
    server = StunnelServer(service_port, tunnel_port)
    loop.create_task(server.run())
    loop.run_forever()


if __name__ == '__main__':
    main()
