# Verifier image. It carries its own build of the simulator and re-executes
# the journal from the seed, so the reward never depends on agent-side files.
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY crucible /src/crucible
RUN cc -O2 -shared -fPIC -o /src/crucible/libcore.so /src/crucible/core.c

FROM python:3.12-slim
COPY --from=build /src/crucible /tests/crucible
COPY test.sh grade.py seed.txt /tests/
RUN chmod 755 /tests/test.sh
WORKDIR /tests
