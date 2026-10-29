"""Spike 5: does Sumopod report cached input tokens?

Reads the usage fields already recorded in agent-eval-harness's runs
(runs/*/inspect.eval and runs/*/trials.jsonl). Makes no model call.

Usage: python3 -I read_usage.py <path-to-agent-eval-harness> > results.md
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

# prices.yaml in the harness, checked 2026-10-23 (USD per million tokens).
PRICES = {
    "gpt-5-mini": {"input": 0.25, "cache_read": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cache_read": 0.005, "output": 0.40},
    "gemini-3.5-flash": {"input": 1.50, "cache_read": 0.15, "output": 9.00},
}


def price_for(model: str) -> dict[str, float] | None:
    for name, price in PRICES.items():
        if model.endswith(name):
            return price
    return None


def model_events(eval_path: Path):
    """Yield (model, raw provider usage or None, Inspect usage) per model call."""
    with zipfile.ZipFile(eval_path) as z:
        for name in z.namelist():
            if not name.startswith("samples/"):
                continue
            sample = json.loads(z.read(name))
            for ev in sample.get("events", []):
                if ev.get("event") != "model":
                    continue
                call = ev.get("call") or {}
                resp = call.get("response")
                raw = resp.get("usage") if isinstance(resp, dict) else None
                yield ev.get("model", ""), raw, (ev.get("output") or {}).get("usage") or {}


def main(harness: Path) -> None:
    rows = []
    for run in sorted((harness / "runs").iterdir()):
        eval_path = run / "inspect.eval"
        if not eval_path.exists():
            continue
        calls = with_raw = reported = 0
        prompt = cached = completion = 0
        model = ""
        for m, raw, usage in model_events(eval_path):
            model = m
            calls += 1
            if raw is None:
                # No raw response kept: fall back to Inspect's split, where
                # input_tokens excludes the cached part.
                prompt += (usage.get("input_tokens") or 0) + (usage.get("input_tokens_cache_read") or 0)
                cached += usage.get("input_tokens_cache_read") or 0
                completion += usage.get("output_tokens") or 0
                continue
            with_raw += 1
            details = raw.get("prompt_tokens_details") or {}
            if "cached_tokens" in details and details["cached_tokens"] is not None:
                reported += 1
            prompt += raw.get("prompt_tokens") or 0
            cached += details.get("cached_tokens") or 0
            completion += raw.get("completion_tokens") or 0
        if "sumopod" not in model:
            continue
        harness_cost = 0.0
        trials = run / "trials.jsonl"
        if trials.exists():
            for line in trials.read_text().splitlines():
                if line.strip():
                    harness_cost += json.loads(line).get("cost_usd") or 0.0
        price = price_for(model)
        assert price is not None, model
        true_cost = (
            (prompt - cached) * price["input"] + cached * price["cache_read"] + completion * price["output"]
        ) / 1e6
        no_cache_cost = (prompt * price["input"] + completion * price["output"]) / 1e6
        rows.append(
            (
                run.name,
                model.split("/")[-1],
                calls,
                with_raw,
                reported,
                prompt,
                cached,
                completion,
                harness_cost,
                true_cost,
                no_cache_cost,
            )
        )

    print(
        "| Run | Model | Calls | With raw usage | `cached_tokens` present | Prompt tokens | Cached "
        "| Cached share | Output | Harness cost | Cost with cache price | Cost if nothing cached |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    tot = [0] * 9
    for r in rows:
        name, model, calls, with_raw, reported, prompt, cached, completion, hc, tc, nc = r
        share = cached / prompt if prompt else 0.0
        print(
            f"| {name} | {model} | {calls} | {with_raw} | {reported} | {prompt:,} | {cached:,} | {share:.0%} "
            f"| {completion:,} | ${hc:.4f} | ${tc:.4f} | ${nc:.4f} |"
        )
        for i, v in enumerate((calls, with_raw, reported, prompt, cached, completion, hc, tc, nc)):
            tot[i] += v
    calls, with_raw, reported, prompt, cached, completion, hc, tc, nc = tot
    print(
        f"| **All** | | {calls} | {with_raw} | {reported} | {prompt:,} | {cached:,} | "
        f"{cached / prompt:.0%} | {completion:,} | ${hc:.4f} | ${tc:.4f} | ${nc:.4f} |"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
