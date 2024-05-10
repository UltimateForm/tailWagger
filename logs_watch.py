import asyncio
from io import TextIOWrapper
from reactivex import Subject, operators
from reactivex.abc.observable import Subscription


class LogsWatch(Subject[str]):
    _path: str

    def __init__(self, path: str) -> None:
        self._path = path
        super().__init__()

    async def follow(self, thefile: TextIOWrapper):
        thefile.seek(0, 2)
        while True:
            line: str = thefile.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue
            yield line.strip()

    async def run(self):
        async for x in self.follow(open(self._path)):
            self.on_next(x)

if __name__ == "__main__":
  watcher = LogsWatch("path")
  watcher.pipe(operators.filter(lambda x: "UNetConnection::Close" in x)).subscribe(lambda x: print(f"HERE {x}"))

  asyncio.run(watcher.run())
