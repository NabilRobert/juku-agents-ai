# Spike 5: does Sumopod report cached input tokens?

**Answer: yes.** Every raw Sumopod response the harness kept has
`usage.prompt_tokens_details.cached_tokens`, in the OpenAI format. No new
calls were made: this reads the existing logs only.

```
python3 -I read_usage.py ~/Desktop/my-kerjaan-aku/agent-eval-harness > results.md
```

[results.md](5-cached-tokens/results/results.md) has the table, per run. Across all 20 Sumopod runs:
- 7,068 model calls. 6,792 kept their raw response, and **all 6,792 carry
  `cached_tokens`**. The other 276 have only Inspect's parsed usage, which
  splits out `input_tokens_cache_read` too;
- 9.68 M prompt tokens, **3.06 M of them cached (32%)**. Caching is
  automatic: no request asked for it;
- the share depends on the task's shape: 45–61% on the filesystem suites
  (long, repeated prefixes), 6–14% on the Pagila "proof" runs.

**A side finding about the harness.** Its `input_tokens` comes from
Inspect, where it *excludes* the cached part. So its cost figure leaves the
cached tokens out entirely. The note in its report and `prices.yaml` says
the figure "errs high"; it errs **low**, by cached × $0.025/M. That's small:
$4.4547 recorded against $4.5206 at the cache price (−1.5%), and $0.5343
against $0.5368 for the 200-task Pagila run behind Juku's measured basis.
It's for the harness repo to fix, not here.

What the logs can't show: whether Sumopod *bills* cached tokens at the
$0.025/M in its price table. That needs the account's billing page, which
is Arthur's.
