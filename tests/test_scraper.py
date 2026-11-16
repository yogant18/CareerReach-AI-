"""Tests for the job-posting scraper. No test here touches the network."""

import pytest

from app import utils
from app.utils import ScrapeError, clean_text, is_safe_url, job_board_api, scrape_website


class FakeResponse:
    def __init__(self, status=200, body=b"", content_type="text/html", json_data=None):
        self.status_code = status
        self.content = body
        self.headers = {"Content-Type": content_type}
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


@pytest.fixture
def fake_web(monkeypatch):
    """Route scraper fetches to canned responses keyed by URL, and treat every host as public."""
    pages, fetched = {}, []

    def fake_fetch(url, accept=""):
        fetched.append(url)
        if url not in pages:
            return FakeResponse(status=404)
        return pages[url]

    monkeypatch.setattr(utils, "_fetch", fake_fetch)
    monkeypatch.setattr(utils, "is_safe_url", lambda url: True)
    return pages, fetched


LONG_TEXT = "We are hiring a Senior Data Engineer to build streaming pipelines with Python, Spark and Kafka. " * 4


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/acme/jobs/123", ("Greenhouse", "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123")),
    ("https://job-boards.greenhouse.io/acme/jobs/123?gh_src=x", ("Greenhouse", "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123")),
    ("https://boards.greenhouse.io/embed/job_app?for=acme&token=456", ("Greenhouse", "https://boards-api.greenhouse.io/v1/boards/acme/jobs/456")),
    ("https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd/apply", ("Lever", "https://api.lever.co/v0/postings/acme/6ed76ce8-4156-4b60-b120-403538bd66cd")),
    ("https://jobs.eu.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd", ("Lever", "https://api.eu.lever.co/v0/postings/acme/6ed76ce8-4156-4b60-b120-403538bd66cd")),
    ("https://nike.wd1.myworkdayjobs.com/en-US/nke/job/Beaverton-OR/Engineer_R-1", ("Workday", "https://nike.wd1.myworkdayjobs.com/wday/cxs/nike/nke/job/Beaverton-OR/Engineer_R-1")),
    ("https://example.com/jobs/1", None),
    ("https://jobs.lever.co/acme", None),
    ("https://boards.greenhouse.io/acme", None),
])
def test_job_board_api_mapping(url, expected):
    assert job_board_api(url) == expected


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost:8501", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data",
    "ftp://example.com/file", "file:///etc/passwd", "", "not a url",
])
def test_unsafe_urls_are_rejected(url):
    assert not is_safe_url(url)
    with pytest.raises(ScrapeError):
        scrape_website(url)


def test_greenhouse_posting_is_read_from_the_api(fake_web):
    pages, fetched = fake_web
    pages["https://boards-api.greenhouse.io/v1/boards/acme/jobs/123"] = FakeResponse(json_data={
        "title": "Data Engineer", "company_name": "Acme", "location": {"name": "Pune"},
        "content": "&lt;p&gt;" + LONG_TEXT + "&lt;/p&gt;",
    })
    text = scrape_website("https://boards.greenhouse.io/acme/jobs/123")
    assert text.startswith("Job title: Data Engineer. Company: Acme. Location: Pune.")
    assert "streaming pipelines" in text and "<p>" not in text and "&lt;" not in text
    assert fetched == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/123"]


def test_lever_and_workday_postings(fake_web):
    pages, _ = fake_web
    pages["https://api.lever.co/v0/postings/acme/6ed76ce8-4156-4b60-b120-403538bd66cd"] = FakeResponse(json_data={
        "text": "ML Engineer", "categories": {"team": "AI", "location": "Remote", "commitment": "Full-time"},
        "descriptionPlain": LONG_TEXT, "lists": [{"text": "Requirements", "content": "<li>PyTorch</li>"}],
        "additionalPlain": "Equal opportunity employer.",
    })
    lever = scrape_website("https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd")
    assert "Job title: ML Engineer." in lever and "Requirements: PyTorch" in lever and "Equal opportunity" in lever

    pages["https://acme.wd1.myworkdayjobs.com/wday/cxs/acme/careers/job/Pune/Dev_R1"] = FakeResponse(json_data={
        "jobPostingInfo": {"title": "Developer", "location": "Pune", "timeType": "Full time", "jobDescription": f"<div>{LONG_TEXT}</div>"},
    })
    workday = scrape_website("https://acme.wd1.myworkdayjobs.com/en-US/careers/job/Pune/Dev_R1")
    assert "Job title: Developer. Location: Pune. Time type: Full time." in workday and "Kafka" in workday


