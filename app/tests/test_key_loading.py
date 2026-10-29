"""The app's signing key and Juku's MCP server's public key: loaded from PEM text, refused clearly if wrong.

Pinned before the two loaders became one pair in juku_common, so the
messages stay what they were: a key of the wrong type names its setting
and how to make the right one; text that isn't a key at all fails with
cryptography's own error.
"""

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from juku_app.cli import signing_key
from juku_app.settings import AppSettings
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings

NOT_A_KEY = "-----BEGIN PRIVATE KEY-----\nbm90IGEga2V5\n-----END PRIVATE KEY-----\n"
NOT_A_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\nbm90IGEga2V5\n-----END PUBLIC KEY-----\n"


def pem_private(key: ec.EllipticCurvePrivateKey | ed25519.Ed25519PrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def pem_public(key: ec.EllipticCurvePublicKey | ed25519.Ed25519PublicKey) -> str:
    return key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def app_config(pem: str) -> AppSettings:
    return AppSettings.model_construct(delegation_signing_key=pem)


def mcp_settings(pem: str, tmp_path: Path) -> McpSettings:
    return McpSettings.model_construct(
        app_database_url="postgresql+asyncpg://u@h/app",
        dict_database_url="postgresql+asyncpg://u@h/dict",
        delegation_public_key=pem,
        audit_log=tmp_path / "audit.jsonl",
    )


def private_key_error(pem: str) -> str:
    """What cryptography itself says about text that isn't a private key: the message the app passes on."""
    with pytest.raises(ValueError) as refused:
        serialization.load_pem_private_key(pem.encode(), password=None)
    return str(refused.value)


def public_key_error(pem: str) -> str:
    """The same, for a public key: the message Juku's MCP server passes on."""
    with pytest.raises(ValueError) as refused:
        serialization.load_pem_public_key(pem.encode())
    return str(refused.value)


def test_the_app_loads_an_ed25519_signing_key() -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    assert (
        signing_key(app_config(pem_private(key))).public_key().public_bytes_raw() == key.public_key().public_bytes_raw()
    )


def test_the_app_refuses_a_signing_key_of_another_type_and_says_how_to_make_one() -> None:
    with pytest.raises(SystemExit) as refused:
        signing_key(app_config(pem_private(ec.generate_private_key(ec.SECP256R1()))))
    assert str(refused.value) == (
        "JUKU_DELEGATION_SIGNING_KEY isn't an Ed25519 private key: make one with ops/make-secrets.sh"
    )


def test_the_app_passes_on_cryptographys_error_for_text_that_isnt_a_key() -> None:
    with pytest.raises(ValueError) as refused:
        signing_key(app_config(NOT_A_KEY))
    assert str(refused.value) == private_key_error(NOT_A_KEY)


def test_the_mcp_server_refuses_a_public_key_of_another_type_and_says_how_to_make_one(tmp_path: Path) -> None:
    other = ec.generate_private_key(ec.SECP256R1()).public_key()
    with pytest.raises(ValueError) as refused:
        create_app(mcp_settings(pem_public(other), tmp_path))
    assert str(refused.value) == (
        "JUKU_MCP_DELEGATION_PUBLIC_KEY isn't an Ed25519 public key: make one with ops/make-secrets.sh"
    )


def test_the_mcp_server_passes_on_cryptographys_error_for_text_that_isnt_a_key(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as refused:
        create_app(mcp_settings(NOT_A_PUBLIC_KEY, tmp_path))
    assert str(refused.value) == public_key_error(NOT_A_PUBLIC_KEY)


def test_the_mcp_server_starts_with_an_ed25519_public_key(tmp_path: Path) -> None:
    create_app(mcp_settings(pem_public(ed25519.Ed25519PrivateKey.generate().public_key()), tmp_path))
