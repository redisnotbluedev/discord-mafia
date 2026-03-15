# Getting Started

How to set up a local development environment for the Discord Mafia bot.

## Prerequisites

You'll need:
- **Git** — to clone the repository
- **Python 3.10+** — the codebase uses modern type syntax (`int | None`, `dict[int, str]`); this guide sets up Python 3.14
- [**Podman**](https://podman.io/) or [**Docker**](https://www.docker.com/) — recommended for running the bot in an isolated container (Podman recommended)
- A **Discord bot token** — from the [Discord Developer Portal](https://discord.com/developers/applications)
- An **OpenAI-compatible API key** — for AI player completions

## 1. Install Python with pyenv

[pyenv](https://github.com/pyenv/pyenv) lets you install and switch between Python versions without touching your system Python.

### Windows (pyenv-win)

```powershell
# Install pyenv-win via the official installer:
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"

# Restart your terminal, then:
pyenv install 3.14
pyenv local 3.14         # creates a .python-version file in the repo
python --version         # should show 3.14.x
```

### macOS / Linux

```bash
# Install pyenv (see https://github.com/pyenv/pyenv#installation)
curl https://pyenv.run | bash

# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.):
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Restart your terminal, then:
pyenv install 3.14
pyenv local 3.14
python --version
```

## 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it:

| OS | Shell | Command |
|---|---|---|
| Windows | PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows | cmd | `.venv\Scripts\activate.bat` |
| macOS / Linux | bash/zsh | `source .venv/bin/activate` |

Your prompt should now show `(.venv)`.

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `discord.py` — Discord API wrapper
- `python-dotenv` — loads `.env` files into environment variables
- `openai` — OpenAI-compatible API client (used for AI player completions)
- `psutil` — system info for the `/info` command

## 4. Configure Secrets

```bash
cp .env.example .env
```

Edit `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `TOKEN` | **Yes** | Your Discord bot token |
| `OPENAI_API_KEY` | **Yes** | API key for an OpenAI-compatible provider |
| `OPENAI_BASE_URL` | No | Override if using a non-OpenAI provider (e.g. `https://api.together.xyz/v1`) |
| `LOG_WEBHOOK_URL` | No | Discord webhook URL to receive log messages |
| `ADMIN_USERS` | **Yes** | Comma-separated Discord user IDs allowed to use admin commands (`/setup`, `/echo`) |

> ⚠️ **Never commit `.env`** — it's already in `.gitignore`. Double-check before pushing.

## 5. Initialize Runtime Data

Create an empty `data.json` in the project root:

```bash
echo {} > data.json
```

This file stores channel profiles, webhook URLs, and guild configs at runtime. It's also in `.gitignore`.

## 6. Run the Bot

### Option A: Direct (for quick testing)

```bash
python main.py
```

You should see log output like `Logged in as YourBot#1234!`

### Option B: Containerized with Podman or Docker (recommended)

Building and running in a container keeps the bot isolated from your host system. If you don't have either, install Podman from [podman.io](https://podman.io/).

The container separates source code (read-only, at `/opt/discord-mafia`) from runtime data (writable, at `/data`). An entrypoint script symlinks read-only config files (`models.json`, `images/`) into the data volume so the app can find them via its relative-path file access.

Podman installs a `docker` alias that points to `podman`, so you can use the same commands regardless of which container engine you are using.

**Build the image:**
```bash
docker build -t discord-mafia .
```

**Run with secrets and a named volume for persistent data:**
```bash
docker run --rm -it \
  --env-file .env \
  -v mafia-data:/data \
  discord-mafia
```

- `--env-file .env` passes secrets at runtime (never baked into the image)
- `-v mafia-data:/data` creates a named volume for `data.json` and `games_ongoing.txt` so game state persists across container restarts

**Detached mode** (background):
```bash
docker run -d --name mafia-bot \
  --env-file .env \
  -v mafia-data:/data \
  discord-mafia

docker logs -f mafia-bot     # follow logs
docker stop mafia-bot        # stop
```

**Inspect or reset data:**
```bash
# See where the volume lives on disk:
docker volume inspect mafia-data

# Start fresh (delete all game state):
docker volume rm mafia-data
```

## 7. Set Up a Discord Channel

Once the bot is running and invited to your server:

1. Use the `/setup` command in the channel where you want games to run
2. The bot will create a webhook and a "Mafia Player" role automatically
3. Send any message in the channel to trigger the lobby embed
