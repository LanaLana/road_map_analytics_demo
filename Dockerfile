FROM ubuntu:latest

LABEL maintainer="Svetlana"

RUN DEBIAN_FRONTEND='noninteractive' apt-get update && apt-get upgrade -y --no-install-recommends 
RUN DEBIAN_FRONTEND="noninteractive" apt-get -y install tzdata

RUN apt-get install -y python3-pip

COPY requirements.txt .

RUN apt-get update && apt-get install -y python3-opencv
RUN pip install opencv-python

RUN pip install --upgrade pip &&\
    pip install -r requirements.txt
WORKDIR /user

CMD ["python3", "./road_map_SF.py"]
