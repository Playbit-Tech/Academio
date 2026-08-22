# Academio — Production Deployment Checklist

Target: single VPS (`my-vps`), native systemd services (no Docker),
nginx TLS passthrough, GitHub Actions CD.
Complete `CHECKLIST-staging.md` first.

## 1. Infrastructure & access

- [ ] VPS sized for load (min 2 vCPU / 4GB for API + AI engine + PG + Redis + Gotenberg)
- [ ] SSH: key-only, password auth disabled (`PasswordAuthentication no`)
- [ ] Deploy user in sudoers with scoped commands (see PlayCMS SUDOERS.md pattern)
- [ ] Unattended security upgrades enabled
- [ ] DNS (Cloudflare): production subdomains → A → VPS
      - [ ] `api-academio.playbit.org`
      - [ ] `ai-academio.playbit.org`
- [ ] Decide Cloudflare SSL mode: **Full (strict)** — origin serves the LE cert

## 2. Secrets & configuration

- [ ] All secrets generated fresh — NONE shared with staging or dev:
      JWT_SECRET, ENCRYPTION_KEY, APP_SECRET, DB_PASSWORD, AI_ENGINE_TOKEN
- [ ] `.env` files chmod 600, owned root; backed up to password manager/vault
- [ ] AI provider keys set with **production rate limits/billing caps**
- [ ] Email/SMS credentials (SES etc.) configured and verified
- [ ] CORS/allowed origins locked to real frontend domains
- [ ] `LOG_LEVEL=info`

## 3. Bootstrap (production run)

- [ ] `bootstrap-vps.sh` executed against prod domains — all staging bootstrap boxes ticked here too
- [ ] Certificates issued for both prod domains; auto-renew timer active (`systemctl list-timers | grep certbot`)
- [ ] TLS grade A- or better (test with an SSL checker after go-live)
- [ ] ufw active: only 22/80/443; verify 5432/6379/3000/8000/8080 NOT reachable externally

## 4. Database safety

- [ ] Automated backups: nightly `pg_dump academio` → offsite (S3/R2), retention ≥ 7 days
- [ ] Restore drill performed once on staging from a prod backup
- [ ] Migrations auto-run on boot confirmed working (watch first prod deploy logs)
- [ ] Redis appendonly persistence on (set by bootstrap)

## 5. CI/CD (GitHub Actions)

- [ ] Backend repo secrets: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `VPS_SSH_KEY`, `SSH_PASSPHRASE` (if key has one) — deploy scripts ship inside each repo (`deployment/`), no cross-repo token needed
- [ ] AI engine repo secrets: same set (`VPS_*`, `SSH_PASSPHRASE`)
- [ ] GitHub **environment: production** created with required reviewers
- [ ] Concurrency group `deploy-prod`, `cancel-in-progress: false`
- [ ] Build arch matches VPS (`uname -m`) — amd64 vs arm64
- [ ] First CI deploy executed and green end-to-end

## 6. Security verification

- [ ] Services run as dedicated users (`academio`, `gotenberg`) — not root
- [ ] systemd hardening active (`systemd show academio | grep -i protect`)
- [ ] `ss -tlnp`: only nginx on 0.0.0.0; everything else loopback
- [ ] Audit logging enabled in app (Rule B11) — mutation writes audit rows
- [ ] Rate limits live in nginx vhosts (api 20r/s, ai 10r/s)

## 7. Go-live operations

- [ ] **Rotate seeded super admin** — default `playbit / Password123!` MUST be changed
- [ ] Create real admin accounts; enable 2FA if available
- [ ] First real school provisioned end-to-end (admission → student → fees)
- [ ] External uptime monitor on both `/health` endpoints
- [ ] Log review scheduled (journalctl units: academio, academio-ai, gotenberg, nginx)

## 8. Rollback readiness

- [ ] Backend rollback path known: `/var/www/academio/.old/server` swap + restart
- [ ] AI rollback path known: `/opt/academio-ai/previous` symlink swap + restart
- [ ] DB restore procedure documented with exact commands
- [ ] On-call owner named for launch week
