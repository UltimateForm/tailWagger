from collections import namedtuple
import re
Punishment = namedtuple("Punishment", ["type", "playfab_id", "reason", "duration"])


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

def get_sanitized_playerrow(rcon_player_row:str):
    try:
        pattern_for_bots = re.compile("^There are \d+ bots")
        # checking if this is the row that has the bots information
        if pattern_for_bots.match(rcon_player_row):
            return rcon_player_row
        separator = ", "
        split_row = rcon_player_row.split(separator)
        # the next 3 liner overengineeer a solution for ppl with commas in their names
        split_row_without_last_ones = split_row[:-2]
        playfab_id = split_row_without_last_ones[0]
        name = separator.join(split_row_without_last_ones[1:])
        return f"{name} ({playfab_id})"
    except Exception as e:
        print(f"Failed to properly process rcon playerlist row ({rcon_player_row}). Error: {str(e)}")
        return rcon_player_row