FROM python:3.12-slim
WORKDIR /code
COPY . /code/

RUN pip install . && \
    stac-api-load-testing --help

ENTRYPOINT ["stac-api-load-testing"]
