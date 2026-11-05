# Running Juku

Two ways, for Arthur: on his own Mac (local-use mode, in use since
2026-11-05), and on the server (slice 8, not yet done). Both run the same
compose stack (`ops/compose.yaml`). The laptop rehearsal (`ops/rehearse.sh`,
in the guide) is a third, throwaway way: it deletes everything on `down`.

## Local use on Arthur's Mac

One command does everything, from the repository: `ops/local/juku.sh`. It runs
`ops/compose.yaml` with `ops/rehearsal/compose.yaml` (a local Postgres with TLS,
and the gateway) and `ops/local/use.yaml` (the real model, and the learners'
database on a protected volume).

| Command | What it does |
|---|---|
| `ops/local/juku.sh start` | Starts the stack; the first time, creates the database volume |
| `ops/local/juku.sh stop` | Stops it. Nothing is deleted |
| `ops/local/juku.sh status` | Each service and its health |
| `ops/local/juku.sh backup` | An encrypted dump of the learners' database |
| `ops/local/juku.sh restore-check` | Restores the latest backup into a scratch database, compares it, drops it |
| `ops/local/juku.sh nightly` | `backup`, then `restore-check` |
| `ops/local/juku.sh install-nightly` | Runs `nightly` every night at 03:00 (see below) |
| `ops/local/juku.sh compose ...` | Any other compose command, with the right files |

The app is at http://127.0.0.1:58080 and Grafana at http://127.0.0.1:53000.

**Never** run `ops/rehearse.sh` on this stack: its `up` re-runs the database
set-up and empties the model key, and its `down` deletes volumes. There is no
`down` in `juku.sh` on purpose. As a guard, the live secrets carry no
`REHEARSAL` marker, so `rehearse.sh up` refuses them; and the learners'
volume isn't one a `down` can delete.

### Where the data is

- **Learners' database:** the Docker volume `juku-local-pgdata`. It's
  `external` in `use.yaml`, so compose never deletes it, whatever command it
  runs. (Until 2026-11-05 it was an anonymous volume, which a recreated
  container would have left behind: the move is in that day's commit.)
- **Backups:** `~/Backups/juku/app-<date>.dump.age`, readable only by Arthur,
  the last 14 days kept. Encrypted with `age` to Juku's own key.
- **The key:** `~/Documents/JUKU-KEYS/juku-backup-age-key.txt` (private,
  never printed) and `.pub`. Without it the backups can't be read: copy it
  somewhere safe that isn't this Mac.
- **Secrets:** `~/.juku/secrets/`, readable only by Arthur, made by
  `ops/make-secrets.sh` through the rehearsal. `ops/secrets` is a link to it,
  so compose finds them while they stay out of the repository (and out of
  `make check`'s secret scan, which doesn't follow links), and a removed
  checkout doesn't take them along. The real model key is
  `juku_model_api_key` there.

### The nightly backup

`ops/local/juku.sh install-nightly` installs a LaunchAgent
(`~/Library/LaunchAgents/com.juku.nightly-backup.plist`, from
`ops/local/nightly-backup.plist`) that runs `nightly` at 03:00. launchd runs a
missed night when the Mac wakes. Its log is `~/Backups/juku/nightly.log`; a
failed restore check ends it with an error there. Arthur installs it himself,
since it's a standing job on his Mac. To remove it:

```bash
launchctl bootout gui/$(id -u)/com.juku.nightly-backup && rm ~/Library/LaunchAgents/com.juku.nightly-backup.plist
```

### Restoring for real

Only after losing the database; this replaces it. Stop the app first, so
nothing writes during the restore:

```bash
ops/local/juku.sh compose stop app juku-mcp
age -d -i ~/Documents/JUKU-KEYS/juku-backup-age-key.txt ~/Backups/juku/app-<date>.dump.age \
  | docker exec -i "$(ops/local/juku.sh compose ps -q db)" pg_restore -U postgres -d app --clean --if-exists --no-owner
ops/local/juku.sh start
```

`restore-check` runs the same restore into a scratch database every night, so
this path is tested.

### Updating the app

After a branch merges, or to try one before it does: build the image from that
checkout, then recreate only the app.

```bash
docker build -f app/Dockerfile -t juku-app:local .
ops/local/juku.sh compose up -d --no-deps --no-build --force-recreate --wait app
```

If the dictionary changed (a new table, a new breakdown), reload it too:

```bash
ops/local/juku.sh compose run --rm --no-deps -T app juku-data load-dictionary
ops/local/juku.sh compose run --rm --no-deps -T app juku-data sync-index
```

## The server (slice 8: not yet done)

The steps for Arthur, in order. Rehearse first with `ops/rehearse.sh`: the
same stack, on a local database, at $0. Juku is private (ADR-029): only the
sign-in page and a signed-in learner's pages are reachable, behind the
server's existing proxy.

### Before you start

All of these must hold. If one doesn't, stop: there's no partial deploy.

| # | What | Why |
|---|---|---|
| 1 | The server's backup fix is done | The standing rule: no deploy until then |
| 2 | The managed Postgres 16 exists, and you have its admin login | ADR-016: the database lives outside the server |
| 3 | A subdomain for the app and one for Grafana, pointed at the server | Slice plan P4 |
| 4 | The gateway is deployed from its own repository, with Juku's entries | `ops/gateway/juku-routes.example.yaml`; its deployment makes the two Docker networks Juku joins |
| 5 | A capped Sumopod key for Juku | Slice plan P3 |
| 6 | A Telegram bot token, and your chat ID | Alerts (ADR-009) |
| 7 | Docker with Compose, and `uv`, on the server | `uv` runs the dictionary download |

### The steps

All commands run from the repository on the server, `/srv/juku` (the path
`ops/crontab` expects).

1. **Get the code.** Clone the repository to `/srv/juku` at the merged `main`.
2. **Settings.** `cp ops/.env.example ops/.env`, then fill it in: the
   database's host and port, the Telegram chat ID, the Grafana address, the
   gateway's networks and audit folder, and the crisis line (check the number
   on an official source first).
