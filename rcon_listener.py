import asyncio
import struct
from reactivex import Subject, operators
import os

# Packet types
SERVERDATA_AUTH = 3
SERVERDATA_EXECCOMMAND = 2


# src: https://github.com/pmrowla/pysrcds/blob/master/srcds/rcon.py
class RconPacket(object):
    """RCON packet"""

    def __init__(self, pkt_id=0, pkt_type=-1, body=""):
        self.pkt_id = pkt_id
        self.pkt_type = pkt_type
        self.body = body

    def __str__(self):
        """Return the body string."""
        return self.body

    def size(self):
        """Return the pkt_size field for this packet."""
        return len(self.body) + 10

    def pack(self):
        """Return the packed version of the packet."""
        return struct.pack(
            "<3i{0}s".format(len(self.body) + 2),
            self.size(),
            self.pkt_id,
            self.pkt_type,
            bytearray(self.body, "utf-8"),
        )


# src: https://github.com/pmrowla/pysrcds/blob/master/srcds/rcon.py
def get_login_packet(pwd: str):
    serverdata_auth = 3
    b = bytes(1)
    b += bytes(serverdata_auth)
    b += pwd.encode()
    return b


class RconListener(Subject[str]):
    _event: str
    _port: int
    _password: str
    _address: str
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _listening: bool

    def __init__(self, event: str = "chat", listening: bool = False) -> None:
        self._event = event
        self._port = int(os.environ["RCON_PORT"])
        self._password = os.environ["RCON_PASSWORD"]
        self._address = os.environ["RCON_ADDRESS"]
        self._listening = listening
        super().__init__()

    async def recv_pkt(self) -> RconPacket:
        """Read one RCON packet"""
        while True:

            header = await self._reader.read(struct.calcsize("<3i"))
            header_length = len(header)
            if header_length != 0:
                break
            else:
                await asyncio.sleep(1)

        (pkt_size, pkt_id, pkt_type) = struct.unpack("<3i", header)
        body_bytes = await self._reader.read(pkt_size - 8)
        body = body_bytes.decode()
        return RconPacket(pkt_id, pkt_type, body)

    async def warmer(self):
        while True:
            await asyncio.sleep(100)
            print("Rewarming...")
            self._writer.write(RconPacket(1, SERVERDATA_EXECCOMMAND, "alive").pack())
            await self._writer.drain()

    async def run(self):
        reader, writer = await asyncio.open_connection(self._address, self._port)
        self._reader = reader
        self._writer = writer
        writer.write(RconPacket(1, SERVERDATA_AUTH, self._password).pack())
        await writer.drain()
        auth_response = await self.recv_pkt()
        if auth_response.pkt_id != 1:
            raise ValueError("AUTHENTICATION FAILURE")
        if not self._listening:
            writer.write(
                RconPacket(32, SERVERDATA_EXECCOMMAND, f"listen {self._event}").pack()
            )
            self._listening = True
        await writer.drain()
        asyncio.create_task(self.warmer())
        while True:
            pck = await self.recv_pkt()
            self.on_next(pck.body)


if __name__ == "__main__":
    login_listener = RconListener(event="login", listening=False)
    login_listener.pipe(operators.filter(lambda x: x.startswith("Login:"))).subscribe(
        on_next=lambda x: print(f"LOGIN: {x}")
    )

    chat_listener = RconListener(event="chat", listening=True)
    chat_listener.pipe(operators.filter(lambda x: x.startswith("Chat:"))).subscribe(
        on_next=lambda x: print(f"CHAT: {x}")
    )

    async def main():
        await asyncio.gather(chat_listener.run(), login_listener.run())

    asyncio.run(main())
