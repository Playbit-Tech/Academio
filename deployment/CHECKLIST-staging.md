# Academio — Staging Deployment Checklist

Target: single VPS, native systemd services (no Docker), GitHub Actions CD.
Staging mirrors production topology at reduced strictness.

## 1. Infrastructure

- [ ] VPS provisioned (Ubuntu 24.04), SSH key-only login confirmed
- [ ] `uname -m` checked — note arch for CI build (`amd64` vs `arm64`)
- [ ] DNS (Cloudflare): staging subdomains created, e.g.
      `api-academio-stg.playbit.org` → A → VPS IP
      `ai-academio-stg.playbit.org` → A → VPS IP
- [ ] Cloudflare API token exists (Zone:DNS:Edit on playbit.org) for certbot DNS-01
- [ ] `/root/.secrets/cloudflare.ini` placed with token, chmod 600

## 2. Bootstrap

- [ ] Parent repo cloned to a working dir on the VPS
- [ ] `sudo CERT_EMAIL=... deployment/scripts/bootstrap-vps.sh` completed:
      - [ ] nginx, certbot, postgresql-16 + pgvector, redis, tesseract, poppler installed
      - [ ] `academio` system user created
      - [ ] uv installed (`uv --version` works)
      - [ ] DB role/database created, `vector` extension enabled
      - [ ] Redis bound to 127.0.0.1
      - [ ] Gotenberg installed and active (`systemctl status gotenberg`)
      - [ ] LE certs issued for BOTH staging domains
      - [ ] nginx vhosts live (`nginx -t` clean, HTTPS responds)
- [ ] `.env` files scaffolded — review both:
      - `/var/www/academio/.env`
      - `/opt/academio-ai/.env`

## 3. Staging-specific configuration

- [ ] `APP_ENV=staging` in api `.env` (not `production`) if supported; else keep `production` but with staging secrets
- [ ] **Separate secrets from prod**: JWT_SECRET, ENCRYPTION_KEY, APP_SECRET, DB_PASSWORD, AI_ENGINE_TOKEN all distinct
- [ ] AI provider keys: use test/low-limit keys where possible
- [ ] Seed/demo data allowed — staging may run `make seed-demo` equivalents
- [ ] Log level may stay `debug` for troubleshooting

## 4. First deploy

- [ ] Backend workflow (Academio-be repo) run against staging environment — or manual package + `deploy-api.sh`
- [ ] AI engine workflow run — or manual rsync + `deploy-ai-engine.sh`
- [ ] `systemctl status academio academio-ai gotenberg` all active
- [ ] Migrations applied on boot (check `journalctl -u academio | grep -i migrat`)

## 5. Smoke tests

- [ ] `curl https://<stg-api-domain>/health` → 200
- [ ] `curl https://<stg-ai-domain>/health` → 200
- [ ] Login flow works (super admin)
- [ ] Create school → tenant schema provisioned
- [ ] PDF generation path (Gotenberg) exercised once
- [ ] One AI roundtrip (chat or embedding) succeeds end-to-end

## 6. Rollback drill (do once)

- [ ] Redeploy previous backend binary from `/var/www/academio/.old/server`
- [ ] `deploy-ai-engine.sh` rollback path verified (`previous` symlink swap)

## 7. Handoff to production

- [ ] All staging smoke tests green for 48h
- [ ] Proceed to `CHECKLIST-production.md`
