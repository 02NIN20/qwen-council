"""Tests for content type detection."""

import pytest

from backend.utils.content_detector import detect_content_type, get_handler_prompt


class TestDetectContentType:
    """Test content type detection from filename and content."""

    def test_python_file_detected_as_code(self) -> None:
        content = """
def hello(name):
    print(f"Hello, {name}!")
    return True

class Foo:
    pass
"""
        assert detect_content_type("script.py", content) == "code"

    def test_javascript_file_detected_as_code(self) -> None:
        content = """
function hello(name) {
    console.log(`Hello, ${name}!`);
    return true;
}

class Foo {
    constructor() {}
}
"""
        assert detect_content_type("app.js", content) == "code"

    def test_math_latex_detected_as_math(self) -> None:
        content = r"""
The quadratic formula states that for $ax^2 + bx + c = 0$,
the solutions are given by:
$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

We can prove this theorem by completing the square.
"""
        assert detect_content_type("proof.tex", content) == "math"

    def test_research_paper_detected_as_research(self) -> None:
        content = """
Abstract
This paper presents a novel approach to deep learning.

Introduction
Recent advances in neural networks have enabled...

Methodology
We used a dataset of 10,000 images...

Results
Our model achieved 95% accuracy...

Conclusion
We have shown that...

References
[1] Smith et al. (2023)...
"""
        assert detect_content_type("paper.txt", content) == "research"

    def test_plain_text_detected_as_text(self) -> None:
        content = """
This is a plain text document. It contains regular prose
and narrative content. There are no code blocks or
mathematical formulas. Just natural language text.
"""
        assert detect_content_type("essay.txt", content) == "text"

    def test_markdown_detected_as_markdown(self) -> None:
        content = """# Title

Some content with **bold** text.

- List item 1
- List item 2
"""
        assert detect_content_type("README.md", content) == "markdown"

    def test_empty_content_returns_text(self) -> None:
        assert detect_content_type("file.txt", "") == "text"
        assert detect_content_type("file.txt", "   ") == "text"

    def test_sql_file_detected_as_code(self) -> None:
        content = """
SELECT u.name, COUNT(o.id) as orders
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.active = TRUE
GROUP BY u.id;
"""
        assert detect_content_type("query.sql", content) == "code"

    def test_html_file_detected_as_code(self) -> None:
        content = """
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello</h1></body>
</html>
"""
        assert detect_content_type("page.html", content) == "code"

    def test_config_file_detected_as_code(self) -> None:
        content = """
server {
    listen 80;
    server_name example.com;
    location / {
        proxy_pass http://backend;
    }
}
"""
        assert detect_content_type("nginx.conf", content) == "code"

    def test_pure_math_text_detected_as_math(self) -> None:
        content = """
Let f(x) = x^2 + 2x + 1 = (x+1)^2
The derivative is f'(x) = 2x + 2
The integral ∫x^2 dx = x^3/3 + C
"""
        assert detect_content_type("math.txt", content) == "math"

    def test_math_with_equations(self) -> None:
        content = """
The equation E = mc^2 is famous.
We also have F = ma.
The Pythagorean theorem: a² + b² = c²
"""
        assert detect_content_type("formulas.txt", content) == "math"


class TestGetHandlerPrompt:
    """Test handler prompt generation."""

    def test_math_prompt(self) -> None:
        prompt = get_handler_prompt("math", "calculus.txt")
        assert "math" in prompt.lower() or "mathematical" in prompt.lower()
        assert "LaTeX" in prompt

    def test_research_prompt(self) -> None:
        prompt = get_handler_prompt("research", "paper.txt")
        assert "academic" in prompt.lower() or "research" in prompt.lower()

    def test_text_prompt(self) -> None:
        prompt = get_handler_prompt("text", "notes.txt")
        assert "read" in prompt.lower() or "answer" in prompt.lower()

    def test_markdown_prompt(self) -> None:
        prompt = get_handler_prompt("markdown", "doc.md")
        assert "markdown" in prompt.lower() or "edit" in prompt.lower()

    def test_code_prompt(self) -> None:
        prompt = get_handler_prompt("code", "main.py")
        assert "read" in prompt.lower() or "answer" in prompt.lower()
