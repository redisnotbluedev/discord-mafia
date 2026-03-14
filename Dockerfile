# --- Discord Mafia Bot Container ---
FROM python:3.14-slim

# Prevents Python from writing .pyc files and enables unbuffered output
# so logs appear immediately in `podman logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Install source code ---
WORKDIR /opt/discord-mafia

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker_entrypoint.sh

# --- Data volume ---
# The app writes data.json and games_ongoing.txt to its CWD.
# We declare /data as a volume so this state persists across
# container restarts.  The entrypoint script symlinks read-only
# source files (models.json, images/) into this directory.
VOLUME /data
WORKDIR /data

# Secrets (TOKEN, OPENAI_API_KEY, etc.) are passed at runtime
# via --env-file.  NEVER bake them into the image.
ENTRYPOINT ["/opt/discord-mafia/docker_entrypoint.sh"]
CMD ["python", "/opt/discord-mafia/main.py"]
