# =====================================================================
# Canal email : sélection du port (465 = SSL implicite, 587 = starttls)
# et détails d'erreur diagnostiques (hébergeurs qui bloquent le SMTP
# sortant). 100 % hors-ligne : smtplib est monkeypatché.
# =====================================================================
from soukna_graph import config
from soukna_graph.tools import emailer


class _FakeSMTP:
    """Context manager SMTP factice qui enregistre son type et ses appels."""

    calls: list[str] = []

    def __init__(self, host, port, timeout=None, ssl=False):
        _FakeSMTP.calls.append(f"connect:{port}:{ssl}")
        self._need_tls = not ssl

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        _FakeSMTP.calls.append("starttls")

    def login(self, user, password):
        _FakeSMTP.calls.append("login")

    def sendmail(self, frm, to, data):
        _FakeSMTP.calls.append("send")


def _setup(monkeypatch, port: int):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(config, "SMTP_PORT", port)
    monkeypatch.setattr(config, "SMTP_USER", "u@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "app-pass")
    monkeypatch.setattr(config, "SMTP_FROM", "u@gmail.com")
    monkeypatch.setattr(emailer.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(emailer.smtplib, "SMTP_SSL",
                        lambda h, p, timeout=None: _FakeSMTP(h, p, ssl=True))
    _FakeSMTP.calls = []


def test_port_587_uses_starttls(monkeypatch):
    _setup(monkeypatch, 587)
    ok, detail = emailer.send_email("a@b.c", "s", "body")
    assert ok is True and detail == "sent"
    assert _FakeSMTP.calls == ["connect:587:False", "starttls", "login", "send"]


def test_port_465_uses_ssl(monkeypatch):
    _setup(monkeypatch, 465)
    ok, detail = emailer.send_email("a@b.c", "s", "body")
    assert ok is True and detail == "sent"
    assert _FakeSMTP.calls == ["connect:465:True", "login", "send"]


def test_connection_error_returns_os_detail(monkeypatch):
    _setup(monkeypatch, 587)

    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(emailer.smtplib, "SMTP", boom)
    ok, detail = emailer.send_email("a@b.c", "s", "body")
    assert ok is False
    assert "smtp:OSError" in detail and "Network is unreachable" in detail


def test_empty_recipient_is_distinct_error(monkeypatch):
    _setup(monkeypatch, 587)
    ok, detail = emailer.send_email("", "s", "body")
    assert ok is False and detail == "recipient_missing"


def test_not_configured_when_host_missing(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "")
    ok, detail = emailer.send_email("a@b.c", "s", "body")
    assert ok is False and detail == "email_not_configured"


def test_html_variant_same_behaviour(monkeypatch):
    _setup(monkeypatch, 465)
    ok, detail = emailer.send_email_html("a@b.c", "s", "<p>hi</p>")
    assert ok is True and detail == "sent"
    assert _FakeSMTP.calls == ["connect:465:True", "login", "send"]
