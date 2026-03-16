# Getting Started

How to set up a local development environment for the Discord Mafia bot.

## Prerequisites

You'll need:
- **Git** — to clone the repository
- **Python 3.10+** — the codebase uses modern type syntax (`int | None`, `dict[int, str]`); this guide sets up Python 3.14
- [**Podman**](https://podman.io/) or [**Docker**](https://www.docker.com/) — recommended for running the bot in an isolated container (Podman recommended)
- A **Discord bot application** — see next section
- An **OpenAI-compatible API key** — for AI player completions

## 1. Create a Discord Bot Application

Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application (or select an existing one).

### Privileged Gateway Intents

Under **Bot → Privileged Gateway Intents**, enable:

| Intent | Required | Why |
|---|---|---|
| **Message Content** | **Yes** | The bot reads message content to route player speech to the game engine (`on_message` in `main.py` and `turnmanager.py`). Without this, `message.content` is empty for messages the bot didn't send. |
| Presence | No | Not used. |
| Server Members | No | Not used. |

The bot also uses `Intents.default()` (which includes non-privileged intents like Guilds, Guild Messages, and Guild Message Reactions) — these don't need to be toggled on in the portal.

### Bot Permissions

Under **OAuth2 → URL Generator**, select the scopes **`bot`** and **`applications.commands`**, then enable these permissions:

| Permission | Where it's used |
|---|---|
| **View Channel** | `scheduler.py` — the bot grants itself `view_channel=True` on the game channel during a game to guarantee visibility even when @everyone is locked out. |
| **Send Messages** | Everywhere — lobby embeds, game announcements, AI player speech, error messages. |
| **Manage Messages** | `abstractor.py` — deletes stale lobby messages. `turnmanager.py` — deletes timed-out turn prompts. |
| **Manage Roles** | `scheduler.py` — assigns/removes the "Mafia Player" role to participants. `moderation.py` — creates the role during `/setup`. |
| **Manage Webhooks** | `moderation.py` — creates a webhook during `/setup` so AI players can post with custom names and avatars. |
| **Manage Threads** | `scheduler.py` — locks the Mafia private thread after the game ends. |
| **Create Public Threads** | `scheduler.py` — the bot grants itself this permission on the channel during a game (used as part of its self-permission override). |
| **Create Private Threads** | `scheduler.py` — creates "Mafia Private Chat" as a private thread for Mafia-team discussion. |
| **Send Messages in Threads** | `turnmanager.py` — AI players and the bot post in the Mafia private thread. The bot also grants/revokes this per-player to enforce turn order. |

The generated permission integer should be **`395942308864`**.

> ⚠️ Copy the generated invite URL from the portal and use it to invite your bot to a server. The URL will look like:
> `https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=395942308864&integration_type=0&scope=bot+applications.commands`

### Bot Token

Under **Bot → Token**, click **Reset Token** to generate a new token. Copy it — you'll need it for the `.env` file in step 5. You can only see the token once; if you lose it, you'll need to reset it again.

## 2. Install Python with pyenv

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

## 3. Create a Virtual Environment

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

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `discord.py` — Discord API wrapper
- `python-dotenv` — loads `.env` files into environment variables
- `openai` — OpenAI-compatible API client (used for AI player completions)
- `psutil` — system info for the `/info` command

## 5. Configure Secrets

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

## 6. Initialize Runtime Data

Create an empty `data.json` in the project root:

```bash
echo {} > data.json
```

This file stores channel profiles, webhook URLs, and guild configs at runtime. It's also in `.gitignore`.

## 7. Run the Bot

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

## 8. Set Up a Discord Channel

Once the bot is running and invited to your server, do one last check of its permissions. If the channel is private, you'll likely need to set up some overrides.  (or a role) 

Your ultimate goal is for the bot to manifest these privileges on the channel you are interested in:

- View Channel
- Manage Channel
- Manage Permissions
- Send Messages
- Send Messages in Threads
- Create Public Threads
- Create Private Threads
- Manage Threads

## 9. Ask The Bot to Install Itself

1. Use the `/setup` command in the channel where you want games to run
2. The bot will create a "Mafia Player" role automatically
3. Send any message in the channel to trigger the lobby embed

The exact effects of Setup appear to be:

- The bot edits its channel overrides (in various ways that should be noops but probably aren't)
- The bot creates the Mafia Player role, which is used for players who are currently in a game of mafia.
- The bot waits for a message to be sent -- when it is, it blocks off the channel and creates a view advertising the game

## 10. Start a Game

The bot defers some setup steps until game start, at which time:

- It explicitly blocks everyone except a selected player from posting in the channel.
- It replaces its channel permission overrides to match the above.
- It creates a webhook which it will use to talk to Discord.
- It creates Mafia Private Chat for the game.
- It adds every player to the Mafia Player role.

In theory, players should stop being Mafia Players when the game ends. (In practice, it's unclear that this works.)