FROM python:3.10-slim-buster

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --use-feature=fast-deps --use-feature=in-tree-build .

CMD [ "python", "./main.py" ]