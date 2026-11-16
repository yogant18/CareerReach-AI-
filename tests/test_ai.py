"""Tests for the prompt chains and the provider layer, using stand-in models (no network, no keys)."""

import types

import pytest

from app import providers as P
from app.chains import Chain
from conftest import SAMPLE_EMAIL, SAMPLE_JOB


def ns(**kwargs):
    return types.SimpleNamespace(**kwargs)


# ---------------- chains ----------------
def test_extract_jobs_parses_json_and_strips_reasoning(make_chain):
    chain = make_chain(default='<think>plan</think>```json\n[{"role":"Data Engineer","skills":["SQL"]}]\n```')
    assert chain.extract_jobs("We need a Data Engineer")[0]["role"] == "Data Engineer"
    assert chain.last_error is None


def test_extract_jobs_falls_back_to_keyword_parser(make_chain):
    chain = make_chain(default="sorry, I cannot do that")
    jobs = chain.extract_jobs("Hiring a Senior Python Engineer with 3+ years of experience in AWS")
    assert jobs and "Python" in jobs[0]["skills"] and chain.last_error


def test_write_mail_cleans_markdown(make_chain):
    chain = make_chain(default="Subject: Hi\n\n**Hello** Priya,\n\n- point\n\nAlex")
    mail = chain.write_mail(SAMPLE_JOB, [], "Alex", "Acme", "BD", "Friendly", 100)
    assert mail.startswith("Subject: Hi") and "*" not in mail and "- point" not in mail


def test_application_mail_uses_the_resume(make_chain):
    seen = []
    chain = make_chain(default="Subject: Applying\n\nBody.\n\nAlex", seen=seen)
    mail = chain.write_application_mail(SAMPLE_JOB, [{"links": "https://gh.example/alex"}], "Alex", "RESUME: built ETL at Initech", "Analyst")
    assert mail.startswith("Subject: Applying")
    assert "built ETL at Initech" in seen[0] and "https://gh.example/alex" in seen[0] and "Never invent" in seen[0]


def test_subject_lines(make_chain):
    chain = make_chain(default='[{"subject":"One","why":"a"},{"subject":"","why":"skip"},{"subject":"Two","why":"b"}]')
    assert chain.subject_lines(SAMPLE_JOB, SAMPLE_EMAIL) == [{"subject": "One", "why": "a"}, {"subject": "Two", "why": "b"}]
    wrapped = make_chain(default='{"subjects":[{"subject":"Wrapped","why":"w"}]}')
    assert wrapped.subject_lines(SAMPLE_JOB, SAMPLE_EMAIL)[0]["subject"] == "Wrapped"


def test_follow_ups_fill_in_missing_fields(make_chain):
    chain = make_chain(default='[{"day":3,"subject":"Re: x","body":"**One**"},{"day":"7","subject":"","body":"Two"},{"subject":"s","body":"Three"}]')
    result = chain.follow_ups(SAMPLE_JOB, SAMPLE_EMAIL, "Alex")
    assert [(f["day"], f["body"]) for f in result] == [(3, "One"), (7, "Two"), (14, "Three")]
    assert result[1]["subject"] == "Re: Python Engineer"


def test_rewrite_keeps_original_when_the_model_fails(make_chain):
    ok = make_chain(default="Subject: Short\n\nShort.\n\nAlex")
    assert ok.rewrite_mail(SAMPLE_EMAIL, "shorter").startswith("Subject: Short") and ok.last_error is None
    empty = make_chain(default="")
    assert empty.rewrite_mail(SAMPLE_EMAIL, "shorter") == SAMPLE_EMAIL and empty.last_error


def test_linkedin_note_never_exceeds_the_limit(make_chain):
    long_note = "This is a sentence about my background. " * 20
    chain = make_chain(default='{"note": "%s", "inmail_subject": "Hello", "inmail_body": "**Body** text"}' % long_note.strip())
    result = chain.linkedin_messages(SAMPLE_JOB, SAMPLE_EMAIL, "Alex")
    assert 0 < len(result["note"]) <= 300 and result["note"].endswith(".")
    assert result["inmail_subject"] == "Hello" and result["inmail_body"] == "Body text"
    assert Chain._fit_to_limit("word " * 100, 50).strip() and len(Chain._fit_to_limit("word " * 100, 50)) <= 50
    assert len(Chain._fit_to_limit("x" * 400, 300)) == 300


@pytest.mark.parametrize("bad_reply", ["not json", "[]", '{"note": ""}'])
def test_bad_model_output_falls_back_to_templates(make_chain, bad_reply):
    chain = make_chain(default=bad_reply)
    assert len(chain.subject_lines(SAMPLE_JOB, SAMPLE_EMAIL)) == 5
    assert [f["day"] for f in chain.follow_ups(SAMPLE_JOB, SAMPLE_EMAIL, "Alex")] == [3, 7, 14]
    linkedin = chain.linkedin_messages(SAMPLE_JOB, SAMPLE_EMAIL, "Alex")
    assert 0 < len(linkedin["note"]) <= 300 and linkedin["inmail_body"]
    assert chain.last_error


