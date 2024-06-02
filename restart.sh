docker stop mordhau-bot-container
docker rm mordhau-bot-container
docker build . -t mordhau-bot
docker run -d -v ./persist/:/bot/persist/ -v /home/mhserver/log/server:/bot/serverlogs --name mordhau-bot-container mordhau-bot
