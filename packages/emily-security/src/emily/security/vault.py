"""Encrypted Secrets Vault for Emily OS."""

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SecretsVault:
    """Secure encrypted storage for API keys, passwords, and tokens."""

    def __init__(self, vault_path: Path | str | None = None, master_key: str | None = None) -> None:
        self.vault_path = Path(vault_path) if vault_path else Path("data/security/vault.json")
        self._key = (master_key or "EMILY_OS_DEFAULT_LOCAL_VAULT_KEY").encode("utf-8")

    def _derive_key(self) -> bytes:
        return hashlib.sha256(self._key).digest()

    def _xor_cipher(self, data: bytes) -> bytes:
        key = self._derive_key()
        return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

    def set_secret(self, key: str, value: str) -> None:
        """Store an encrypted secret key-value pair."""
        vault_data = self._read_vault_raw()
        enc_value = base64.b64encode(self._xor_cipher(value.encode("utf-8"))).decode("utf-8")
        vault_data[key] = enc_value
        self._write_vault_raw(vault_data)

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        """Retrieve and decrypt a secret key."""
        vault_data = self._read_vault_raw()
        if key not in vault_data:
            return default
        try:
            raw_enc = base64.b64decode(vault_data[key].encode("utf-8"))
            dec_bytes = self._xor_cipher(raw_enc)
            return dec_bytes.decode("utf-8")
        except Exception as e:
            logger.error("Failed to decrypt secret %s: %s", key, e)
            return default

    def list_keys(self) -> list[str]:
        """List stored secret keys without revealing values."""
        return sorted(self._read_vault_raw().keys())

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from the vault."""
        vault_data = self._read_vault_raw()
        if key in vault_data:
            del vault_data[key]
            self._write_vault_raw(vault_data)
            return True
        return False

    def _read_vault_raw(self) -> dict[str, str]:
        if not self.vault_path.exists():
            return {}
        try:
            content = self.vault_path.read_text(encoding="utf-8")
            return json.loads(content) if content else {}
        except Exception:
            return {}

    def _write_vault_raw(self, data: dict[str, str]) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
