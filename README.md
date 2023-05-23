pip freeze > requirements.txt

source .venv/bin/activate


docker build -t my-python-app .

docker run -d --name my-running-app my-python-app

docker compose --profile auto up --build -d