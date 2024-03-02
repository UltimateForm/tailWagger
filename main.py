from typing import Any
import discord
from os import environ
import asyncio
from discord.flags import Intents
from discord import Embed
import parse_utilities
import requests
from srcds.rcon import RconConnection
from typing import List

# todo: split this into files
# todo: use dataclasses for config
# todo: automate channel registry

# note: revisit parse_utilities if punishments changed
PUNISHMENTS = [".warn", ".ban"]
CMD_EXECUTOR = ".run "


class Wagger(discord.Client):
    # todo: fix these types or parse channels ids from env, right now are being set to string despite type annotation
    _channel_id: int = None
    _warn_channel_id: int = None
    _ban_channel_id: int = None
    _console_channel_id: int = None
    _server_status_channel_id: int = None
    _channel: discord.TextChannel = None
    _warn_channel: discord.TextChannel = None
    _ban_channel: discord.TextChannel = None
    _console_channel: discord.TextChannel = None
    _server_status_channel: discord.TextChannel = None
    _rcon_connection: RconConnection = None
    _rcon_ready: bool = False
    _rcon_cmd_blacklist: List[str] = []
    _server_status_job = None
    ready: bool = False

    def __init__(
        self,
        channel_id,
        warn_channel_id,
        ban_channel_id,
        console_channel_id,
        server_status_channel_id,
        intents: Intents,
        rcon_pass: str | None = None,
        rcon_addr: str | None = None,
        rcon_port: int | None = None,
        rcon_cmd_blacklist: list[str] = [],
        **options: Any,
    ) -> None:
        self._channel_id = channel_id
        self._warn_channel_id = warn_channel_id
        self._ban_channel_id = ban_channel_id
        self._console_channel_id = console_channel_id
        self._server_status_channel_id = server_status_channel_id
        if rcon_pass and rcon_addr and rcon_port:
            self._rcon_cmd_blacklist = rcon_cmd_blacklist
            self._rcon_connection = RconConnection(
                rcon_addr, rcon_port, rcon_pass, single_packet_mode=True
            )
            self._server_status_job = asyncio.get_event_loop().create_task(
                self.server_status_watch()
            )
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        self._channel = await self.fetch_channel(self._channel_id)
        self._warn_channel = await self.fetch_channel(self._warn_channel_id)
        self._ban_channel = await self.fetch_channel(self._ban_channel_id)
        self._console_channel = await self.fetch_channel(self._console_channel_id)
        self._server_status_channel = await self.fetch_channel(
            self._server_status_channel_id
        )
        print(
            f"Logged on as {self.user}"
        )
        self.ready = True

    async def send(self, content: str):
        await self._channel.send()
        await self._channel.send(content)

    def exec_command(self, cmd: str) -> str:
        if any([cmd.startswith(black) for black in self._rcon_cmd_blacklist]):
            return "Forbidden"
        response: bytes = self._rcon_connection.exec_command(cmd)
        # response_parsed = response.replace("b'", "").replace("\n\x00\x00", "")
        response_parsed = response.decode("utf-8").replace("\x00\x00", "")
        return response_parsed

    async def server_status_watch(self, interval_secs: int = 30):
        while True:
            if self._console_channel == None:
                await asyncio.sleep(interval_secs)
            try:
                embed = Embed(description="Server Status")
                server_status = self.exec_command("info")
                server_status_per_line = [
                    line for line in server_status.split("\n") if line
                ]
                # why? version has a ":" inside of its value that muddles things
                server_status_kv = [
                    kv.split(": ")
                    for kv in server_status_per_line
                    if not kv or not kv.startswith("Version")
                ]
                server_status_dict = dict(server_status_kv)
                embed.title = server_status_dict["ServerName"]
                embed.add_field(name="Status", value=":green_circle:")
                embed.add_field(name="Gamemode", value=server_status_dict["GameMode"])
                embed.add_field(name="Current Map", value=server_status_dict["Map"])
                playerlist = self.exec_command("playerlist")
                code_block_playerlist = f"```{playerlist}```"
                playercount = playerlist.count("\n")
                embed.add_field(
                    name=f"Player list ({playercount})",
                    value=code_block_playerlist,
                    inline=False,
                )
                await self._server_status_channel.send(
                    embed=embed, delete_after=interval_secs, silent=True
                )
            except Exception as e:
                print(f"Failed to get server info: {str(e)}")
                await self._server_status_channel.send(
                    ":exclamation::exclamation::exclamation: ERROR WHILE RETRIEVING SERVER STATUS :exclamation::exclamation::exclamation:",
                    delete_after=interval_secs,
                )
            await asyncio.sleep(interval_secs)

    async def exec_discord_command(self, message: discord.message.Message):
        message_raw = message.content
        message_cmd = message_raw.replace(CMD_EXECUTOR, "")
        response = self.exec_command(message_cmd)
        code_block_response = f"```{response}```"
        if len(response) > 1000:
            await message.reply(code_block_response)
            return
        embed = Embed(title="CMD")
        embed.add_field(name="Input", value=message_cmd, inline=False)
        embed.add_field(name="Output", value=code_block_response, inline=False)
        await message.reply(embed=embed)

    async def send_punishment(self, embed: Embed, message: str):
        user_agent = environ["USER_AGENT"]
        punishment: parse_utilities.Punishment = parse_utilities.get_punishment(message)
        info_api = environ["INFO_API"]
        url = f"{info_api}/{punishment.playfab_id}"
        headers = {"User-Agent": user_agent}
        response = requests.get(url, headers=headers)
        json_response = response.json()
        embed.title = "Punishment"
        embed.color = discord.colour.Colour.from_str("#8b0000")
        embed.add_field(name="Culprit Name", value=json_response["name"])
        embed.add_field(name="Culprit Platform", value=json_response["platform"])
        embed.add_field(name="Reason", value=punishment.reason)
        embed.add_field(name="Duration", value=punishment.duration)
        embed.set_image(url=json_response["avatarUrl"])
        if punishment.type == ".ban":
            await self._ban_channel.send(embed=embed)
        else:
            await self._warn_channel.send(embed=embed)
        return embed

    async def on_message(self, message: discord.message.Message):
        if message.content == "ping":
            await message.channel.send("pong")
        elif str(
            message.channel.id
        ) == self._console_channel_id and message.content.startswith(CMD_EXECUTOR):
            await self.exec_discord_command(message)
        elif len(message.embeds) > 0 and str(message.channel.id) == self._channel_id:
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
                    await self.send_punishment(new_embed, true_message)
                except Exception as e:
                    print(f"Failed to send punishment log. {e}")


