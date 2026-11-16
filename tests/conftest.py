import os
import sys

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SAMPLE_EMAIL = (
    "Subject: Quick idea for your Python role\n\n"
    "Hi Priya,\n\nWe built X & Y (50% faster).\nSee https://a.example/1?x=1&y=2\n\nBest,\nAlex"
)
SAMPLE_JOB = {"role": "Python Engineer", "experience": "3+ years", "skills": ["Python", "AWS"], "description": "Builds APIs"}


def scripted_llm(rules, default="Subject: Default\n\nDefault body.\n\nAlex", seen=None):
    """
    A stand-in model: returns the reply for the first rule whose marker appears in the prompt.
    `rules` is a list of (marker, reply). Prompts are appended to `seen` when given.
    """
    def reply(inp):
        text = inp.to_string() if hasattr(inp, "to_string") else str(inp)
        if seen is not None:
            seen.append(text)
        for marker, answer in rules:
            if marker in text:
                return AIMessage(content=answer)
        return AIMessage(content=default)
    return RunnableLambda(reply)


@pytest.fixture
def make_chain():
    """Build a Chain whose model is replaced by a scripted stand-in."""
    from app.chains import Chain

    def _make(rules=(), default="Subject: Default\n\nDefault body.\n\nAlex", seen=None):
        chain = Chain("gsk_testkey", "test-model", provider="groq")
        chain.llm = scripted_llm(list(rules), default, seen)
        return chain
    return _make
