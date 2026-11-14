[🇺🇸 English](integrations.md) · 🇧🇷 Português

# Integrações opcionais

Todas vêm desligadas até serem configuradas, e **nenhuma delas pode mudar o desfecho de um deploy**: uma falha vira uma linha no resumo (`betterstack:`, `cloudflare:`, `webhook:`). Os tokens ficam em arquivos só do root no servidor (`0600`), nunca na configuração JSON, e são mascarados em toda linha que o Deproi imprime ou registra.

## Better Stack

São dois recursos independentes. Configure um, outro ou os dois.

**Os monitores ganham uma folga durante a recriação.** Logo antes de os serviços serem recriados, cada monitor do Uptime listado ganha um período de confirmação maior, para que os poucos segundos de reinício não acordem ninguém. O valor original é salvo antes (`/var/lib/deproi/<name>/monitors.json`) e restaurado depois que o serviço fica saudável (ou depois da reversão). Se um deploy morre no meio, o próximo restaura. Monitores pausados não são tocados.

**Cada commit publicado vira uma release** no Better Stack Errors, registrada em segundo plano depois que a versão nova está no ar (com uma conferência antes, para que publicar de novo não a duplique).

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
BETTERSTACK_UPTIME_TOKEN=...   # token da API do Uptime (monitores)
BETTERSTACK_ERRORS_TOKEN=...   # token da API do Errors/Telemetry (releases)
```

Se o Better Stack não responde, a primeira falha de conexão desliga o cliente pelo resto do deploy. Assim, uma indisponibilidade custa um timeout, não um por chamada.

## Cloudflare

Depois de um deploy bem-sucedido, purga o cache dos hosts do ambiente (`POST /zones/<zone>/purge_cache` com `{"hosts": [...]}`). Só esses hosts: outros sites da mesma zona não são tocados.

```json
"integrations": {
  "cloudflare": {
    "credentials_file": "/etc/deproi/myapp-prod.cloudflare.env",
    "zone_id": "0123456789abcdef0123456789abcdef",
    "hosts": ["app.example.com"]
  }
}
```

Por padrão, `hosts` é o host da `url`.

```bash
# /etc/deproi/myapp-prod.cloudflare.env — root:root 0600
CLOUDFLARE_API_TOKEN=...   # um token só com Zone → Cache Purge, para esta zona
```

## Webhook

Uma mensagem ao fim de cada deploy, para o Slack, o Discord ou qualquer endpoint HTTPS que aceite JSON.

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

| `format` | Corpo |
|---|---|
| `slack` | `{"text": "✅ myapp-prod: …mensagem…"}` |
| `discord` | `{"content": "✅ myapp-prod: …mensagem…"}` |
| `json` (padrão) | `{"name", "situation", "commit", "previous", "step", "message", "url", "duration", "protected", "deproi_version"}` |

Por padrão, `events` é `["success", "failure"]`. A URL do webhook é tratada como segredo: só o host dela aparece numa linha de erro.

## Ganchos de pós-deploy

Não são uma integração, mas rodam no mesmo momento: os comandos de `hooks.post_deploy` rodam **em segundo plano** depois de um deploy bem-sucedido, com a imagem nova, sob uma trava própria. O job do GitHub não espera por eles. O resultado aparece na linha `post_deploy:` do **próximo** deploy e no syslog. Se uma versão mais nova entrou no ar nesse meio-tempo, eles são pulados (rodar código antigo contra a versão nova a desfaria).
