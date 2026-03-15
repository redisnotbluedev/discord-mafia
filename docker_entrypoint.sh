#!/bin/sh
# entrypoint.sh — sets up the data volume before starting the bot.
#
# The app uses relative paths for both read-only config (models.json)
# and writable state (data.json, games_ongoing.txt).  We run from a
# writable /data volume and symlink the read-only files from the
# source directory so everything resolves correctly.

set -e

# Symlink read-only source files the app expects to find in CWD.
# -sf: overwrite stale symlinks from previous runs.
ln -sf /opt/discord-mafia/models.json ./models.json
ln -sf /opt/discord-mafia/images      ./images

# Hand off to the CMD (default: python /opt/discord-mafia/main.py).
exec "$@"
