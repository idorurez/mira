# Gateway Setup for Pii-chan

Pii-chan runs as a **separate agent** on your existing OpenClaw gateway, with the Pi as a **node** providing local capabilities (voice, CAN bus).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Gateway                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Wintermute Agent  │  │     Pii-chan Agent          │   │
│  │   (main workspace)  │  │   (pii-chan-workspace)      │   │
│  │                     │  │                             │   │
│  │   SOUL.md           │  │   SOUL.md (car personality) │   │
│  │   MEMORY.md         │  │   MEMORY.md (drive history) │   │
│  │   Discord/etc       │  │   Voice from car node       │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                                    ▲                         │
│                                    │ WebSocket               │
└────────────────────────────────────┼─────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │    Pi 5 Node        │
                          │    (in car)         │
                          │                     │
                          │  - Microphone/TTS   │
                          │  - CAN bus tools    │
                          │  - Local fallback   │
                          └─────────────────────┘
```

---

## Docker Deployment (Recommended)

If you run OpenClaw via Docker Compose, follow these steps. Everything lives under `~/.openclaw/` which is already mounted — **survives restarts, rebuilds, and recompose**.

### Step 1: Create Pii-chan Workspace on Host

```bash
# On the gateway HOST (not inside container)
mkdir -p ~/.openclaw/pii-chan-workspace

# Clone repo and copy template files
git clone https://github.com/idorurez/pii-chan.git /tmp/pii-chan
cp /tmp/pii-chan/workspace-template/* ~/.openclaw/pii-chan-workspace/

# Verify
ls ~/.openclaw/pii-chan-workspace/
# Should show: AGENTS.md  HEARTBEAT.md  IDENTITY.md  MEMORY.md  SOUL.md  USER.md
```

### Step 2: Register Pii-chan Agent

```bash
# Run inside container (replace 'wintermute' with your container name if different)
# Note: Docker image uses node directly, not the openclaw CLI wrapper
docker exec -w /app wintermute node dist/index.js agents add pii-chan --workspace /home/node/.openclaw/pii-chan-workspace
```

**If you get permission errors:** Fix ownership on host:
```bash
sudo chown -R 1000:1000 ~/.openclaw/pii-chan-workspace/
```

This writes to `~/.openclaw/openclaw.json` on the host, so it persists.

### Step 3: Verify Agent Exists

```bash
docker exec -w /app wintermute node dist/index.js agents list
# Should show both: main (default) and pii-chan
```

### Step 4: Install Pii-chan Skill

```bash
# On host — copy skill to the config dir
cp -r /tmp/pii-chan/skills/car-control ~/.openclaw/skills/

# Clean up
rm -rf /tmp/pii-chan
```

---

## Native Deployment

If you run OpenClaw natively (not Docker):

### Step 1: Create Pii-chan Agent

```bash
openclaw agents add pii-chan --workspace ~/.openclaw/pii-chan-workspace
```

### Step 2: Set Up Workspace

```bash
git clone https://github.com/idorurez/pii-chan.git /tmp/pii-chan
cp /tmp/pii-chan/workspace-template/* ~/.openclaw/pii-chan-workspace/
cp -r /tmp/pii-chan/skills/car-control ~/.openclaw/skills/
rm -rf /tmp/pii-chan
```

---

## Pi Node Setup

On the Raspberry Pi:

```bash
# Install OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard

# Configure as node pointing to gateway
openclaw onboard --node

# When prompted:
# - Gateway URL: wss://your-gateway-ip:18789
# - Approve pairing request on gateway
```

### Approve on Gateway

```bash
# Docker
docker exec -w /app wintermute node dist/index.js nodes pending
docker exec -w /app wintermute node dist/index.js nodes approve <requestId>

# Native
openclaw nodes pending
openclaw nodes approve <requestId>
```

---

## Configure Node → Agent Routing

On the gateway, configure the Pi node to route to the pii-chan agent:

```bash
# Get node ID
docker exec -w /app wintermute node dist/index.js nodes status

# Configure routing (exact method TBD based on OpenClaw version)
# Option A: Per-node agent binding
docker exec -w /app wintermute node dist/index.js config set nodes.<node-id>.agent pii-chan
```

---

## Verification

```bash
# Docker commands (replace with just 'openclaw ...' for native installs)

# Check node is connected
docker exec -w /app wintermute node dist/index.js nodes status

# Check agents exist
docker exec -w /app wintermute node dist/index.js agents list

# Test node invocation
docker exec -w /app wintermute node dist/index.js nodes invoke --node piichan --command system.run --params '{"command":["echo","hello"]}'
```

---

## What's Persistent (Docker)

| Item | Location on Host | Survives Compose |
|------|------------------|------------------|
| Agent config | `~/.openclaw/openclaw.json` | ✅ Yes |
| Pii-chan workspace | `~/.openclaw/pii-chan-workspace/` | ✅ Yes |
| Pii-chan memories | `~/.openclaw/pii-chan-workspace/MEMORY.md` | ✅ Yes |
| Skills | `~/.openclaw/skills/` | ✅ Yes |
| Node pairing | `~/.openclaw/` (state files) | ✅ Yes |

**No changes to `docker-compose.yml` needed** — everything is under the already-mounted `${OPENCLAW_CONFIG_DIR}`.

---

## Separate Contexts

| Aspect | Wintermute | Pii-chan |
|--------|------------|----------|
| Workspace | `~/.openclaw/workspace/` | `~/.openclaw/pii-chan-workspace/` |
| Personality | Your main assistant | Car spirit |
| Memory | Discord, projects, life | Drives, car stuff |
| Channels | Discord, Signal, etc. | Voice from car node |
| Tools | All | Car-specific + basics |

They share the same gateway infrastructure but are completely isolated in personality, memory, and context.
