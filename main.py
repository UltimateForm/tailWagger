from typing import Any
import discord
from os import environ
import asyncio
from discord.flags import Intents
from watcher import Watcher


class Wagger(discord.Client):
    _channel_id: int = None
    _channel: discord.TextChannel = None
    ready: bool = False

    def __init__(self, channel_id, intents: Intents, **options: Any) -> None:
        self._channel_id = channel_id
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        self._channel = await self.fetch_channel(self._channel_id)
        print(f"Logged on as {self.user}, chatting in {self._channel.name}")
        self.ready = True

    async def send(self, content: str):
        await self._channel.send(content)

    async def on_message(self, message: discord.message.Message):
        if message.content == "How are you?":
            await message.channel.send("I'm good, thank you!")


intents = discord.Intents.default()
intents.message_content = True
target_channel_id = environ["D_CHANNEL_ID"]
target_file_path = environ["TARGET_FILE_PATH"]
client = Wagger(target_channel_id, intents=intents)


async def monitor():
    print("Monitoring started")
    watch = Watcher("/home/monke/src/tailWagger/target.txt", 15)
    async for new_lines in watch:
        print(f"New lines: {new_lines}")
        if client.ready and new_lines is not None and len(new_lines) > 0:
            for line in new_lines.splitlines():
              await client.send(line)

loop = asyncio.get_event_loop()
# loop.run_until_complete(asyncio.wait((loop.create_task(monitor()),)))
loop.run_until_complete(asyncio.gather(
    monitor(),
    client.start(environ["D_TOKEN"])
))

