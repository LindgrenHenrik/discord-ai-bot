pip freeze > requirements.txt

source .venv/bin/activate

docker build -t my-python-app .

docker run -d --name my-running-app my-python-app

This is what to write to give the docker container access to restarting host docker containers
docker run -d --name my-running-app -v /var/run/docker.sock:/var/run/docker.sock my-python-app

docker compose --profile download up --build

docker compose --profile auto up --build -d


docker system prune -a