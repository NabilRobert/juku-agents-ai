"""FF12's numbers are guardrails.yaml's: the Lighthouse assertions and the build's budget script use them."""

import json
import re
from pathlib import Path

import pytest
from juku_app.previews import PAGES, render_previews
from juku_common.rules import Rules

WEB = Path(__file__).resolve().parents[1] / "web"
# One lab run is noise: CI's first measured 340 ms of blocking time on beranda, a page with 2 KB of JavaScript.
LIGHTHOUSE_RUNS = 3


@pytest.mark.fitness("FF12")
def test_lighthouse_asserts_the_rule_files_budget(rules: Rules) -> None:
    assertions = json.loads((WEB / "lighthouserc.json").read_text())["ci"]["assert"]["assertions"]

    def limit(name: str) -> float:
        return float(assertions[name][1]["maxNumericValue"])

    assert limit("resource-summary:script:size") == rules.threshold("FF12", "javascript_kb") * 1024
    assert limit("resource-summary:stylesheet:size") == rules.threshold("FF12", "css_kb") * 1024
    assert limit("largest-contentful-paint") == rules.threshold("FF12", "largest_contentful_paint_ms")
    assert limit("total-blocking-time") == rules.threshold("FF12", "total_blocking_time_ms")
    assert limit("cumulative-layout-shift") == rules.threshold("FF12", "cumulative_layout_shift")


@pytest.mark.fitness("FF12")
def test_lighthouse_judges_each_page_by_the_median_of_three_runs() -> None:
    config = json.loads((WEB / "lighthouserc.json").read_text())["ci"]
    assert config["collect"]["numberOfRuns"] == LIGHTHOUSE_RUNS
    # lhci's default, "optimistic", would keep the best run and hide a slow page; the median hides one outlier only.
    methods = {name: options[1].get("aggregationMethod") for name, options in config["assert"]["assertions"].items()}
    assert methods == dict.fromkeys(methods, "median")


@pytest.mark.fitness("FF12")
def test_the_build_budget_script_uses_the_same_limits(rules: Rules) -> None:
    script = (WEB / "scripts" / "check-budget.mjs").read_text()
    javascript = re.search(r"JS_BUDGET = (\d+) \* 1024", script)
    css = re.search(r"CSS_BUDGET = (\d+) \* 1024", script)
    assert javascript and css
    assert float(javascript.group(1)) == rules.threshold("FF12", "javascript_kb")
    assert float(css.group(1)) == rules.threshold("FF12", "css_kb")


def test_every_preview_page_renders(tmp_path: Path) -> None:
    written = render_previews(tmp_path)
    assert [path.stem for path in written] == list(PAGES)
    assert all('<html lang="id">' in path.read_text() for path in written)
