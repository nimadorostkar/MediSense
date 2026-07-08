# MediSense — Production Deployment

Self-contained deployment. Runs on its own ports and does **not** depend on any
other web server on the host. Domain: **medisense.nimadorostkar.com**.

## Stack (`docker-compose.prod.yml`, project `medisense`)

| Service | Role | Host exposure |
|---|---|---|
| `web` (nginx) | serves the built React SPA + proxies `/api`,`/v2` → api | `8080` (HTTP), `8443` (HTTPS) |
| `api` (FastAPI/Gunicorn) | hybrid engine + demo diagnoser + Gemini chat | `127.0.0.1:8787` |
| `postgres` (pgvector) | knowledge base | internal only |
| `redis` | cache | internal only |

## First deploy

```bash
git clone https://github.com/nimadorostkar/MediSense.git ~/MediSense && cd ~/MediSense
# 1) secrets
cp backend/.env.example backend/.env      # set GEMINI_API_KEY, CORS_ORIGINS, etc.
# 2) build the frontend static bundle
cd frontend && npm ci && npm run build && cd ..
# 3) TLS cert for the origin (Let's Encrypt) → deploy/ssl/{fullchain,privkey}.pem
mkdir -p deploy/ssl deploy/acme
# 4) bring up
docker compose -f docker-compose.prod.yml up -d --build
curl -s http://localhost:8080/api/health
```

## Domain (Cloudflare-fronted)

`medisense.nimadorostkar.com` is proxied by Cloudflare (orange cloud) to the EC2
origin `13.58.63.117`. The origin serves HTTPS on **8443** with a valid Let's
Encrypt cert for the hostname. Point Cloudflare at it:

1. **SSL/TLS → Overview:** set mode to **Full (strict)**.
2. **Rules → Origin Rules → Create:** if hostname = `medisense.nimadorostkar.com`,
   **Rewrite origin port → 8443**.

Then `https://medisense.nimadorostkar.com` serves MediSense end-to-end encrypted.
(Alternative: origin port `8080` + SSL mode **Flexible** — no origin cert, but the
Cloudflare↔origin hop is unencrypted.)

## TLS certificate & renewal

Origin cert lives in `deploy/ssl/` (mounted into `web`). Obtained via Let's
Encrypt for `medisense.nimadorostkar.com`. Because port 80 on this host belongs
to another app, HTTP-01 renewal is not available here — renew via **DNS-01**
(Cloudflare API token) or replace with a **Cloudflare Origin CA** cert (15-year,
no renewal). A deploy hook (`/etc/letsencrypt/renewal-hooks/deploy/medisense.sh`)
copies a renewed cert into `deploy/ssl/` and reloads the `web` container.

## Notes

- `demoMode`: the deterministic dermatology engine grounds every diagnosis/dose.
- `aiChat` (Gemini): writes the conversational replies only; it never changes a
  diagnosis, dose, or safety flag. Free-tier quota → falls back to grounded text.
- Postgres/Redis are never published; the API is bound to localhost.
