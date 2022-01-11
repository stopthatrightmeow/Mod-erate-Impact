# syntax=docker/dockerfile:1
FROM python:3.9-slim-buster

WORKDIR /app

# Copy in application requirements
COPY requirements.txt requirements.txt

# Install requirements
RUN pip3 install -r requirements.txt

COPY . . 

CMD [ "python3", "main.py"]