# this is untenable, create some sort of configuration collector
intents = discord.Intents.default()
intents.message_content = True
target_channel_id = environ["D_CHANNEL_ID"]
warn_channel_id = environ["D_PUN_CHANNEL_ID"]
ban_channel_id = environ["D_BAN_CHANNEL_ID"]
console_channel_id = environ["D_CONSOLE_CHANNEL_ID"]
server_status_channel_id = environ["D_SERVER_STATUS_ID"]
rcon_addr = environ["RCON_ADDRESS"]
rcon_pass = environ["RCON_PASSWORD"]
rcon_port_unparsed = environ["RCON_PORT"]
cmd_blacklist_unparsed = environ["RCON_CMD_BLACKLIST"]
cmd_blacklist = cmd_blacklist_unparsed.split(",")
rcon_port = int(rcon_port_unparsed)
client = Wagger(
    target_channel_id,
    warn_channel_id,
    ban_channel_id,
    console_channel_id,
    server_status_channel_id,
    intents=intents,
    rcon_addr=rcon_addr,
    rcon_port=rcon_port,
    rcon_pass=rcon_pass,
    rcon_cmd_blacklist=cmd_blacklist,
)
loop = asyncio.get_event_loop()
loop.run_until_complete(client.start(environ["D_TOKEN"]))
