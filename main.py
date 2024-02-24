from typing import Any
import discord
from os import environ
import asyncio
from discord.flags import Intents
from discord import Embed
import parse_utilities
import requests

PUNISHMENTS = [".warn", ".ban"]

class Wagger(discord.Client):
    _channel_id: int = None
    _pun_channel_id: int = None
    _channel: discord.TextChannel = None
    _ban_channel: discord.TextChannel = None
    ready: bool = False

    def __init__(self, channel_id, pun_channel_id, intents: Intents, **options: Any) -> None:
        self._channel_id = channel_id
        self._pun_channel_id = pun_channel_id
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        self._channel = await self.fetch_channel(self._channel_id)
        self._ban_channel = await self.fetch_channel(self._pun_channel_id)
        print(f"Logged on as {self.user}, chatting in {self._channel.name} and {self._ban_channel.name}")
        self.ready = True

    async def send(self, content: str):
        await self._channel.send(content)

    async def send_to_punishments(self, embed:Embed, message:str):
        user_agent = "Sulla@GladiatorDuels"
        (type, playfabId, reason) = parse_utilities.get_punishment(message)
        info_api = environ["INFO_API"]
        url = f"{info_api}/{playfabId}"
        headers = {
            "User-Agent": user_agent
        }
        response = requests.get(url, headers=headers)
        json_response = response.json()
        embed.add_field(name="Culprit Name", value=json_response["name"])
        embed.add_field(name="Culprit Platform", value=json_response["platform"])
        embed.add_field(name="Reason", value=reason)
        await self._ban_channel.send("Punishment", embed=embed)
        return embed

    async def on_message(self, message: discord.message.Message):
        if message.content == "ping":
            await self.send("Pong")
        elif len(message.embeds) > 0 and str(message.channel.id) != self._pun_channel_id:
            print(f"received message {message}")
            embed = message.embeds[0]
            source_dict = embed.to_dict()
            new_embed = Embed.from_dict(source_dict)
            descrip = new_embed.description
            split = descrip.split("\n**")
            messageKey = [element for element in split if element.startswith("Message")]
            messageValue = messageKey[0]
            true_message = messageValue.replace("Message:** ", "")
            if any(true_message.startswith(pun) for pun in PUNISHMENTS):
                try:
                    await self.send_to_punishments(new_embed, true_message)
                except Exception as e:
                    print(f"Failed to send punishment log. {e}")



intents = discord.Intents.default()
intents.message_content = True
target_channel_id = environ["D_CHANNEL_ID"]
pun_channel_id = environ["D_PUN_CHANNEL_ID"]

client = Wagger(target_channel_id, pun_channel_id, intents=intents)

loop = asyncio.get_event_loop()
loop.run_until_complete(client.start(environ["D_TOKEN"]))

