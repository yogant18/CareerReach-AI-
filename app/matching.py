"""
Skill matching between a job's required skills and a reference text
(a resume, or the tech stacks in a portfolio).

This is plain keyword matching, not AI: a skill counts as matched when it, or a
common alias of it, appears in the reference text. It is fast, free and
predictable, but it will not recognise a skill described in different words.
"""

import re
from typing import Any, Dict, Iterable, List

# Each group lists different ways of writing the same skill.
_ALIAS_GROUPS = [
    {"javascript", "js"},
    {"typescript", "ts"},
    {"kubernetes", "k8s"},
    {"machine learning", "ml"},
    {"artificial intelligence", "ai"},
    {"amazon web services", "aws"},
    {"google cloud platform", "google cloud", "gcp"},
    {"microsoft azure", "azure"},
    {"postgresql", "postgres"},
    {"node js", "nodejs", "node"},
    {"react js", "reactjs", "react"},
    {"vue js", "vuejs", "vue"},
    {"next js", "nextjs"},
    {"golang", "go"},
    {"c#", "csharp"},
    {"ci cd", "cicd", "continuous integration"},
    {"natural language processing", "nlp"},
    {"large language models", "large language model", "llms", "llm"},
    {"user experience", "ux"},
    {"search engine optimization", "seo"},
]


_AMBIGUOUS = {"go"}


def _norm(text: Any) -> str:
    """Lowercase and keep only letters, digits, + and # (so 'C++', 'C#', 'Node.js' survive as tokens)."""
    return re.sub(r"[^a-z0-9+#]+", " ", str(text).lower()).strip()


def _variants(skill: str) -> set:
    base = _norm(skill)
    own = {base, base.replace(" ", "")}
    out = set(own)
    for group in _ALIAS_GROUPS:
        if own & group:
            # "go" is also an everyday word, so it only counts when the job itself says "Go"
            out |= {alias for alias in group if alias not in _AMBIGUOUS}
    return {v for v in out if v}


def skill_match(job_skills: Iterable[Any], reference_text: str) -> Dict[str, Any]:
    """
    Compare a job's skills with a reference text.
    Returns {"matched": [...], "missing": [...], "total": n, "score": 0-100}.
    """
    skills: List[str] = []
    seen = set()
    for raw in job_skills or []:
        skill = str(raw).strip()
        if skill and _norm(skill) and _norm(skill) not in seen:
            seen.add(_norm(skill))
            skills.append(skill)

    tokens = _norm(reference_text).split()
    padded = " " + " ".join(tokens) + " "
    # single words plus adjacent pairs joined, so "node js" in the text matches "nodejs"
    joined = set(tokens) | {a + b for a, b in zip(tokens, tokens[1:])}

    matched, missing = [], []
    for skill in skills:
        hit = any(f" {v} " in padded or v in joined for v in _variants(skill))
        (matched if hit else missing).append(skill)

    total = len(skills)
    return {
        "matched": matched,
        "missing": missing,
        "total": total,
        "score": round(100 * len(matched) / total) if total else 0,
    }
