import pytest
from pathlib import Path

from scripts.validate import (
    ValidationResult,
    count_bullets,
    extract_code_blocks,
    extract_headings,
    extract_inline_codes,
    extract_paths,
    extract_urls,
    validate,
    validate_code_blocks,
    validate_headings,
    validate_inline_codes,
    validate_urls,
)


class TestExtractHeadings:
    def test_basic_headings(self):
        text = "# H1\n## H2\n### H3"
        headings = extract_headings(text)
        assert headings == [("#", "H1"), ("##", "H2"), ("###", "H3")]

    def test_no_headings(self):
        assert extract_headings("Just some text") == []

    def test_heading_with_spaces(self):
        headings = extract_headings("#  Spaced Title  ")
        assert headings == [("#", "Spaced Title")]

    def test_inline_hash_not_heading(self):
        text = "Some text with # in the middle"
        assert extract_headings(text) == []


class TestExtractCodeBlocks:
    def test_basic_backtick_block(self):
        text = "```python\nprint('hello')\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "print('hello')" in blocks[0]

    def test_tilde_block(self):
        text = "~~~bash\necho hi\n~~~"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "echo hi" in blocks[0]

    def test_multiple_blocks(self):
        text = "```\nblock1\n```\n\nsome text\n\n```\nblock2\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2

    def test_unclosed_fence_skipped(self):
        text = "```\nunclosed block"
        blocks = extract_code_blocks(text)
        assert blocks == []

    def test_no_blocks(self):
        assert extract_code_blocks("Just text, no code") == []

    def test_block_preserves_content_exactly(self):
        content = "```python\ndef foo():\n    return 42\n```"
        blocks = extract_code_blocks(content)
        assert blocks[0] == content

    def test_longer_fence_not_closed_by_shorter(self):
        text = "````\nouter\n```\nnested\n```\nouter end\n````"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "nested" in blocks[0]


class TestExtractUrls:
    def test_http_url(self):
        urls = extract_urls("See https://example.com for details")
        assert "https://example.com" in urls

    def test_multiple_urls(self):
        text = "https://foo.com and http://bar.org"
        urls = extract_urls(text)
        assert len(urls) == 2

    def test_no_urls(self):
        assert extract_urls("No links here") == set()

    def test_url_in_markdown_link(self):
        urls = extract_urls("[link](https://example.com)")
        assert "https://example.com" in urls


class TestCountBullets:
    def test_dash_bullets(self):
        text = "- item1\n- item2\n- item3"
        assert count_bullets(text) == 3

    def test_asterisk_bullets(self):
        text = "* item1\n* item2"
        assert count_bullets(text) == 2

    def test_plus_bullets(self):
        text = "+ item1"
        assert count_bullets(text) == 1

    def test_no_bullets(self):
        assert count_bullets("Just text") == 0


class TestExtractInlineCodes:
    def test_basic_inline_code(self):
        codes = extract_inline_codes("Use `foo()` and `bar()`")
        assert "foo()" in codes
        assert "bar()" in codes

    def test_no_inline_code(self):
        assert extract_inline_codes("No backticks here") == []

    def test_code_inside_fence_excluded(self):
        text = "```\n`not inline`\n```\n\nBut `this is` inline"
        codes = extract_inline_codes(text)
        assert "this is" in codes


class TestValidationResult:
    def test_starts_valid(self):
        r = ValidationResult()
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_invalidates(self):
        r = ValidationResult()
        r.add_error("something broke")
        assert r.is_valid is False
        assert "something broke" in r.errors

    def test_add_warning_stays_valid(self):
        r = ValidationResult()
        r.add_warning("minor issue")
        assert r.is_valid is True
        assert "minor issue" in r.warnings


class TestValidateHeadings:
    def test_identical_headings(self):
        r = ValidationResult()
        text = "# H1\n## H2"
        validate_headings(text, text, r)
        assert r.is_valid

    def test_missing_heading(self):
        r = ValidationResult()
        orig = "# H1\n## H2"
        comp = "# H1"
        validate_headings(orig, comp, r)
        assert not r.is_valid
        assert any("count" in e for e in r.errors)

    def test_changed_heading_text(self):
        r = ValidationResult()
        orig = "# Original Title"
        comp = "# Changed Title"
        validate_headings(orig, comp, r)
        assert r.is_valid  # count matches, so valid but warning
        assert any("Heading text" in w or "order" in w for w in r.warnings)


class TestValidateCodeBlocks:
    def test_identical_blocks(self):
        r = ValidationResult()
        text = "```python\ncode\n```"
        validate_code_blocks(text, text, r)
        assert r.is_valid

    def test_missing_block(self):
        r = ValidationResult()
        orig = "```python\ncode\n```"
        comp = "no code block here"
        validate_code_blocks(orig, comp, r)
        assert not r.is_valid

    def test_modified_block(self):
        r = ValidationResult()
        orig = "```python\noriginal code\n```"
        comp = "```python\nmodified code\n```"
        validate_code_blocks(orig, comp, r)
        assert not r.is_valid


class TestValidateUrls:
    def test_identical_urls(self):
        r = ValidationResult()
        text = "See https://example.com"
        validate_urls(text, text, r)
        assert r.is_valid

    def test_missing_url(self):
        r = ValidationResult()
        orig = "See https://example.com"
        comp = "See the docs"
        validate_urls(orig, comp, r)
        assert not r.is_valid
        assert any("URL mismatch" in e for e in r.errors)


class TestValidateInlineCodes:
    def test_identical_inline_codes(self):
        r = ValidationResult()
        text = "Use `foo()` here"
        validate_inline_codes(text, text, r)
        assert r.is_valid

    def test_missing_inline_code(self):
        r = ValidationResult()
        orig = "Use `foo()` and `bar()`"
        comp = "Use foo and bar"
        validate_inline_codes(orig, comp, r)
        assert not r.is_valid
        assert any("Inline code lost" in e for e in r.errors)


class TestValidateEndToEnd:
    def test_identical_files_valid(self, tmp_path):
        content = "# Title\n\nSome text with `code` and https://example.com\n\n```bash\necho hi\n```"
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text(content)
        comp.write_text(content)
        result = validate(orig, comp)
        assert result.is_valid

    def test_compressed_file_missing_url(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text("See https://example.com for info")
        comp.write_text("See docs for info")
        result = validate(orig, comp)
        assert not result.is_valid

    def test_compressed_file_missing_code_block(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text("Run:\n\n```bash\nnpm install\n```")
        comp.write_text("Run npm install")
        result = validate(orig, comp)
        assert not result.is_valid

    def test_compressed_file_drops_heading(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text("# Title\n## Section\nContent")
        comp.write_text("# Title\nContent")
        result = validate(orig, comp)
        assert not result.is_valid
