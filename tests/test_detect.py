import pytest
from pathlib import Path

from scripts.detect import (
    _is_code_line,
    _is_json_content,
    _is_yaml_content,
    detect_file_type,
    should_compress,
)


class TestIsCodeLine:
    def test_import_statement(self):
        assert _is_code_line("import os")
        assert _is_code_line("from pathlib import Path")

    def test_require_statement(self):
        assert _is_code_line("require('fs')")

    def test_variable_declarations(self):
        assert _is_code_line("const x = 1")
        assert _is_code_line("let y = 2")
        assert _is_code_line("var z = 3")

    def test_function_definitions(self):
        assert _is_code_line("def my_func():")
        assert _is_code_line("class MyClass:")
        assert _is_code_line("function foo() {")
        assert _is_code_line("async function bar() {")
        assert _is_code_line("export const baz = () => {")

    def test_control_flow(self):
        assert _is_code_line("if (condition) {")
        assert _is_code_line("for (let i = 0; i < n; i++) {")
        assert _is_code_line("while (true) {")

    def test_closing_braces(self):
        assert _is_code_line("}")
        assert _is_code_line("});")
        assert _is_code_line("])")

    def test_decorators(self):
        assert _is_code_line("@property")
        assert _is_code_line("@pytest.mark.parametrize")

    def test_json_key_value(self):
        assert _is_code_line('  "name": "value"')

    def test_natural_language_not_flagged(self):
        assert not _is_code_line("This is a sentence.")
        assert not _is_code_line("- A bullet point")
        assert not _is_code_line("## A heading")
        assert not _is_code_line("Some text with a colon: here")


class TestIsJsonContent:
    def test_valid_json_object(self):
        assert _is_json_content('{"key": "value"}')

    def test_valid_json_array(self):
        assert _is_json_content('[1, 2, 3]')

    def test_invalid_json(self):
        assert not _is_json_content("not json")
        assert not _is_json_content("key: value")
        assert not _is_json_content("")

    def test_valid_json_nested(self):
        assert _is_json_content('{"a": {"b": [1, 2]}}')


class TestIsYamlContent:
    def test_yaml_like_content(self):
        lines = [
            "name: my-project",
            "version: 1.0.0",
            "author: John Doe",
            "description: A project",
            "license: MIT",
        ]
        assert _is_yaml_content(lines)

    def test_frontmatter(self):
        lines = ["---", "title: Hello", "date: 2024-01-01", "---"]
        assert _is_yaml_content(lines)

    def test_natural_language_not_yaml(self):
        lines = [
            "This is a paragraph.",
            "It has multiple sentences.",
            "Nothing looks like YAML here.",
        ]
        assert not _is_yaml_content(lines)

    def test_empty_lines(self):
        assert not _is_yaml_content([])


class TestDetectFileType:
    def test_markdown_extension(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Hello\nSome content")
        assert detect_file_type(f) == "natural_language"

    def test_txt_extension(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("Some notes")
        assert detect_file_type(f) == "natural_language"

    def test_rst_extension(self, tmp_path):
        f = tmp_path / "docs.rst"
        f.write_text("Title\n=====\nContent")
        assert detect_file_type(f) == "natural_language"

    def test_python_extension(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("def hello(): pass")
        assert detect_file_type(f) == "code"

    def test_js_extension(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        assert detect_file_type(f) == "code"

    def test_json_extension(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"key": "val"}')
        assert detect_file_type(f) == "config"

    def test_yaml_extension(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("key: value")
        assert detect_file_type(f) == "config"

    def test_extensionless_natural_language(self, tmp_path):
        f = tmp_path / "README"
        f.write_text("This is documentation.\nIt describes the project.\nNothing code-like here.")
        assert detect_file_type(f) == "natural_language"

    def test_extensionless_json(self, tmp_path):
        f = tmp_path / "MANIFEST"
        f.write_text('{"name": "pkg", "version": "1.0"}')
        assert detect_file_type(f) == "config"

    def test_extensionless_code(self, tmp_path):
        f = tmp_path / "script"
        code = "\n".join([
            "import os",
            "from pathlib import Path",
            "def main():",
            "    pass",
            "class Foo:",
            "    def bar(self):",
            "        return 1",
        ])
        f.write_text(code)
        assert detect_file_type(f) == "code"

    def test_unknown_extension(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("some data")
        assert detect_file_type(f) == "unknown"


class TestShouldCompress:
    def test_markdown_should_compress(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("# Title\nContent here.")
        assert should_compress(f) is True

    def test_original_backup_skipped(self, tmp_path):
        f = tmp_path / "doc.original.md"
        f.write_text("# Title\nContent here.")
        assert should_compress(f) is False

    def test_python_not_compressed(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("def hello(): pass")
        assert should_compress(f) is False

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.md"
        assert should_compress(f) is False

    def test_directory_not_compressed(self, tmp_path):
        assert should_compress(tmp_path) is False
