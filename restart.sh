docker stop mordhau-bot-container
docker rm mordhau-bot-container
docker build . -t mordhau-bot
docker run -d --name mordhau-bot-container mordhau-bot
