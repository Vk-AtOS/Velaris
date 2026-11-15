# Velaris production image. Build from the repository root:  docker build -f deploy/Dockerfile -t velaris:local .
# One image, two roles (see deploy/docker-compose.example.yml):
#   API (8730, internal, gateway only):  python -m velaris.api
#   Public app (8731, behind nginx):     python -m velaris.api.public
# Runs as a non-root user with a read-only root filesystem: the only writable paths are the VELARIS_DATA volume and /tmp (tmpfs).
FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VELARIS_DATA=/data VELARIS_API_HOST=0.0.0.0 VELARIS_PUBLIC_HOST=0.0.0.0

RUN groupadd --system --gid 10001 velaris \
 && useradd --system --uid 10001 --gid velaris --home-dir /nonexistent --shell /usr/sbin/nologin velaris \
 && mkdir /data && chown velaris:velaris /data && chmod 700 /data

WORKDIR /app
# Dependencies first (layer cache). Versions are pinned by deploy/constraints.txt.
COPY requirements.txt deploy/constraints.txt /app/deploy/
RUN grep -v '^pytest' /app/deploy/requirements.txt > /tmp/runtime.txt \
 && pip install -r /tmp/runtime.txt -c /app/deploy/constraints.txt && rm /tmp/runtime.txt

COPY --chown=root:root velaris /app/velaris
COPY --chown=root:root departments /app/departments
COPY --chown=root:root main.py /app/main.py
COPY --chown=root:root deploy/healthcheck.py /app/healthcheck.py

USER velaris:velaris
VOLUME ["/data"]
EXPOSE 8730 8731
# ponytail: one worker per process on purpose. The gateway replay cache (velaris/api/auth.py) and the public rate limiter
# are per process; several workers would let a replayed request or a burst through a sibling worker. Scale by running
# separate deployments per organisation (VELARIS_ORG is one organisation per deployment), not --workers.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "/app/healthcheck.py", "8730", "/health"]
CMD ["python", "-m", "velaris.api"]
