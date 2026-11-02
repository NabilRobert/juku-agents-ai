"""Which model the app builds from its settings. No model is called."""

import pytest
from juku_app.cli import chat_model
from juku_app.settings import AppSettings
from pydantic import ValidationError
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel


def settings_with(**overrides: str) -> AppSettings:
    return AppSettings(
        app_database_url="postgresql://unused",
        dict_database_url="postgresql://unused",
        session_secret="unused",
        delegation_signing_key="unused",
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def test_the_reasoning_effort_reaches_the_model() -> None:
    model = chat_model(settings_with(model_api_key="not-a-real-key", model_reasoning_effort="low"))
    assert isinstance(model, OpenAIChatModel)
    assert model.settings == {"openai_reasoning_effort": "low"}


def test_with_no_effort_set_the_model_keeps_its_own_default() -> None:
    model = chat_model(settings_with(model_api_key="not-a-real-key"))
    assert isinstance(model, OpenAIChatModel)
    assert model.settings is None


def test_an_effort_the_model_doesnt_know_stops_start_up() -> None:
    with pytest.raises(ValidationError):
        settings_with(model_reasoning_effort="extreme")


def test_without_a_key_the_app_uses_its_stand_in_whatever_the_effort() -> None:
    assert isinstance(chat_model(settings_with(model_reasoning_effort="high")), FunctionModel)
