FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash curl ca-certificates git gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# OpenCode is the recommended harness. Shipping it in the image means Harbor
# finds it already installed and each trial starts in seconds instead of
# reinstalling Node and OpenCode over the network.
ENV NVM_DIR=/root/.nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" && nvm install 22 && nvm alias default 22 \
    && npm i -g opencode-ai@latest && opencode --version

COPY crucible /usr/local/bin/crucible
RUN chmod 755 /usr/local/bin/crucible

ENV CRUCIBLE_URL=http://sim:8000
WORKDIR /app
