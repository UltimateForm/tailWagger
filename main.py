from typing import Any
import discord
from os import environ, path
import asyncio
from discord.flags import Intents
from discord import Embed
from logs_watch import LogsWatch
import parse_utilities
import requests
from srcds.rcon import RconConnection
from typing import List
import numpy as np
import json
from collections import ChainMap
from rcon_listener import RconListener
from reactivex import operators, from_
from kill_watch import KillWatch

# todo: split this into files
# todo: use dataclasses for config
# todo: automate channel registry

# note: revisit parse_utilities if punishments changed
PUNISHMENTS = [".warn", ".ban"]
PUNISHMENT_REMOVALS = [".warnremove"]
CMD_EXECUTOR = ".run "
PLAYER_CONFIG_PATH = "./persist/player_config.npy"


class Wagger(discord.Client):
    # todo: fix these types or parse channels ids from env, right now are being set to string despite type annotation
    _channel_id: int = None
    _warn_channel_id: int = None
    _ban_channel_id: int = None
    _console_channel_id: int = None
    _server_status_channel_id: int = None
    _unpunish_channel_id: int = None
    _server_noti_channel_id: int = None
    _tech_noti_channel_id: int = None
    _channel: discord.TextChannel = None
    _warn_channel: discord.TextChannel = None
    _console_channel: discord.TextChannel = None
    _server_status_channel: discord.TextChannel = None
    _unpunish_channel: discord.TextChannel = None
    _unpunish_channel: discord.TextChannel = None
    _server_noti_channel: discord.TextChannel = None
    _tech_noti_channel: discord.TextChannel = None
    _rcon_ready: bool = False
    _rcon_cmd_blacklist: List[str] = []
    _server_status_job = None
    # potential security risk
    _rcon_password: str
    _rcon_port: int
    _rcon_addr: str
    player_config: dict = {"tags": {}, "salutes": {}, "watch": {}}
    ready: bool = False
    current_rex = ""

    def __init__(
        self,
        channel_id,
        warn_channel_id,
        console_channel_id,
        server_status_channel_id,
        unpunish_channel_id,
        server_noti_channel_id,
        tech_noti_channel_id,
        intents: Intents,
        rcon_pass: str | None = None,
        rcon_addr: str | None = None,
        rcon_port: int | None = None,
        rcon_cmd_blacklist: list[str] = [],
        **options: Any,
    ) -> None:
        self._channel_id = channel_id
        self._warn_channel_id = warn_channel_id
        self._console_channel_id = console_channel_id
        self._server_status_channel_id = server_status_channel_id
        self._unpunish_channel_id = unpunish_channel_id
        self._server_noti_channel_id = server_noti_channel_id
        self._tech_noti_channel_id = tech_noti_channel_id
        if rcon_pass and rcon_addr and rcon_port:
            self._rcon_addr = rcon_addr
            self._rcon_password = rcon_pass
            self._rcon_port = rcon_port
            self._rcon_cmd_blacklist = rcon_cmd_blacklist
            self._server_status_job = asyncio.get_event_loop().create_task(
                self.server_status_watch()
            )
        self.load_config()
        super().__init__(intents=intents, **options)

    # def _connect_rcon(self):
    #     self._rcon_connection = RconConnection(
    #         self._rcon_addr,
    #         self._rcon_port,
    #         self._rcon_password,
    #         single_packet_mode=True,
    #     )

    async def on_ready(self):
        self._channel = await self.fetch_channel(self._channel_id)
        self._warn_channel = await self.fetch_channel(self._warn_channel_id)
        self._console_channel = await self.fetch_channel(self._console_channel_id)
        self._server_status_channel = await self.fetch_channel(
            self._server_status_channel_id
        )
        self._unpunish_channel = await self.fetch_channel(self._unpunish_channel_id)
        self._server_noti_channel = await self.fetch_channel(
            self._server_noti_channel_id
        )
        self._tech_noti_channel = await self.fetch_channel(
            self._tech_noti_channel_id
        )
        print(f"Logged on as {self.user}")
        self.ready = True

    async def send(self, content: str):
        await self._channel.send()
        await self._channel.send(content)

    def save_config(self):
        print(f"Saving file to ${PLAYER_CONFIG_PATH}")
        np.save(PLAYER_CONFIG_PATH, self.player_config)

    def load_config(self):
        print(f"Loading file from ${PLAYER_CONFIG_PATH}")
        file_exists = path.exists(PLAYER_CONFIG_PATH)
        print(f"File ${PLAYER_CONFIG_PATH} exists? {file_exists}")
        if not file_exists:
            print(">Could not load player config file as it does not exit")
            return
        self.player_config = np.load(PLAYER_CONFIG_PATH, allow_pickle=True).item()

    def add_watch(self, cmd: str):
        args = cmd.split(" ", 2)
        if len(args) < 3:
            return "Invalid arguments"
        id = args[1]
        reason = args[2]
        if "watch" not in self.player_config:
            self.player_config["watch"] = {}
        self.player_config["watch"][id] = reason
        self.save_config()
        return json.dumps(self.player_config, indent=2)

    def unwatch(self, cmd: str):
        args = cmd.split(" ")
        if len(args) != 2:
            return "Invalid arguments"
        id = args[1]
        self.player_config["watch"].pop(id, None)
        self.save_config()
        return json.dumps(self.player_config, indent=2)

    async def process_joiners(self, joiners: dict[str, str]):
        ids = joiners.keys()
        if len(ids) == 0:
            return
        await self.notify_watch(joiners)

    async def exec_command(self, cmd: str) -> str:
        try:
            if cmd.startswith("watch "):
                return self.add_watch(cmd)
            if cmd.startswith("unwatch "):
                return self.unwatch(cmd)
            if any([cmd.startswith(black) for black in self._rcon_cmd_blacklist]):
                return "Forbidden"
            target_con = RconConnection(
                self._rcon_addr,
                self._rcon_port,
                self._rcon_password,
                single_packet_mode=True,
            )
            print(f"Executing {cmd}")
            response: bytes = await asyncio.to_thread(target_con.exec_command, cmd)
            print(f"Excuted {cmd}")

            # response_parsed = response.replace("b'", "").replace("\n\x00\x00", "")
            response_parsed = response.decode("US-ASCII").replace("\x00\x00", "")
            target_con._sock.close()
            return response_parsed
        except ConnectionError:
            return "RCON Connection Error"
        except Exception as e:
            print(f"Unknown error occured {str(e)}")
            return "Uknown error"

    async def notify_watch(self, targets: dict[str, str]):
        ids = targets.keys()
        config = self.player_config["watch"]
        target_ids = set(id for id in ids if id in config.keys())
        if len(target_ids) == 0:
            return
        [
            asyncio.create_task(
                self._server_noti_channel.send(
                    f"@here Player `{targets[id]} ({id})` has joined server. WatchReason: **{config[id]}**"
                )
            )
            for id in target_ids
        ]

    async def server_status_watch(self, interval_secs: int = 30):
        while True:
            if self._console_channel == None:
                await asyncio.sleep(interval_secs)
            try:
                embed = Embed(description="Server Status")
                server_status = await self.exec_command("info")
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
                server_name = server_status_dict["ServerName"]
                embed.description = f"```{server_name}```"
                embed.add_field(name="Status", value=":green_circle:")
                embed.add_field(name="Gamemode", value=server_status_dict["GameMode"])
                embed.add_field(name="Current Map", value=server_status_dict["Map"])
                playerlist = await self.exec_command("playerlist")
                code_block_playerlist = f"```{playerlist}```"
                playerlist_sanitized: List[str] = []
                player_count = 0
                no_players_online = (
                    playerlist == "There are currently no players present"
                )

                if not no_players_online:
                    playerlist_rows = [row for row in playerlist.split("\n") if row]
                    current_list_size = 0
                    player_count = len(playerlist_rows)
                    for row_index, row in enumerate(playerlist_rows):
                        sanitized_row = parse_utilities.get_sanitized_playerrow(row)
                        expected_new_lines = row_index + 1
                        expected_new_list_size = current_list_size + len(sanitized_row)
                        if expected_new_lines + expected_new_list_size > 990:
                            playerlist_sanitized.append(
                                "-- LIST CUT OFF FOR DISPLAY --"
                            )
                            break
                        playerlist_sanitized.append(sanitized_row)
                        current_list_size += len(sanitized_row)
                    playerlist_sanitized_joined = "\n".join(playerlist_sanitized)
                    code_block_playerlist = f"```{playerlist_sanitized_joined}```"

                embed.add_field(
                    name=f"Player list ({player_count})",
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
        response = await self.exec_command(message_cmd)
        code_block_response = f"```{response}```"
        if len(response) > 1000:
            await message.reply(code_block_response)
            return
        embed = Embed(title="CMD")
        embed.add_field(name="Input", value=message_cmd, inline=False)
        embed.add_field(name="Output", value=code_block_response, inline=False)
        await message.reply(embed=embed)

    async def get_player_info(self, playfab_id: str) -> dict:
        user_agent = environ["USER_AGENT"]
        info_api = environ["INFO_API"]
        url = f"{info_api}/{playfab_id}"
        headers = {"User-Agent": user_agent}
        response = await asyncio.to_thread(requests.get, url, headers=headers)
        json_response = response.json()
        return json_response

    async def send_punishment(self, embed: Embed, message: str):
        punishment: parse_utilities.Punishment = parse_utilities.get_punishment(message)
        json_response = await self.get_player_info(punishment.playfab_id)
        embed.title = "Punishment"
        embed.color = discord.colour.Colour.from_str("#8b0000")
        embed.add_field(name="Culprit Name", value=json_response["name"])
        embed.add_field(name="Culprit Platform", value=json_response["platform"])
        embed.add_field(name="Reason", value=punishment.reason)
        embed.add_field(name="Duration", value=punishment.duration)
        embed.set_image(url=json_response["avatarUrl"])
        if punishment.type == ".warn":
            await self._warn_channel.send(embed=embed)
        return embed

    async def send_unpunishment(self, embed: Embed, message: str):
        new_embed = Embed()
        new_embed.title = "Warn-Remove Log"
        descrip = embed.description
        split = descrip.split("\n**")
        # todo: fix this.... embed.fields needs to work
        author_key = [element for element in split if element.startswith("Sender")]
        author_value = author_key[0]
        true_author = author_value.replace("Sender:** ", "")
        new_embed.add_field(name="Author", value=true_author, inline=False)
        culprit_playfab_id = message.split(" ")[1]
        culprit_info = await self.get_player_info(culprit_playfab_id)
        culprit_name = culprit_info["name"]
        new_embed.add_field(
            name="Culprit", value=f"{culprit_name} ({culprit_playfab_id})"
        )
        new_embed.set_image(url=culprit_info["avatarUrl"])
        await self._unpunish_channel.send(embed=new_embed)

    async def send_ip_event(self, embed: Embed):
        await self._tech_noti_channel.send(embed=embed)

    async def on_message(self, message: discord.message.Message):
        if message.content == "ping":
            await message.channel.send("pong")
        elif str(
            message.channel.id
        ) == self._console_channel_id and message.content.startswith(CMD_EXECUTOR):
            await self.exec_discord_command(message)
        elif len(message.embeds) > 0 and str(message.channel.id) == self._channel_id:
            embed = message.embeds[0]
            source_dict = embed.to_dict()
            new_embed = Embed.from_dict(source_dict)

            embed_dict = parse_utilities.embed_to_dict(new_embed)
            true_message = embed_dict.get("Message", "")
            if embed_dict["Type"] == "AdminPrivateAnnounce":
                print("Deleting ")
                try:
                    self._channel.delete_messages()
                    await message.delete()
                except e:
                    print(f"Failed to delete message. {str(e)}")
                return
            if any(true_message.startswith(unpun) for unpun in PUNISHMENT_REMOVALS):
                try:
                    await self.send_unpunishment(new_embed, true_message)
                except Exception as e:
                    print(f"Failed to send unpunishment log. {str(e)}")
            elif any(true_message.startswith(pun) for pun in PUNISHMENTS):
                try:
                    await self.send_punishment(new_embed, true_message)
                except Exception as e:
                    print(f"Failed to send punishment log. {str(e)}")


# this is untenable, create some sort of configuration collector
intents = discord.Intents.default()
intents.message_content = True
target_channel_id = environ["D_CHANNEL_ID"]
warn_channel_id = environ["D_PUN_CHANNEL_ID"]
console_channel_id = environ["D_CONSOLE_CHANNEL_ID"]
server_status_channel_id = environ["D_SERVER_STATUS_ID"]
unpunish_channel_id = environ["D_UNPUNISH_CHANNEL_ID"]
tech_noti_id = environ["D_TECH_NOTI_D"]
server_noti_id = environ["D_SERVER_NOTI_ID"]
rcon_addr = environ["RCON_ADDRESS"]
rcon_pass = environ["RCON_PASSWORD"]
rcon_port_unparsed = environ["RCON_PORT"]
cmd_blacklist_unparsed = environ["RCON_CMD_BLACKLIST"]
cmd_blacklist = cmd_blacklist_unparsed.split(",")
rcon_port = int(rcon_port_unparsed)
client = Wagger(
    target_channel_id,
    warn_channel_id,
    console_channel_id,
    server_status_channel_id,
    unpunish_channel_id,
    server_noti_id,
    tech_noti_id,
    intents=intents,
    rcon_addr=rcon_addr,
    rcon_port=rcon_port,
    rcon_pass=rcon_pass,
    rcon_cmd_blacklist=cmd_blacklist,
)
loop = asyncio.get_event_loop()

login_listener = RconListener(event="login", listening=False)
killfeed_listener = RconListener(event="killfeed", listening=False)
kill_watcher = KillWatch()
logs_watch = LogsWatch(environ["LOGS_PATH"])

PLAYER_MAP: dict[str, str] = {}


def login_process(event: str):
    (success, event_data) = parse_utilities.parse_event(
        event, parse_utilities.GROK_LOGIN_EVENT
    )
    if not success:
        return
    event_text = event_data.get("eventText", "").lower()
    if event_text.lower().startswith(
        "logged out"
    ) and client.current_rex == event_data.get("playfabId", None):
        client.current_rex = ""
    if not event_text.lower().startswith("logged in"):
        return
    try:
        playfab_id = event_data["playfabId"]
        userName = event_data["userName"]
        PLAYER_MAP[playfab_id] = userName
        asyncio.create_task(client.process_joiners({playfab_id: userName}))
    except Exception as e:
        print(f"Failed to process login event {str(e)}")


login_listener.pipe(operators.filter(lambda x: x.startswith("Login:"))).subscribe(
    login_process
)
kill_watcher.subscribe(
    on_next=lambda x: asyncio.create_task(client.exec_command(f"say {x}"))
)


def logout_log_process(log: str):
    (success, parsed) = parse_utilities.parse_event(
        log, parse_utilities.GROK_LOGOUT_LOG
    )
    if not success:
        return
    embed = Embed(title="Ip Event")
    playfabId = parsed.get("playfabId", None)
    userName = PLAYER_MAP.get(playfabId, "")
    embed.add_field(name="PlayfabId", value=parsed.get("playfabId", None), inline=False)
    embed.add_field(name="Username", value=userName, inline=False)
    embed.add_field(name="IP", value=parsed.get("ipAddress"), inline=False)
    embed.add_field(name="RAW", value=log, inline=False)
    asyncio.create_task(client.send_ip_event(embed))


logs_watch.pipe(operators.filter(lambda x: "UNetConnection::Close" in x)).subscribe(
    logout_log_process
)


async def main():
    await asyncio.gather(
        logs_watch.run(),
        killfeed_listener.run(),
        login_listener.run(),
        client.start(environ["D_TOKEN"]),
    )


loop.run_until_complete(main())
