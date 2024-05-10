from collections import namedtuple
import re
from discord import Embed
from pygrok import Grok

Punishment = namedtuple("Punishment", ["type", "playfab_id", "reason", "duration"])
GROK_LOGIN_EVENT = "%{WORD:eventType}: %{NOTSPACE:date} %{GREEDYDATA:userName} \(%{WORD:playfabId}\) %{GREEDYDATA:eventText}"
GROK_KILLFEED_EVENT = "%{WORD:eventType}: %{NOTSPACE:date}: %{NOTSPACE:killerPlayfabId} \(%{GREEDYDATA:userName}\) killed %{NOTSPACE:killedPlayfabId} \(%{GREEDYDATA:killedUserName}\)"
GROK_KILLFEED_BOT_EVENT = "%{WORD:eventType}: %{NOTSPACE:date}: %{NOTSPACE:killerPlayfabId} \(%{GREEDYDATA:userName}\) killed  \(%{GREEDYDATA:killedUserName}\)"


def parse_event(event: str, grok_pattern: str) -> tuple[bool, dict[str, str]]:
    pattern = Grok(grok_pattern)
    match = pattern.match(event)
    if not match:
        return (False, match)
    else:
        return (True, match)


def get_info_from_login(login_event: str) -> dict[str, str]:
    pattern = Grok(
        "%{WORD:eventType}: %{NOTSPACE:date} %{GREEDYDATA:userName} \(%{WORD:playfabId}\) %{GREEDYDATA:eventText}"
    )
    match = pattern.match(login_event)
    if not match:
        return {}
    return match


# doing this because i've seen discord allows embeds without the expected fields() array
def embed_to_dict(embed: Embed):
    fields = embed.fields
    if fields:
        return dict((field.name, field.value) for field in fields)
    embed_descr = embed.description
    lines = embed_descr.split("\n")
    pairs = [line.split(":** ") for line in lines if line]
    dictionary = dict((key.lstrip("**"), value) for [key, value] in pairs)
    return dictionary


def get_playfab_id_map(player_row: str) -> dict[str, str]:
    regex = re.compile(r"([A-Z0-9])*\)$")
    match = regex.search(player_row)
    if not match:
        return {}
    matched_str = match.group(0).rstrip(")")
    player_name = player_row.rstrip(f" ({matched_str})")
    return {matched_str: player_name}


def get_punishment(message: str) -> tuple:
    split_message = message.split(" ")
    pun_type = split_message[0]
    playfab_id = split_message[1]
    reason = None
    duration: str | None = None
    duration_int: int | None = None
    # todo: find way to do this without .warn lockin
    if pun_type == ".warn":
        reason = split_message[2]
        duration = split_message[3] if len(split_message) > 3 else None
    else:
        reason = split_message[3] if len(split_message) > 3 else None
        duration = split_message[2]
    if duration:
        try:
            duration_int = int(duration)
        except Exception:
            print(f"Failed to parse duration for '{message}'")
    r = Punishment(pun_type, playfab_id, reason, duration_int)
    return r


def get_sanitized_playerrow(rcon_player_row: str, with_playfab_id: bool = True):
    try:
        pattern_for_bots = re.compile("^There are \d+ bots")
        pattern_for_empty = re.compile("^There are currently no players present")
        # checking if this is the row that has the bots information
        if pattern_for_bots.match(rcon_player_row) or pattern_for_empty.match(
            rcon_player_row
        ):
            return rcon_player_row
        separator = ", "
        split_row = rcon_player_row.split(separator)
        # the next 3 liner overengineeer a solution for ppl with commas in their names
        split_row_without_last_ones = split_row[:-2]
        playfab_id = split_row_without_last_ones[0]
        name = separator.join(split_row_without_last_ones[1:])
        return f"{name} ({playfab_id})" if with_playfab_id else name
    except Exception as e:
        print(
            f"Failed to properly process rcon playerlist row ({rcon_player_row}). Error: {str(e)}"
        )
        return rcon_player_row