3. **Secrets.** `ops/make-secrets.sh`. It makes every password, the database
   URLs, the signing keys and the session secret, and lists the four it can't
   make. Put those in `ops/secrets/` by hand, one value per file:
   `telegram_bot_token`, `juku_shiori_gateway_key`, `juku_keiko_gateway_key`
   (both from the gateway's deployment) and `juku_model_api_key`.
4. **Database.** `PGHOST=<the provider's host> PGUSER=<the admin login>
   ops/db/setup.sh`. It asks for the admin password; it never takes it on the
   command line.
5. **Images.** `docker compose -f ops/compose.yaml build`.
6. **Migrations.** As the migrator role:
   ```bash
   docker compose -f ops/compose.yaml run --rm --no-deps app \
     sh -c 'JUKU_MIGRATOR_DATABASE_URL="$(cat /run/secrets/juku_migrator_database_url)" alembic upgrade heads'
   ```
7. **Dictionary.** `uv run juku-data fetch-dictionary` downloads the pinned
   OpenJLPT files and checks them. Then:
   ```bash
   docker compose -f ops/compose.yaml run --rm --no-deps app juku-data load-dictionary
   docker compose -f ops/compose.yaml run --rm --no-deps app juku-data sync-index
   ```
8. **Start it.** `docker compose -f ops/compose.yaml up -d --wait`.
9. **The schedule.** `crontab ops/crontab`. From then on, no crontab means no
   runs, and the alerts notice.
10. **The proxy.** Forward the app's subdomain to `127.0.0.1:8080` and
    Grafana's to `127.0.0.1:3000` (the ports in `ops/.env`).
11. **You, as owner.** Each owner command runs in its own container
    (`run --rm`), never with `exec` in the app's: the `juku` command loads the
    whole app, and two in one 256 MB container are killed (the rehearsal found
    this). Issue a code, sign up with it in the browser, then find your public
    ID and make yourself owner:
    ```bash
    docker compose -f ops/compose.yaml run --rm --no-deps -T app juku invite --count 1
    docker compose -f ops/compose.yaml run --rm --no-deps -T app juku learners
    docker compose -f ops/compose.yaml run --rm --no-deps -T app juku set-role <your public id> owner
    ```
    From then on, the owner page (`/admin/learners`) issues codes.

### Backups on the server

The managed database's provider keeps encrypted backups for 7 days (the
consent notice says so). Before inviting anyone, restore one of them into a
scratch database once, the same check as `restore-check` above, and write down
how long it took.

### Checks after the deploy

- `curl -fsS https://<the app's subdomain>/healthz` answers.
- Grafana's data source is green, and the alert rules are listed.
- **Alert delivery:** stop the crontab for six minutes. "Heartbeat stale"
  should reach Telegram, then resolve when it's back.
- **The gateway:** the rehearsal's check, from the server
  (`ops/rehearse.sh`'s `check_the_gateway`): 401 without a key, 200 with
  Shiori's.
- **A weekly run on demand:** after Sunday 18:00 in your timezone,
  `docker compose -f ops/compose.yaml run --rm --no-deps -T app juku run-weekly --due`.
