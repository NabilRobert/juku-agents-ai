# Spike 3: does Grafana fit?

**Fail: Grafana OSS 13.2.4 idles at a median of 217 MiB with no cap, and
runs at 244–251 MiB inside a 256 MB cap.** That's not "well under 256 MB",
so by ADR-009's own rule the fallback applies: cron alerts.

```
./measure.sh 2g 300   > results-uncapped.txt
./measure.sh 256m 300 > results-256m.txt
GOMEMLIMIT=150MiB ./measure.sh 256m 300 > results-256m-gomemlimit150.txt
```

What runs (`compose.yaml`):
- `grafana/grafana:13.2.4` (the OSS edition; `grafana-oss` stopped
  updating in June 2026), with a provisioned Postgres data source
  (`provisioning/datasources/`) on a read-only role, and one provisioned
  dashboard of two panels (`dashboards/tool-health.json`);
- `postgres:16`, with a stand-in `monitoring.tool_calls` table of 20,000
  rows (`init.sql`);
- an internal Docker network, so nothing can reach the internet. Plugin
  preinstall, update checks, analytics and the news feed are off. The admin
  password is generated per run and never printed.

`measure.sh` checks that the data source is healthy and the dashboard is
provisioned, waits 60 s, then samples memory every 10 s:
- 5 minutes idle;
- 1 minute after loading the dashboard's queries 20 times (both panels
  return rows);
- 2 more minutes idle.

"stats" is `docker stats` (cgroup usage less inactive page cache), and
"anon" is the cgroup's anonymous memory, Grafana's own heap and stacks.

## Numbers (MiB: median / max)

| Run | Idle | After the dashboard | Idle again | OOM kills |
|---|---|---|---|---|
| No cap (2 GB) | 217 / 249 (anon 207 / 239) | 216 / 216 | 235 / 244 | 0 |
| 256 MB cap | 244 / 249 (anon 218 / 237) | 250 / 250 | 250 / 251 | 0 |
| 256 MB cap, `GOMEMLIMIT=150MiB` | 232 / 242 (anon 221 / 232) | 242 / 242 | 242 / 243 | 0 |

- Inside the cap it never crashed, but it sat 5–12 MiB under the limit,
  with no room for a burst of dashboard use or alert evaluation.
- `GOMEMLIMIT` (a soft heap target for Go's garbage collector) didn't
  help. Grafana's live heap alone is above 200 MiB, so there's nothing left
  for the collector to trim. Grafana 13 starts many services at boot
  (unified storage, alerting, search, plugins) whether they're used or not.

## What it changes in the plan

**Proposed (ADR-009 and settled decision 3 already say this):** monitoring
becomes **cron alerts** with no Grafana. Concretely:
- the same `monitoring` schema and evidence SQL;
- a cron job that runs the alert queries (heartbeat, missed runs, budget,
  error rates, detector flags, audit chain, cross-learner refusals) and
  sends to the Telegram bot;
- Arthur reads the dashboards' numbers from the Run Inspector page, or
  with psql.

That frees about 250 MB on the shared server.

The alternative, raising Grafana's cap to about 384 MB, is a server-budget
decision for Arthur. It isn't the recommendation: the rule was set before
the measurement, and the cron path needs no new service.