def test_falls_back_to_the_page_when_the_board_api_fails(fake_web):
    pages, fetched = fake_web
    url = "https://boards.greenhouse.io/acme/jobs/123"
    pages[url] = FakeResponse(body=f"<html><body><main>{LONG_TEXT}</main></body></html>".encode())
    assert "streaming pipelines" in scrape_website(url)
    assert fetched == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/123", url]


def test_structured_data_is_preferred_over_page_chrome(fake_web):
    pages, _ = fake_web
    html = f"""<html><head><script type="application/ld+json">
      {{"@context":"https://schema.org","@graph":[{{"@type":"WebSite"}},
        {{"@type":"JobPosting","title":"Backend Engineer","hiringOrganization":{{"name":"Acme"}},
          "employmentType":"FULL_TIME","description":"<p>{LONG_TEXT}</p>"}}]}}
      </script></head><body><nav>Home Careers</nav><div id="app"></div>
      <p>Cookie banner text that should not be used.</p></body></html>"""
    pages["https://acme.example/careers/1"] = FakeResponse(body=html.encode())
    text = scrape_website("https://acme.example/careers/1")
    assert text.startswith("Job title: Backend Engineer. Company: Acme. Employment type: FULL_TIME.")
    assert "Cookie banner" not in text


def test_plain_page_text_drops_scripts_and_navigation(fake_web):
    pages, _ = fake_web
    html = f"<html><body><nav>MENU</nav><script>var secret=1</script><main>{LONG_TEXT}</main><footer>FOOT</footer></body></html>"
    pages["https://acme.example/job"] = FakeResponse(body=html.encode())
    text = scrape_website("https://acme.example/job")
    assert "streaming pipelines" in text and "MENU" not in text and "secret" not in text and "FOOT" not in text


@pytest.mark.parametrize("response,expected", [
    (FakeResponse(status=403), "blocks automated readers"),
    (FakeResponse(status=429), "blocks automated readers"),
    (FakeResponse(status=404), "not found"),
    (FakeResponse(status=500), "returned an error"),
    (FakeResponse(body=b"%PDF-1.7", content_type="application/pdf"), "not a web page"),
    (FakeResponse(body=b"<html><body><div id='root'></div></body></html>"), "JavaScript"),
])
def test_failures_give_clear_messages(fake_web, response, expected):
    pages, _ = fake_web
    pages["https://acme.example/job"] = response
    with pytest.raises(ScrapeError) as err:
        scrape_website("https://acme.example/job")
    assert expected in str(err.value) and "Paste Job Description Directly" in str(err.value)


def test_long_pages_are_trimmed(fake_web):
    pages, _ = fake_web
    pages["https://acme.example/job"] = FakeResponse(body=("<p>" + LONG_TEXT * 100 + "</p>").encode())
    assert len(scrape_website("https://acme.example/job")) == utils.MAX_TEXT_CHARS


def test_redirect_to_private_address_is_blocked(monkeypatch):
    class Redirect:
        is_redirect, is_permanent_redirect = True, False
        headers = {"Location": "http://127.0.0.1/secret"}
        def close(self): pass

    monkeypatch.setattr(utils, "is_safe_url", lambda url: "127.0.0.1" not in url)
    monkeypatch.setattr(utils.requests, "get", lambda *a, **k: Redirect())
    with pytest.raises(ScrapeError) as err:
        utils._fetch("https://public.example/job")
    assert "not allowed" in str(err.value)


def test_clean_text_strips_tags_and_urls():
    assert clean_text("<b>Hello</b>   world https://x.example/a?b=1 ok") == "Hello world ok"


def test_sample_job_url_prefers_an_engineering_role_and_survives_failures(fake_web):
    pages, _ = fake_web
    assert utils.find_sample_job_url() is None  # every board unavailable
    pages["https://boards-api.greenhouse.io/v1/boards/airbnb/jobs"] = FakeResponse(json_data={"jobs": [
        {"id": 11, "title": "Account Executive"}, {"id": 22, "title": "Senior Software Engineer"},
    ]})
    assert utils.find_sample_job_url() == "https://boards.greenhouse.io/airbnb/jobs/22"
    assert job_board_api(utils.find_sample_job_url())[0] == "Greenhouse"
