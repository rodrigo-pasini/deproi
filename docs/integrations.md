🇺🇸 English · [🇧🇷 Português](integrations.pt-BR.md)

# Optional integrations

All of them are off unless configured, and **none of them can change the outcome of a deploy**: a failure becomes a line in the summary (`betterstack:`, `cloudflare:`, `webhook:`). Tokens live in root-only files on the server (`0600`), never in the JSON config, and are redacted from every line Deproi prints or logs.

## Better Stack

Two independent features. Configure either or both.

**Monitors get a grace period during recreation.** Right before the services are recreated, each listed Uptime monitor gets a longer confirmation period, so the few seconds of restart do not page anyone. The original value is saved first (`/var/lib/deproi/<name>/monitors.json`) and restored after health (or rollback). If a deploy dies halfway, the next one restores it. Paused monitors are not touched.

**Each deployed commit becomes a release** in Better Stack Errors, registered in the background after the new version is live (checked first, so republishing does not duplicate it).

```json
"integrations": {
  "betterstack": {
    "credentials_file": "/etc/deproi/myapp-prod.betterstack.env",
    "monitors": ["123456", "123457"],
    "grace_period": 1200,
    "errors": { "application_id": "98765", "environment": "production" }
  }
}
```

```bash
# /etc/deproi/myapp-prod.betterstack.env — root:root 0600
BETTERSTACK_UPTIME_TOKEN=...   # Uptime API token (monitors)
BETTERSTACK_ERRORS_TOKEN=...   # Errors/Telemetry API token (releases)
```

If Better Stack does not answer, the first connection failure switches the client off for the rest of the deploy, so an outage costs one timeout, not one per call.

## Cloudflare

After a successful deploy, purges the cache of the environment's hosts (`POST /zones/<zone>/purge_cache` with `{"hosts": [...]}`). Only those hosts: other sites in the same zone are untouched.

```json
"integrations": {
  "cloudflare": {
    "credentials_file": "/etc/deproi/myapp-prod.cloudflare.env",
    "zone_id": "0123456789abcdef0123456789abcdef",
    "hosts": ["app.example.com"]
  }
}
```

`hosts` defaults to the host of `url`.

```bash
# /etc/deproi/myapp-prod.cloudflare.env — root:root 0600
CLOUDFLARE_API_TOKEN=...   # a token with only Zone → Cache Purge, for this zone
```

## Webhook

One message at the end of each deploy, to Slack, Discord or any HTTPS endpoint that accepts JSON.

```json
"integrations": {
  "webhook": {
    "url_file": "/etc/deproi/myapp-prod.webhook.env",
    "format": "slack",
    "events": ["failure"]
  }
}
```

```bash
# /etc/deproi/myapp-prod.webhook.env — root:root 0600
WEBHOOK_URL=https://hooks.slack.com/services/...
```

| `format` | Body |
|---|---|
| `slack` | `{"text": "✅ myapp-prod: …message…"}` |
| `discord` | `{"content": "✅ myapp-prod: …message…"}` |
| `json` (default) | `{"name", "situation", "commit", "previous", "step", "message", "url", "duration", "protected", "deproi_version"}` |

`events` is `["success", "failure"]` by default. The webhook URL is treated as a secret: only its host ever appears in an error line.

## Post-deploy hooks

Not an integration, but they run at the same moment: `hooks.post_deploy` commands run **in the background** after a successful deploy, with the new image, under their own lock. The GitHub job does not wait for them. Their result appears in the **next** deploy's `post_deploy:` line and in syslog. If a newer version went live in the meantime, they are skipped (running old code against the new version would undo it).
