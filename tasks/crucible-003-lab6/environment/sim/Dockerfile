FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY crucible /src/crucible
RUN cc -O2 -shared -fPIC -o /src/crucible/libcore.so /src/crucible/core.c

FROM python:3.12-slim
COPY --from=build /src/crucible /opt/crucible
RUN mkdir -p /var/crucible
WORKDIR /opt
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "crucible.server", "--data", "/var/crucible", "--port", "8000"]
