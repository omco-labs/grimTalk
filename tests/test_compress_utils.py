import pytest
from pathlib import Path, PurePosixPath

from scripts.compress import is_sensitive_path, strip_llm_wrapper


class TestIsSensitivePath:
    def test_env_file(self, tmp_path):
        assert is_sensitive_path(tmp_path / ".env")
        assert is_sensitive_path(tmp_path / ".env.production")

    def test_credentials_file(self, tmp_path):
        assert is_sensitive_path(tmp_path / "credentials.md")
        assert is_sensitive_path(tmp_path / "credentials.json")

    def test_secrets_file(self, tmp_path):
        assert is_sensitive_path(tmp_path / "secrets.md")
        assert is_sensitive_path(tmp_path / "secret.txt")

    def test_password_file(self, tmp_path):
        assert is_sensitive_path(tmp_path / "passwords.txt")
        assert is_sensitive_path(tmp_path / "password.md")

    def test_ssh_key_files(self, tmp_path):
        assert is_sensitive_path(tmp_path / "id_rsa")
        assert is_sensitive_path(tmp_path / "id_ed25519")
        assert is_sensitive_path(tmp_path / "id_rsa.pub")
        assert is_sensitive_path(tmp_path / "authorized_keys")

    def test_pem_and_key_files(self, tmp_path):
        assert is_sensitive_path(tmp_path / "cert.pem")
        assert is_sensitive_path(tmp_path / "private.key")
        assert is_sensitive_path(tmp_path / "keystore.jks")

    def test_sensitive_directory_components(self, tmp_path):
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        assert is_sensitive_path(ssh_dir / "config")

        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        assert is_sensitive_path(aws_dir / "credentials")

    def test_api_key_in_name(self, tmp_path):
        assert is_sensitive_path(tmp_path / "api-key.md")
        assert is_sensitive_path(tmp_path / "apikey.txt")

    def test_token_in_name(self, tmp_path):
        assert is_sensitive_path(tmp_path / "access-token.md")

    def test_safe_files_not_flagged(self, tmp_path):
        assert not is_sensitive_path(tmp_path / "README.md")
        assert not is_sensitive_path(tmp_path / "CONTRIBUTING.md")
        assert not is_sensitive_path(tmp_path / "notes.txt")
        assert not is_sensitive_path(tmp_path / "config.md")
        assert not is_sensitive_path(tmp_path / "SKILL.md")


class TestStripLlmWrapper:
    def test_strips_markdown_fence(self):
        wrapped = "```markdown\n# Title\n\nContent here\n```"
        result = strip_llm_wrapper(wrapped)
        assert result == "# Title\n\nContent here"

    def test_strips_backtick_fence_no_lang(self):
        wrapped = "```\ncontent\n```"
        result = strip_llm_wrapper(wrapped)
        assert result == "content"

    def test_strips_tilde_fence(self):
        wrapped = "~~~\ncontent\n~~~"
        result = strip_llm_wrapper(wrapped)
        assert result == "content"

    def test_passthrough_no_wrapper(self):
        content = "# Title\n\nNo outer fence here"
        assert strip_llm_wrapper(content) == content

    def test_passthrough_partial_fence(self):
        content = "```python\nsome code\n```\n\nmore text"
        assert strip_llm_wrapper(content) == content

    def test_preserves_inner_code_blocks(self):
        wrapped = "```markdown\n# Title\n\n```bash\necho hi\n```\n\nEnd\n```"
        result = strip_llm_wrapper(wrapped)
        assert "```bash" in result
        assert "echo hi" in result
