FROM python:3.10-slim-buster

WORKDIR /app

COPY . /app

RUN pip install .

CMD [ "python", "./main.py" ]