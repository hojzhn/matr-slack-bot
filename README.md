# Slack Slash-Command Bot

A minimal Slack bot (using [Bolt for Python](https://slack.dev/bolt-python/) in
**Socket Mode**) that responds to the `/hello` slash command.

## 1. Create the Slack app

1. Go to <https://api.slack.com/apps> → **Create New App** → *From scratch*.
2. **Socket Mode** → enable it. This generates an **App-Level Token** (starts
   with `xapp-`) with the `connections:write` scope. Save it.
3. **Slash Commands** → **Create New Command**:
   - Command: `/hello`
   - (Request URL can be anything, e.g. `https://example.com` — Socket Mode
     ignores it.)
4. **OAuth & Permissions** → add the `commands` bot scope, then **Install to
   Workspace**. Copy the **Bot User OAuth Token** (starts with `xoxb-`).

## 2. Set environment variables

PowerShell:

```powershell
$env:SLACK_BOT_TOKEN = "xoxb-..."   # Bot User OAuth Token
$env:SLACK_APP_TOKEN = "xapp-..."   # App-Level Token
```

## 3. Install & run

```powershell
.\.venv\Scripts\python.exe -m pip install -r production-support\requirements.txt
.\.venv\Scripts\python.exe production-support\app.py
```

When it's running, type `/hello` (or `/hello world`) in any channel where the
bot is installed and it will reply.
