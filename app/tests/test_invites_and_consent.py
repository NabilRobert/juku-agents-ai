"""ADR-013 invite codes and the versioned consent (Phase 2, privacy)."""

import pytest
from juku_app.consent import CONSENT_VERSION, ConsentAnswers, ConsentRefusedError, has_current_consent, record_consent
from juku_app.invites import InviteRefusedError, attach, issue_codes, redeem
from juku_data.engine.models import Learner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: invites and consent land in the next commit")

YES = ConsentAnswers(is_adult=True, accepts_service=True, accepts_aggregates=True, accepts_group_digest=False)


async def test_only_a_hash_of_each_code_is_stored(app_engine: AsyncEngine) -> None:
    codes = await issue_codes(app_engine, 3)
    assert len(set(codes)) == 3
    async with app_engine.connect() as connection:
        stored = " ".join(str(row) for row in (await connection.execute(text("SELECT * FROM app.invite_codes"))).all())
    for code in codes:
        assert code.split(".")[1] not in stored


async def test_a_code_redeems_and_a_wrong_one_does_not(app_engine: AsyncEngine) -> None:
    code = (await issue_codes(app_engine, 1))[0]
    invite = await redeem(app_engine, code)
    assert invite.learner_id is None
    with pytest.raises(InviteRefusedError):
        await redeem(app_engine, code[:-1] + ("A" if code[-1] != "A" else "B"))
    with pytest.raises(InviteRefusedError):
        await redeem(app_engine, "no-such-code")


async def test_a_used_code_logs_its_learner_back_in(app_engine: AsyncEngine, learner: Learner) -> None:
    code = (await issue_codes(app_engine, 1))[0]
    await attach(app_engine, await redeem(app_engine, code), learner.id)
    assert (await redeem(app_engine, code)).learner_id == learner.id


async def test_a_learner_without_consent_has_none(app_engine: AsyncEngine, learner: Learner) -> None:
    assert not await has_current_consent(app_engine, learner.id)
    await record_consent(app_engine, learner.id, YES)
    assert await has_current_consent(app_engine, learner.id)


async def test_a_new_consent_version_asks_again(app_engine: AsyncEngine, learner: Learner) -> None:
    await record_consent(app_engine, learner.id, YES)
    assert not await has_current_consent(app_engine, learner.id, version=CONSENT_VERSION + "-next")


@pytest.mark.parametrize(
    "answers",
    [
        ConsentAnswers(is_adult=False, accepts_service=True, accepts_aggregates=True, accepts_group_digest=False),
        ConsentAnswers(is_adult=True, accepts_service=False, accepts_aggregates=True, accepts_group_digest=False),
    ],
    ids=["under-18", "service-refused"],
)
async def test_consent_needs_18_and_the_service_terms(
    app_engine: AsyncEngine, learner: Learner, answers: ConsentAnswers
) -> None:
    with pytest.raises(ConsentRefusedError):
        await record_consent(app_engine, learner.id, answers)
    assert not await has_current_consent(app_engine, learner.id)
