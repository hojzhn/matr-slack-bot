# Deploying to a DigitalOcean droplet (Ubuntu, Socket Mode)

The bot uses **Socket Mode** (outbound WebSocket only) — no domain, open ports,
nginx, or DO firewall changes are needed. Deployment = code on the box → venv →
secrets → keep alive with **systemd**.

Paths below assume the repo is cloned to `/opt/matr-slack-bot` and run as a
`slackbot` user. Adjust to taste.

## 0. Push the latest code (local machine)

```bash
git add -A && git commit -m "Add deploy files" && git push origin main
```

## 1. Let the droplet pull from GitHub (deploy key — works for private repos)

SSH into the droplet, then:

```bash
ssh-keygen -t ed25519 -C "matr-slack-bot droplet" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Copy that public key into GitHub → repo **Settings → Deploy keys → Add deploy
key** (read-only is enough). Now the droplet can clone over SSH.

> Alternative: clone over HTTPS with a fine-grained Personal Access Token.

## 2. Install system deps + clone

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
sudo useradd --system --create-home --shell /usr/sbin/nologin slackbot   # optional dedicated user

sudo git clone git@github.com:hojzhn/matr-slack-bot.git /opt/matr-slack-bot
cd /opt/matr-slack-bot
```

## 3. Virtualenv + dependencies

```bash
sudo python3 -m venv /opt/matr-slack-bot/.venv
sudo /opt/matr-slack-bot/.venv/bin/pip install --upgrade pip
sudo /opt/matr-slack-bot/.venv/bin/pip install -r requirements.txt
```

## 4. Secrets

```bash
sudo cp .env.example .env
sudo nano .env          # fill in SLACK_BOT_TOKEN, SLACK_APP_TOKEN, DATABASE_URL
sudo chmod 600 .env
sudo chown -R slackbot:slackbot /opt/matr-slack-bot
```

## 5. Install the systemd service (keeps it running + restarts on reboot/crash)

```bash
sudo cp deploy/matr-slack-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now matr-slack-bot
```

## 6. Verify

```bash
systemctl status matr-slack-bot
journalctl -u matr-slack-bot -f      # live logs — look for "Bolt app is running!"
```

You should see the three poller lines:

```
proof_alerts: polling order_proofs every 15s -> channel ...
order_alerts: polling job_tracking every 15s -> channel ...
submission_alerts: polling submissions every 15s -> channel ...
```

## Redeploying after a code change

```bash
cd /opt/matr-slack-bot
sudo -u slackbot git pull
sudo /opt/matr-slack-bot/.venv/bin/pip install -r requirements.txt   # only if deps changed
sudo systemctl restart matr-slack-bot
```
