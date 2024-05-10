from reactivex import Subject
import math

STREAK_TEMPLATES = {
    5: "{0} is on a 5+ kill streak!",
    10: "{0} is on a 10+ kill streak!",
    15: "15 CONSECUTIVE KILLS BY {0}!",
    20: "20?! 20 (!!!) CONSECUTIVE KILLS BY {0}",
    "*": "INSANE {1} CONSECUTIVE KILLSTREAK BY {0}!",
}


def get_closest_multiple(n: int, factor: int):
    return round(factor * round(n / factor))


class KillWatch(Subject[str]):
    scoreboard = dict[str, int]

    def __init__(self) -> None:
        self.scoreboard = {}
        super().__init__()

    def handle_killer_streak(self, userName: str, playfabId: str):
        current_streak = self.scoreboard.get(playfabId, 0)
        current_streak += 1
        self.scoreboard[playfabId] = current_streak
        if current_streak > 0 and current_streak % 5 != 0:
            return
        closest_mult = get_closest_multiple(current_streak, 5)
        if current_streak != closest_mult:
            return
        template = STREAK_TEMPLATES.get(current_streak, STREAK_TEMPLATES["*"])
        msg = template.format(userName, current_streak)
        self.on_next(msg)

    def handle_killed_streak(self, userName: str, playfabId: str):
        current_streak = self.scoreboard.get(playfabId, 0)
        if current_streak == 0:
            return
        self.scoreboard[playfabId] = 0

    def handle_event(self, event_data: dict[str, str]):
        killer = event_data.get("userName", "")
        killed = event_data.get("killedUserName", "")
        killerPlayfabId = event_data.get("killerPlayfabId", "")
        killedPlayfabId = event_data.get("killedPlayfabId", "BOT")
        if not killerPlayfabId:
            return
        self.handle_killer_streak(killer, killerPlayfabId)
        self.handle_killed_streak(killed, killedPlayfabId)
