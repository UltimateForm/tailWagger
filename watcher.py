from io import TextIOWrapper
import time
import asyncio

class Watcher():
	_path:str = ""
	_pointer:int = 0
	_file:TextIOWrapper = None
	_interval = 2.5
	def __init__(self, path:str, interval:float) -> None:
		self._path = path
		self._interval = interval

	def _load_file(self) -> TextIOWrapper:
		file = open(self._path, "r")
		return file

	def __aiter__(self):
		self._file = self._load_file()
		self._file.read()
		return self

	async def __anext__(self):
		await asyncio.sleep(self._interval)
		content = self._file.read()
		self._pointer += 1
		if self._pointer >= 25:
			raise StopIteration()
		return content

if __name__ == "__main__":
	watch = Watcher("/home/monke/src/tailWagger/target.txt", 10)
	for item in watch:
		print(f"Here item {item}")