def test_demo_mode_works_without_any_key():
    chain = Chain("DEMO_MODE", "m")
    assert chain.is_demo_mode and chain.llm is None
    assert chain.extract_jobs("Looking for a Python Developer with 2 years of experience")
    assert chain.write_mail(SAMPLE_JOB, [], "Alex", "Acme", "BD", "Friendly", 100).startswith("Subject:")
    assert chain.write_application_mail(SAMPLE_JOB, [], "Alex", "resume").startswith("Subject:")
    assert len(chain.subject_lines(SAMPLE_JOB, SAMPLE_EMAIL)) == 5
    assert len(chain.linkedin_messages(SAMPLE_JOB, SAMPLE_EMAIL, "Alex")["note"]) <= 300
    assert chain.rewrite_mail(SAMPLE_EMAIL, "x") == SAMPLE_EMAIL and "needs an AI key" in chain.last_error
    assert chain.chat_response([{"role": "user", "content": "subject lines please"}])


# ---------------- providers ----------------
@pytest.mark.parametrize("provider,key,valid", [
    ("groq", "gsk_abc", True), ("groq", "sk-abc", False), ("groq", "DEMO_MODE", False),
    ("openai", "sk-abcdefgh12345", True), ("openai", "sk-ant-abcdefgh", False), ("openai", "gsk_abc", False),
    ("anthropic", "sk-ant-abcdefgh", True), ("anthropic", "sk-abcdefgh", False),
    ("gemini", "AIzaSyA1234567890abcdefghij", True), ("gemini", "short", False), ("gemini", "sk-abcdefghijklmnopqrstuvwxyz", False),
    ("groq", "", False), ("openai", "sk-abc def", False), ("unknown", "gsk_abc", False),
])
def test_key_format_checks(provider, key, valid):
    assert P.is_valid_key(provider, key) is valid


def test_keys_are_redacted_from_error_text():
    text = P.redact_keys("bad key sk-ant-api03-AbC_123-xyz, AIzaSyA1234567890abc, gsk_abc123, Bearer tok.en end")
    assert "sk-ant" not in text and "AIza" not in text and "gsk_" not in text and "tok.en" not in text
    assert text.count("[REDACTED]") == 4


def test_normalize_handles_system_and_leading_assistant_turns():
    system, messages = P._normalize([
        {"role": "system", "content": "be brief"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "  "},
    ])
    assert system == "be brief" and messages == [{"role": "user", "content": "hi"}]
    assert P._normalize("just text") == ("", [{"role": "user", "content": "just text"}])
    with pytest.raises(ValueError):
        P._normalize([{"role": "assistant", "content": "only me"}])


class FakeOpenAI:
    def __init__(self, models=(), reject_temperature=False):
        self.calls = []
        self.reject_temperature = reject_temperature
        self.models = ns(list=lambda: [ns(id=m) for m in models])
        self.chat = ns(completions=ns(create=self._create))

    def _create(self, **kwargs):
        import httpx2
        import openai

        self.calls.append(kwargs)
        if self.reject_temperature and "temperature" in kwargs:
            request = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
            raise openai.BadRequestError("Unsupported value: 'temperature'", response=httpx2.Response(400, request=request), body=None)
        return ns(choices=[ns(message=ns(content="hello"))])


def test_model_lists_are_filtered_and_fall_back(monkeypatch):
    ids = ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-astra-2026-09-01", "gpt-6-audio", "text-embedding-4", "o4-mini", "gpt-image-2"]
    monkeypatch.setattr(P, "_openai_client", lambda provider, key: FakeOpenAI(models=ids))
    assert P.list_models("openai", "sk-abcdefgh12345") == ["gpt-6-astra", "gpt-6.1-sol", "o4-mini"]
    gemini_ids = ["models/gemini-3.8-flash", "models/gemini-3.8-pro", "models/gemini-embedding-2", "models/veo-4"]
    monkeypatch.setattr(P, "_openai_client", lambda provider, key: FakeOpenAI(models=gemini_ids))
    assert P.list_models("gemini", "AIzaSyA1234567890abcdefghij") == ["gemini-3.8-flash", "gemini-3.8-pro"]

    def broken(provider, key):
        raise RuntimeError("network down")
    monkeypatch.setattr(P, "_openai_client", broken)
    assert P.list_models("openai", "sk-abcdefgh12345") == P.PROVIDERS["openai"]["default_models"]
    assert P.list_models("openai", "not-a-key") == P.PROVIDERS["openai"]["default_models"]
    assert P.list_models("anthropic", "sk-ant-abcdefgh")[0] == "claude-opus-5-5"


