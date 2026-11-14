FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash curl ca-certificates git gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY crucible /usr/local/bin/crucible
RUN chmod 755 /usr/local/bin/crucible

ENV CRUCIBLE_URL=http://sim:8000
WORKDIR /app
