"""FF10's simulated learners: each is one of the 5,000 synthetic learners, signed in, studying.

Run by evals/load/run.py, one Locust process per step. A learner signs in by cookie: the session the app
itself would set after /masuk (Starlette's SessionMiddleware format, signed with the stack's session secret),
because redeeming 5,000 invite codes would measure argon2, not the study path. What a learner does, by weight,
follows the product: mostly quiz batches and answers (each answer writes a learning event), then the home page,
the plan, memory, reading and the report, and now and then a chat question (scripted model, real MCP call).

Response times are kept in two groups, "$0 path" (every page and write, no model) and "chat", and written to
`$JUKU_LOAD_OUT` when the step ends, since FF10 judges the $0 path alone.
"""

from __future__ import annotations

import json
import os
import random
import secrets
from base64 import b64encode
from pathlib import Path
from typing import Any

from itsdangerous import TimestampSigner
from locust import HttpUser, between, events, task

SYNTHETIC_LEARNERS = 5000  # juku_data.synthetic.SYNTHETIC_LEARNERS: public IDs syn-1 to syn-5000
QUIZ_ANSWERS_PER_VISIT = 4
CHAT_QUESTION = "Kata apa yang sebaiknya saya pelajari minggu ini?"
CHAT_PATH = "/chat/kirim"

times_by_group: dict[str, list[float]] = {"$0 path": [], "chat": []}
failures_by_group: dict[str, int] = {"$0 path": 0, "chat": 0}


def session_cookie(secret: str, learner: str, csrf: str) -> str:
    """The cookie Starlette's SessionMiddleware sets: base64 JSON, signed with itsdangerous' TimestampSigner."""
    data = b64encode(json.dumps({"learner": learner, "csrf": csrf}).encode("utf-8"))
    return TimestampSigner(secret).sign(data).decode("utf-8")


@events.request.add_listener
def record(name: str, response_time: float, exception: Exception | None, **_kwargs: Any) -> None:
    group = "chat" if name == CHAT_PATH else "$0 path"
    times_by_group[group].append(response_time)
    if exception is not None:
        failures_by_group[group] += 1


@events.test_stop.add_listener
def write_groups(**_kwargs: Any) -> None:
    out = os.environ.get("JUKU_LOAD_OUT")
    if out:
        Path(out).write_text(json.dumps({"times_ms": times_by_group, "failures": failures_by_group}))


class Learner(HttpUser):
    wait_time = between(2, 8)  # seconds between a learner's actions: reading a question, choosing

    def on_start(self) -> None:
        secret = Path(os.environ["JUKU_LOAD_SECRETS"], "juku_session_secret").read_text().strip()
        self.csrf = secrets.token_hex(16)
        learner = f"syn-{random.randint(1, SYNTHETIC_LEARNERS)}"  # noqa: S311 (picking a learner, not a secret)
        self.client.cookies.set("juku_session", session_cookie(secret, learner, self.csrf))

    @task(6)
    def quiz(self) -> None:
        batch = self.client.get("/kuis/data?batch=0", name="/kuis/data")
        if batch.status_code != 200:
            return
        for item in batch.json()["items"][:QUIZ_ANSWERS_PER_VISIT]:
            answer = {"word_id": item["word_id"], "kind": item["kind"], "chosen": random.choice(item["options"])}  # noqa: S311
            self.client.post("/kuis/jawab", json=answer, headers={"X-CSRF-Token": self.csrf})

    @task(3)
    def home(self) -> None:
        self.client.get("/beranda")

    @task(1)
    def plan(self) -> None:
        self.client.get("/rencana")

    @task(1)
    def memory(self) -> None:
        self.client.get("/ingat")

    @task(1)
    def reading(self) -> None:
        self.client.get("/bacaan")

    @task(1)
    def report(self) -> None:
        self.client.get("/laporan")

    @task(1)
    def chat(self) -> None:
        with self.client.post(
            CHAT_PATH, json={"question": CHAT_QUESTION}, headers={"X-CSRF-Token": self.csrf}, catch_response=True
        ) as reply:
            if not reply.status_code:
                reply.failure("connection dropped: no response")
            # The scripted answer cites a word the MCP call returned, so an unverified one means the call failed.
            elif '"is_verified": true' not in reply.text:
                reply.failure("no verified answer: the stream ended early or the tool call failed")
