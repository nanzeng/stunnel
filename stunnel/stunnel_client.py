import click
import asyncio
import zmq
import zmq.asyncio
import logging 


class StunnelClient:
    def __init__(self, service_addr, service_port, server_addr, server_port, bufsize=4096):
        self.service_addr = service_addr
        self.service_port = service_port
        self.server_addr = server_addr
        self.server_port = server_port
        self.bufsize = bufsize

        self.context = zmq.asyncio.Context()
        self.sessions = {}

    async def run(self):
        socket = self.context.socket(zmq.ROUTER)
        socket.connect(f'tcp://{self.server_addr}:{self.server_port}')

        while True:
            identity, _, addr, data = await socket.recv_multipart()
            print(identity, addr, data)
            if addr not in self.sessions:
                reader, writer = await asyncio.open_connection(
                        host=self.service_addr,
                        port=self.service_port
                )
                print('connected to {writer.get_extra_info("peername")}')
                self.sessions[addr] = reader, writer
                asyncio.create_task(self.from_service(identity, addr, socket))
            asyncio.create_task(self.to_service(addr, data))

    async def from_service(self, identity, addr, socket):
        reader, writer = self.sessions[addr]
        while not reader.at_eof():
            data = await reader.read(self.bufsize)
            print(data)
            if data:
                await socket.send_multipart([identity, b'', addr, data])
        print('EOF received from service, Exit')
        del self.sessions[addr]
        writer.close()
        await writer.wait_closed()

    async def to_service(self, addr, data):
        _, writer = self.sessions[addr]
        writer.write(data)
        await writer.drain()


@click.command()
@click.option('--laddr', default='127.0.0.1')
@click.option('--lport', type=int)
@click.option('--raddr')
@click.option('--rport', type=int)
def main(laddr, lport, raddr, rport):
    loop = asyncio.get_event_loop()
    client = StunnelClient(laddr, lport, raddr, rport)

    loop.create_task(client.run())
    loop.run_forever()


if __name__ == '__main__':
    main()
