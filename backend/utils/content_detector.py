"""Content type detector — distinguishes code from general text/math/research.

Used by the chat endpoint to route text content to a general-purpose
LLM call instead of the code-focused multi-agent council.
"""

from __future__ import annotations

import re
from typing import Any


# File extensions that are always code
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
    ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh", ".sql",
    ".css", ".scss", ".html", ".vue", ".svelte", ".swift", ".kt",
    ".m", ".mm", ".cs", ".fs", ".ml", ".ex", ".exs", ".clj",
    ".scala", ".r", ".jl", ".d", ".dart", ".lua", ".tcl", ".vim",
}

# Patterns that strongly indicate code (vs prose)
CODE_PATTERNS = [
    re.compile(r'^\s*(def|class|import|from|function|var|let|const|if|else|for|while|return)\s', re.MULTILINE),
    re.compile(r'^\s*(public|private|protected)\s+(static\s+)?(void|int|String|bool)', re.MULTILINE),
    re.compile(r'[{};]\s*$', re.MULTILINE),
    re.compile(r'^\s*(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\s', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*(#include|using namespace|package|import\s)', re.MULTILINE),
    re.compile(r'^\s{2,}[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]', re.MULTILINE),  # indented code
]

# Patterns that strongly indicate math/prose
MATH_PATTERNS = [
    re.compile(r'\$[^$]+\$|\\\([^\\]+\)'),  # LaTeX
    re.compile(r'\\[a-zA-Z]+\b'),  # LaTeX commands
    re.compile(r'\b(theorem|lemma|proof|corollary|proposition)\b', re.IGNORECASE),
    re.compile(r'\b(equation|formula|integral|sum|product|limit)\b', re.IGNORECASE),
    re.compile(r'[=≈≠≤≥±∫∑∏∂∞∇∈∉∀∃⊆⊇∪∩]'),
    re.compile(r'\b\d+\s*[\+\-\*/\^=]\s*\d+'),  # arithmetic
    re.compile(r'\b(integral|derivative|matrix|vector|tensor)\b', re.IGNORECASE),
]

# Patterns for research papers / academic text
RESEARCH_PATTERNS = [
    re.compile(r'\b(abstract|introduction|methodology|results|conclusion|references)\b', re.IGNORECASE),
    re.compile(r'\b(hypothesis|thesis|dissertation|peer.review|journal)\b', re.IGNORECASE),
    re.compile(r'\\cite\{|\\ref\{|\\section\{|\\begin\{'),
    re.compile(r'^\s*Abstract[:.\s]', re.MULTILINE | re.IGNORECASE),
]


def detect_content_type(filename: str, content: str) -> str:
    """Detect whether the content is code, math, or general text.

    Returns
    -------
    str
        One of: "code", "math", "research", "text", "markdown"
    """
    if not content or not content.strip():
        return "text"

    # Check extension first
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext in CODE_EXTENSIONS:
        return "code"

    # Markdown
    md_ext = {".md", ".markdown"}
    if ext in md_ext or content.lstrip().startswith("# "):
        return "markdown"

    # Count matches for each type
    code_score = sum(1 for p in CODE_PATTERNS if p.search(content))
    math_score = sum(1 for p in MATH_PATTERNS if p.search(content))
    research_score = sum(1 for p in RESEARCH_PATTERNS if p.search(content))

    # If multiple code patterns → code
    if code_score >= 2:
        return "code"

    # If math patterns → math
    if math_score >= 2:
        return "math"

    # If research patterns → research
    if research_score >= 2:
        return "research"

    # If single code pattern with high density → code
    if code_score == 1 and code_score * 10 > research_score + math_score:
        return "code"

    # Default to text (prose, natural language)
    return "text"


def get_handler_prompt(content_type: str, filename: str) -> str:
    """Get the appropriate system prompt for the content type."""
    base = "You are a helpful expert assistant."
    if content_type == "math":
        return f"{base} You excel at analyzing mathematical content. When the user shares math (formulas, proofs, equations), explain it clearly, verify correctness, identify errors, and provide insights. Use proper LaTeX notation in your responses."
    if content_type == "research":
        return f"{base} You excel at reading and analyzing academic papers. Summarize key findings, evaluate methodology, identify strengths and weaknesses, and answer questions about the research clearly."
    if content_type == "markdown":
        return f"{base} You can read and help edit markdown documents. Provide feedback on structure, clarity, and accuracy."
    return f"{base} Read the content provided and answer the user's question clearly and thoroughly."
