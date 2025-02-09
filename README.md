pip freeze > requirements.txt
source .venv/bin/activate
python bot.py


docker stop my-running-app
docker rm my-running-app
docker build -t my-python-app .

docker run -d --name my-running-app my-python-app
This is what to write to give the docker container access to restarting host docker containers
docker run -d --name my-running-app -v /var/run/docker.sock:/var/run/docker.sock my-python-app



in the stable-diffusion-webui-docker
docker compose --profile download up --build
docker compose --profile auto up --build -d


docker system prune -a


https://discord.com/developers/applications
discord bot
create app
insallation: remove install link
private bot and give more permissions


fix for auto container..
https://github.com/AbdBarho/stable-diffusion-webui-docker/issues/719