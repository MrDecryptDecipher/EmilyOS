"""Unit tests for Security Runtime & Policy Subsystem."""

import pytest
from emily.core.types.tool import ToolPermissionLevel
from emily.security.approvals import ApprovalGateManager
from emily.security.audit import AuditLogger
from emily.security.subsystem import SecuritySubsystem
from emily.security.tokens import CapabilityTokenManager
from emily.security.vault import SecretsVault


def test_secrets_vault_encrypt_decrypt(tmp_path):
    v_path = tmp_path / "vault.json"
    vault = SecretsVault(vault_path=v_path)
    vault.set_secret("OPENAI_KEY", "sk-test123456789")

    retrieved = vault.get_secret("OPENAI_KEY")
    assert retrieved == "sk-test123456789"
    assert vault.list_keys() == ["OPENAI_KEY"]

    deleted = vault.delete_secret("OPENAI_KEY")
    assert deleted is True
    assert vault.get_secret("OPENAI_KEY") is None


def test_capability_tokens():
    mgr = CapabilityTokenManager()
    token = mgr.issue_token(
        granted=[ToolPermissionLevel.READ, ToolPermissionLevel.DESKTOP],
        label="test-token",
        valid_seconds=3600,
    )
    assert mgr.validate(token.token_id, [ToolPermissionLevel.READ]) is True
    assert mgr.validate(token.token_id, [ToolPermissionLevel.EXECUTE]) is False


def test_approval_gates():
    mgr = ApprovalGateManager()
    req = mgr.request_approval("trade_execution", "Execute buy order for 10 AAPL")
    assert req.approved is None
    assert len(mgr.list_pending()) == 1

    ok = mgr.respond(req.request_id, approved=True)
    assert ok is True
    assert len(mgr.list_pending()) == 0
    assert mgr.list_history()[0].approved is True


def test_audit_logger_hash_chain(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=log_path)
    rec1 = logger.record_event("login", "user1", {"ip": "127.0.0.1"})
    rec2 = logger.record_event("action", "user1", {"action": "delete"})

    assert rec2.prev_hash == rec1.record_hash
    assert logger.verify_integrity() is True


@pytest.mark.asyncio
async def test_security_subsystem_lifecycle():
    subsystem = SecuritySubsystem()

    class DummyCtx:
        pass

    await subsystem.start(DummyCtx())
    assert subsystem.vault is not None
    await subsystem.stop(DummyCtx())