def test_openai_retries_without_temperature_when_rejected(monkeypatch):
    client = FakeOpenAI(reject_temperature=True)
    monkeypatch.setattr(P, "_openai_client", lambda provider, key: client)
    llm = P.build_llm("openai", "sk-abcdefgh12345", "gpt-x", 0.6)
    assert llm.invoke([{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]).content == "hello"
    assert [c.get("temperature") for c in client.calls] == [0.6, None]
    assert client.calls[0]["messages"][0] == {"role": "system", "content": "s"}


class FakeClaude:
    def __init__(self, beta_error=None, refusal=False):
        self.calls = []
        self.beta = ns(messages=ns(create=lambda **kw: self._create("beta", beta_error, refusal, kw)))
        self.messages = ns(create=lambda **kw: self._create("plain", None, refusal, kw))

    def _create(self, path, error, refusal, kwargs):
        self.calls.append((path, kwargs))
        if error:
            raise error
        if refusal:
            return ns(stop_reason="refusal", stop_details=ns(explanation="policy"), content=[])
        return ns(stop_reason="end_turn", content=[ns(type="thinking", thinking=""), ns(type="text", text="from claude")])


def claude_bad_request(message):
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError(message, response=httpx2.Response(400, request=request), body=None)


def test_claude_request_shape(monkeypatch):
    client = FakeClaude()
    monkeypatch.setattr(P, "_anthropic_client", lambda key: client)
    llm = P.build_llm("anthropic", "sk-ant-abcdefgh", "claude-opus-5-5", 0.9)
    reply = llm.invoke([{"role": "system", "content": "sys"}, {"role": "assistant", "content": "hi"}, {"role": "user", "content": "q"}])
    assert reply.content == "from claude"
    path, kwargs = client.calls[0]
    assert path == "beta" and kwargs["fallbacks"] == "default" and kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["system"] == "sys" and kwargs["messages"] == [{"role": "user", "content": "q"}]
    assert "temperature" not in kwargs and kwargs["output_config"] == {"effort": "medium"}
    assert not P.supports_temperature("anthropic") and P.supports_temperature("openai")


def test_claude_haiku_skips_fallbacks_and_refusals_raise(monkeypatch):
    haiku = FakeClaude()
    monkeypatch.setattr(P, "_anthropic_client", lambda key: haiku)
    P.build_llm("anthropic", "sk-ant-abcdefgh", "claude-haiku-5-5").invoke("hi")
    assert haiku.calls[0][0] == "plain" and "fallbacks" not in haiku.calls[0][1]

    monkeypatch.setattr(P, "_anthropic_client", lambda key: FakeClaude(refusal=True))
    with pytest.raises(RuntimeError, match="declined"):
        P.build_llm("anthropic", "sk-ant-abcdefgh", "claude-opus-5-5").invoke("hi")


def test_claude_retries_plainly_only_when_fallbacks_are_rejected(monkeypatch):
    rejected = FakeClaude(beta_error=claude_bad_request("fallbacks: beta not enabled"))
    monkeypatch.setattr(P, "_anthropic_client", lambda key: rejected)
    assert P.build_llm("anthropic", "sk-ant-abcdefgh", "claude-opus-5-5").invoke("hi").content == "from claude"
    assert [path for path, _ in rejected.calls] == ["beta", "plain"]

    other = FakeClaude(beta_error=claude_bad_request("messages: too long"))
    monkeypatch.setattr(P, "_anthropic_client", lambda key: other)
    with pytest.raises(Exception, match="too long"):
        P.build_llm("anthropic", "sk-ant-abcdefgh", "claude-opus-5-5").invoke("hi")
    assert [path for path, _ in other.calls] == ["beta"]


def test_chain_errors_never_contain_the_key(monkeypatch):
    monkeypatch.setattr(P, "_anthropic_client", lambda key: FakeClaude(beta_error=claude_bad_request("invalid x-api-key sk-ant-SECRETSECRET123")))
    chain = Chain("sk-ant-abcdefgh", "claude-opus-5-5", provider="anthropic")
    mail = chain.write_mail(SAMPLE_JOB, [], "Alex", "Acme", "BD", "Friendly", 100)
    assert mail.startswith("Subject:")  # built-in template used
    assert "SECRET" not in chain.last_error and "[REDACTED]" in chain.last_error


@pytest.mark.parametrize("raw,expected", [
    ("AuthenticationError: Error code: 401 - invalid api key", "key was rejected"),
    ("RateLimitError: Error code: 429 - rate limit reached", "Wait a minute"),
    ("You exceeded your current quota, please check your plan and billing details", "no credit left"),
    ("BadRequestError: model `x` does not exist", "Pick a different model"),
    ("APITimeoutError: Request timed out.", "took too long"),
    ("RuntimeError: Claude declined this request (policy).", "declined"),
    ("OutputParserException: Invalid json output", "unexpected format"),
    ("ValueError: something unusual", ""),
])
def test_errors_get_plain_explanations(raw, expected):
    explanation = P.explain_error(raw)
    assert (expected in explanation) if expected else explanation == ""


def test_groq_calls_have_a_timeout():
    assert P.build_llm("groq", "gsk_abc", "m").request_timeout == P.REQUEST_TIMEOUT_SECONDS
