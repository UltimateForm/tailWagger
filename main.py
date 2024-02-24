from typing import Any
import discord
from os import environ
import asyncio
from discord.flags import Intents
from watcher import Watcher
from discord import Embed
import re
import parse_utilities
import requests

playfabIdRegex = r"\(([^)]*)\)[^(]*$"

class Wagger(discord.Client):
    _channel_id: int = None
    _channel: discord.TextChannel = None
    _ban_channel: discord.TextChannel = None
    ready: bool = False

    def __init__(self, channel_id, intents: Intents, **options: Any) -> None:
        self._channel_id = channel_id
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        self._channel = await self.fetch_channel(self._channel_id)
        self._ban_channel = await self.fetch_channel(1210988905734611064)
        print(f"Logged on as {self.user}, chatting in {self._channel.name} and {self._ban_channel.name}")
        self.ready = True

    async def send(self, content: str):
        await self._channel.send(content)

    async def on_message(self, message: discord.message.Message):
        if message.content == "ping":
            await self.send("Pong")
        if len(message.embeds) > 0 and  message.channel.id != 1210988905734611064:
            print("messa rec")
            embed = message.embeds[0]
            source_dict = embed.to_dict()
            new_embed = Embed.from_dict(source_dict)
            descrip = new_embed.description
            split = descrip.split("\n**")
            messageKey = [element for element in split if element.startswith("Message")]
            messageValue = messageKey[0]
            true_message = messageValue.replace("Message:** ", "")
            #".warn 3A2C9BEC839DD28C FFA 2999"
            user_agent = "Sulla@GladiatorDuels"
            (type, playfabId, reason) = parse_utilities.get_punishment(true_message)
            url = f"https://api.mordhau-scribe.com:8443/api/players/{playfabId}"
            headers = {
                "User-Agent": user_agent
            }
            response = requests.get(url)
            json_response = response.json()
            new_embed.add_field(name="Culprit Name", value=json_response["name"])
            new_embed.add_field(name="Culprit Platform", value=json_response["platform"])
            new_embed.add_field(name="Reason", value=reason)

            await self._ban_channel.send("Ban", embed=new_embed)
        # await self.send(embed=embed)



intents = discord.Intents.default()
intents.message_content = True
target_channel_id = environ["D_CHANNEL_ID"]
# target_file_path = environ["TARGET_FILE_PATH"]
client = Wagger(target_channel_id, intents=intents)

#1210988905734611064
async def monitor():
    print("Monitoring started")
    await asyncio.sleep(10)
    await client.send("Hello world")
    # watch = Watcher("/home/monke/src/tailWagger/target.txt", 15)
    # async for new_lines in watch:
    #     print(f"New lines: {new_lines}")
    #     if client.ready and new_lines is not None and len(new_lines) > 0:
    #         for line in new_lines.splitlines():
    #           await client.send(line)

loop = asyncio.get_event_loop()
# loop.run_until_complete(asyncio.wait((loop.create_task(monitor()),)))
loop.run_until_complete(asyncio.gather(
    monitor(),
    client.start(environ["D_TOKEN"])
))

