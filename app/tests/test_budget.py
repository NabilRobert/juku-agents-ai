"""B1 and B2: the budget guard stops at each cap, before the model call, and the two pools stay apart."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from juku_app.budget import BudgetGuard, BudgetRefusedError
from juku_common.rules import Rules
from juku_data.engine.models import Learner
from pydantic_ai.usage import RunUsage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def usage(input_tokens: int, output_tokens: int, requests: int = 1) -> RunUsage:
    return RunUsage(requests=requests, input_tokens=input_tokens, output_tokens=output_tokens)


async def spend(engine: AsyncEngine, pool: str, usd: str, learner_id: int | None = None, at: datetime = NOW) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.model_calls "
                "(called_at, pool, learner_id, requests, input_tokens, output_tokens, cost_usd) "
                "VALUES (:at, :pool, :learner, 1, 0, 0, :usd)"
            ),
            {"at": at, "pool": pool, "learner": learner_id, "usd": Decimal(usd)},
        )


@pytest.mark.guardrail("budget.input_usd_per_million")
@pytest.mark.guardrail("budget.output_usd_per_million")
def test_cost_comes_from_the_token_counts_and_the_price_table(clean_budget: AsyncEngine, rules: Rules) -> None:
    guard = BudgetGuard(clean_budget, rules)
    # 12,000 in at $0.25/M and 1,100 out at $2.00/M: the cost model's one chat question, $0.0052.
    assert guard.cost_of(usage(12_000, 1_100)) == Decimal("0.005200")


async def test_a_call_is_recorded_with_its_cost(clean_budget: AsyncEngine, rules: Rules, learner: Learner) -> None:
    guard = BudgetGuard(clean_budget, rules)
    cost = await guard.record("chat", learner.id, usage(12_000, 1_100))
    async with clean_budget.connect() as connection:
        recorded = await connection.scalar(text("SELECT sum(cost_usd) FROM app.model_calls WHERE pool = 'chat'"))
    assert recorded == cost == Decimal("0.005200")


@pytest.mark.guardrail("budget.chat_pool_usd")
async def test_chat_stops_when_its_pool_is_spent(clean_budget: AsyncEngine, rules: Rules, learner: Learner) -> None:
    guard = BudgetGuard(clean_budget, rules)
    await spend(clean_budget, "chat", str(rules.budget.chat_pool_usd), at=NOW - timedelta(days=3))
    with pytest.raises(BudgetRefusedError) as refused:
        await guard.check("chat", learner.id, NOW)
    assert refused.value.reason == "chat_pool_spent"


@pytest.mark.guardrail("budget.reports_pool_usd")
async def test_reports_are_reserved_so_chat_spending_never_stops_them(clean_budget: AsyncEngine, rules: Rules) -> None:
    guard = BudgetGuard(clean_budget, rules)
    await spend(clean_budget, "chat", str(rules.budget.chat_pool_usd), at=NOW - timedelta(days=3))
    await guard.check("reports", None, NOW)
    await spend(clean_budget, "reports", str(rules.budget.reports_pool_usd), at=NOW - timedelta(days=3))
    with pytest.raises(BudgetRefusedError) as refused:
        await guard.check("reports", None, NOW)
    assert refused.value.reason == "reports_pool_spent"


@pytest.mark.guardrail("budget.chat_daily_global_usd")
async def test_chat_stops_for_the_day_at_the_global_daily_cap(
    clean_budget: AsyncEngine, rules: Rules, learner: Learner
) -> None:
    guard = BudgetGuard(clean_budget, rules)
    await spend(clean_budget, "chat", str(rules.budget.chat_daily_global_usd), at=NOW - timedelta(hours=1))
    with pytest.raises(BudgetRefusedError) as refused:
        await guard.check("chat", learner.id, NOW)
    assert refused.value.reason == "chat_daily_global"
    await guard.check("chat", learner.id, NOW + timedelta(days=1))  # a new day


@pytest.mark.guardrail("budget.chat_daily_questions_per_learner")
async def test_a_learner_stops_at_their_daily_question_cap(
    clean_budget: AsyncEngine, rules: Rules, learner: Learner
) -> None:
    guard = BudgetGuard(clean_budget, rules)
    for _ in range(rules.budget.chat_daily_questions_per_learner):
        await guard.check("chat", learner.id, NOW)
        await spend(clean_budget, "chat", "0.000001", learner.id, at=NOW - timedelta(minutes=5))
    with pytest.raises(BudgetRefusedError) as refused:
        await guard.check("chat", learner.id, NOW)
    assert refused.value.reason == "learner_daily_questions"


@pytest.mark.guardrail("budget.chat_daily_questions_per_learner")
async def test_the_learners_day_is_their_own(clean_budget: AsyncEngine, rules: Rules, learner: Learner) -> None:
    """20 questions at 06:00 in Jakarta (23:00 UTC the day before), then 08:00 there: the same day for them."""
    guard = BudgetGuard(clean_budget, rules)
    tuesday_6am_wib = datetime(2026, 11, 9, 23, 0, tzinfo=UTC)
    for _ in range(rules.budget.chat_daily_questions_per_learner):
        await spend(clean_budget, "chat", "0.000001", learner.id, at=tuesday_6am_wib)
    with pytest.raises(BudgetRefusedError) as refused:
        await guard.check("chat", learner.id, datetime(2026, 11, 10, 1, 0, tzinfo=UTC))
    assert refused.value.reason == "learner_daily_questions"


@pytest.mark.guardrail("budget.chat_run_request_limit")
@pytest.mark.guardrail("budget.chat_run_total_tokens_limit")
@pytest.mark.guardrail("budget.report_run_request_limit")
@pytest.mark.guardrail("budget.report_run_total_tokens_limit")
def test_each_run_is_capped_by_pydantic_ais_usage_limits(clean_budget: AsyncEngine, rules: Rules) -> None:
    guard = BudgetGuard(clean_budget, rules)
    chat, report = guard.run_limits("chat"), guard.run_limits("reports")
    assert (chat.request_limit, chat.total_tokens_limit) == (6, 20000)
    assert (report.request_limit, report.total_tokens_limit) == (8, 40000)


@pytest.mark.guardrail("budget.alert_fractions")
async def test_pool_sizes_reach_grafana_and_its_alerts_use_the_rule_files_fractions(
    clean_budget: AsyncEngine, rules: Rules
) -> None:
    import yaml
    from juku_testkit.databases import repo_root

    await BudgetGuard(clean_budget, rules).sync_pool_sizes()
    async with clean_budget.connect() as connection:
        sizes = dict((await connection.execute(text("SELECT pool, size_usd FROM app.budget_pools"))).all())
    assert sizes == {"chat": Decimal("1.200000"), "reports": Decimal("0.900000")}
    alerting = yaml.safe_load((repo_root() / "ops/grafana/provisioning/alerting/rules.yaml").read_text())
    thresholds = sorted(
        step["model"]["conditions"][0]["evaluator"]["params"][0]
        for group in alerting["groups"]
        for rule in group["rules"]
        if rule["uid"].startswith("juku-budget-")
        for step in rule["data"]
        if step["refId"] == "C"
    )
    assert thresholds == sorted(rules.budget.alert_fractions)
