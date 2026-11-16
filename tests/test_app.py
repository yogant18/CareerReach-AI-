"""
End-to-end tests that run the real Streamlit app in Streamlit's test harness,
with the AI model replaced by a scripted stand-in.
"""

import os

import pytest
from streamlit.testing.v1 import AppTest

from app import chains
from conftest import ROOT, scripted_llm

MAIN = os.path.join(ROOT, "app", "main.py")

RULES = [
    ("Extract all job postings", '[{"role":"ML Engineer","experience":"3+ years","skills":["Python","AWS","Rust"],"description":"Builds ML pipelines"}]'),
    ("subject lines for the cold email", '[{"subject":"AI subject one","why":"because"},{"subject":"AI subject two","why":"reason"}]'),
    ("short follow-up emails", '[{"day":3,"subject":"Re: ML","body":"F1 body"},{"day":7,"subject":"Re: ML","body":"F2 body"},{"day":14,"subject":"Re: ML","body":"F3 body"}]'),
    ("two LinkedIn messages", '{"note":"Short note about the ML role.","inmail_subject":"ML role","inmail_body":"InMail body text."}'),
    ("CHANGE REQUESTED", "Subject: Original subject\n\nRewritten shorter body.\n\nAlex"),
    ("CANDIDATE RESUME", "Subject: Application subject\n\nApplication body based on my resume.\n\nAlex"),
]
DEFAULT = "Subject: Original subject\n\nHi there,\n\nOriginal body.\n\nAlex"


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The app on the free trial, with a scripted model and its data files in a temp folder."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake_for_tests")
    monkeypatch.setenv("USAGE_STORE_PATH", str(tmp_path / "usage.json"))
    monkeypatch.setenv("FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    monkeypatch.setenv("USAGE_SALT", "test-salt")
    for name in ("FREE_EMAILS_PER_DAY", "FREE_CHATS_PER_DAY", "FREE_GLOBAL_DAILY_CAP", "FREE_TRIAL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    prompts = []
    monkeypatch.setattr(chains, "build_llm", lambda provider, key, model, temperature=0.2: scripted_llm(RULES, DEFAULT, prompts))
    import streamlit as st
    st.cache_resource.clear()
    st.cache_data.clear()
    at = AppTest.from_file(MAIN, default_timeout=180).run()
    at.prompts = prompts
    at.tmp_path = tmp_path
    return at


def button(at, label):
    return [b for b in at.button if b.label == label][0]


def email_box(at):
    return [t for t in at.text_area if t.label.startswith("Cold Email")][0]


def linkedin_note(at):
    boxes = [t for t in at.text_area if t.label == "LinkedIn connection note"]
    return boxes[0].value if boxes else None


def no_errors(at):
    assert [e.value for e in at.exception] == []


def fill_agency_profile(at):
    for field in at.sidebar.text_input:
        if field.label.startswith("Your / Sender"):
            field.set_value("Alex")
        if field.label == "Your Company":
            field.set_value("Acme")


def generate_from_description(at):
    [r for r in at.radio if r.label == "Choose Input Method:"][0].set_value("Paste Job Description Directly").run()
    button(at, "Generate from Description").click().run()
    return at


def test_app_loads_on_the_free_trial(app):
    no_errors(app)
    assert app.radio(key="access_mode").options == ["Free trial", "Use my own API key"]
    assert any("7/7 emails" in m.value and "unlimited chat" in m.value for m in app.sidebar.markdown)


def test_generation_requires_a_sender_profile(app):
    generate_from_description(app)
    no_errors(app)
    assert any("Sender Name and Company" in e.value for e in app.error)
    assert not [t for t in app.text_area if t.label.startswith("Cold Email")]


def test_email_tools_flow(app):
    fill_agency_profile(app)
    generate_from_description(app)
    no_errors(app)
    assert email_box(app).value.startswith("Subject: Original subject")
    assert {"Open in Gmail", "Open in Outlook", "Mail app"} <= {link.label for link in app.get("link_button")}
    assert any("6/7 emails" in m.value for m in app.sidebar.markdown)

    app.run()  # results survive a rerun
    email_box(app).set_value(email_box(app).value + "\nPS edited by hand").run()

    button(app, "Suggest 5 subject lines").click().run()
    [b for b in app.button if b.label == "Use"][1].click().run()
    assert email_box(app).value.startswith("Subject: AI subject two") and "PS edited by hand" in email_box(app).value

    button(app, "Shorter").click().run()
    assert "Rewritten shorter body." in email_box(app).value
    button(app, "Undo").click().run()
    assert email_box(app).value.startswith("Subject: AI subject two")

    button(app, "Write follow-ups").click().run()
    assert [t.value for t in app.text_area if t.label.startswith("Follow-up")] == ["F1 body", "F2 body", "F3 body"]

    # LinkedIn messages were written with the email and are shown without any extra click
    assert linkedin_note(app) == "Short note about the ML role."
    assert any("/ 300 characters" in c.value for c in app.caption)
    assert "Open LinkedIn" in {link.label for link in app.get("link_button")}
    button(app, "Rewrite from current email").click().run()
    no_errors(app)
    assert linkedin_note(app) == "Short note about the ML role."

    app.get("feedback")[0].set_value(1).run()
    assert '"rating": "up"' in (app.tmp_path / "feedback.jsonl").read_text()
    assert any("6/7 emails" in m.value for m in app.sidebar.markdown)  # the tools did not use email credits

    button(app, "Clear results").click().run()
    no_errors(app)
    assert not [t for t in app.text_area if t.label.startswith("Cold Email")]


def test_free_trial_stops_after_the_daily_limit(app, monkeypatch):
    monkeypatch.setenv("FREE_EMAILS_PER_DAY", "1")
    import streamlit as st
    st.cache_resource.clear()
    app.run()
    fill_agency_profile(app)
    generate_from_description(app)
    assert email_box(app).value
    button(app, "Generate from Description").click().run()
    no_errors(app)
    assert any("Free limit reached" in m.value for m in app.markdown)


def test_chat_is_not_limited_and_input_stays_below_messages(app):
    app.chat_input[0].set_value("hi").run()
    no_errors(app)
    assert [m.name for m in app.chat_message] == ["assistant", "user", "assistant"]
    assert not (app.tmp_path / "usage.json").exists()  # chat is not metered


def test_job_seeker_mode_uses_resume_and_shows_match(app):
    app.radio(key="writer_mode").set_value("A job seeker").run()
    generate_from_description(app)
    assert any("add your name" in e.value for e in app.error)

    app.text_input(key="seeker_name").set_value("Alex").run()
    button(app, "Generate from Description").click().run()
    assert any("resume" in e.value for e in app.error)

    resume = "Data engineer with four years of Python and Amazon Web Services experience building ETL pipelines at Initech."
    app.text_area(key="resume_pasted").set_value(resume).run()
    button(app, "Generate from Description").click().run()
    no_errors(app)
    assert email_box(app).value.startswith("Subject: Application subject")
    assert any("Initech" in p for p in app.prompts)
    match = [m.value for m in app.markdown if "Skill match" in m.value][0]
    assert "Skill match: 67%" in match and "2 of 3 skills found in your resume" in match
    assert "badge-miss" in match and "Rust" in match


def test_each_visitor_has_a_private_portfolio(app):
    def add_item(at, tech, link):
        fields = {f.label: f for f in at.text_input}
        fields["Techstack / Skills (e.g. Next.js, FastAPI, PostgreSQL)"].set_value(tech)
        fields["Portfolio / Case Study URL"].set_value(link)
        button(at, "Add to Database").click().run()

    def count(at):
        return [m.value for m in at.sidebar.markdown if "indexed" in m.value][0]

    other = AppTest.from_file(MAIN, default_timeout=180).run()
    add_item(app, "Python, FastAPI", "https://a.example/1")
    other.run()
    assert count(app).startswith("**1** item") and count(other).startswith("**0** items")
    button(other, "Clear Portfolio").click().run()
    app.run()
    assert count(app).startswith("**1** item")


def test_own_key_mode_offers_all_providers(app):
    app.radio(key="access_mode").set_value("Use my own API key").run()
    assert app.selectbox(key="provider_choice").options == ["Groq (free)", "OpenAI (ChatGPT)", "Google Gemini", "Anthropic (Claude)"]
    app.selectbox(key="provider_choice").set_value("anthropic").run()
    no_errors(app)
    assert app.selectbox(key="model_choice_anthropic").options[0] == "claude-opus-5-5"
    assert not app.sidebar.slider  # Claude has no temperature setting
    app.text_input(key="user_key_anthropic").set_value("sk-wrong").run()
    assert any("doesn't look like a Claude key" in e.value for e in app.sidebar.error)


def test_text_from_web_pages_cannot_inject_markdown(app, monkeypatch):
    hostile = '[{"role":"Engineer [click here](http://evil.example)","experience":"![x](http://evil.example/p.png)","skills":["Python"],"description":"**bold** <b>html</b>"}]'
    monkeypatch.setattr(chains, "build_llm", lambda provider, key, model, temperature=0.2: scripted_llm([("Extract all job postings", hostile)], DEFAULT))
    fill_agency_profile(app)
    generate_from_description(app)
    no_errors(app)
    heading = [m.value for m in app.markdown if m.value.startswith("#### Job #1")][0]
    assert r"\[click here\]" in heading and "[click here](" not in heading
    assert any(r"\!\[x\]" in m.value for m in app.markdown)


def test_sample_url_button_uses_a_live_posting(app, monkeypatch):
    import streamlit as st
    from app import utils
    monkeypatch.setattr(utils, "find_sample_job_url", lambda: "https://boards.greenhouse.io/acme/jobs/42")
    st.cache_data.clear()
    app.run()  # the button's callback is bound on the run before the click
    button(app, "Use Sample URL").click().run()
    no_errors(app)
    assert app.text_input(key="url_input").value == "https://boards.greenhouse.io/acme/jobs/42"


def test_linkedin_is_offered_up_front(app):
    choice = app.radio(key="output_choice")
    assert choice.options == ["Email + LinkedIn messages", "Email only", "LinkedIn messages only"]
    assert choice.value == "Email + LinkedIn messages"
    assert "Email & LinkedIn Generator" in [tab.label for tab in app.tabs]


def test_email_only_keeps_linkedin_optional(app):
    fill_agency_profile(app)
    app.radio(key="output_choice").set_value("Email only").run()
    generate_from_description(app)
    no_errors(app)
    assert email_box(app).value and linkedin_note(app) is None
    assert not any("two LinkedIn messages" in p for p in app.prompts)  # no LinkedIn call was made
    button(app, "Write LinkedIn messages").click().run()
    assert linkedin_note(app) == "Short note about the ML role."


def test_linkedin_only_shows_linkedin_first(app):
    fill_agency_profile(app)
    app.radio(key="output_choice").set_value("LinkedIn messages only").run()
    generate_from_description(app)
    no_errors(app)
    assert linkedin_note(app) == "Short note about the ML role."
    headings = [m.value for m in app.markdown]
    card = next(i for i, v in enumerate(headings) if "cr-li-title" in v)
    email_heading = next(i for i, v in enumerate(headings) if v == "##### Email version")
    assert card < email_heading and email_box(app).value
