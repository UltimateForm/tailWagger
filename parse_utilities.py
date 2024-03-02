from collections import namedtuple

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
