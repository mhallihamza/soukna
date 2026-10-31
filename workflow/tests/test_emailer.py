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


# --- Voie Brevo (HTTPS API) ---------------------------------------------

def _setup_brevo(monkeypatch, status=201, payload=None):
    monkeypatch.setattr(emailer.config, "BREVO_API_KEY", "xkeysib-test")
    monkeypatch.setattr(emailer.config, "SMTP_FROM", "u@gmail.com")
    sent = {}

    class _R:
        status_code = status
        headers = {"content-type": "application/json"}
        @staticmethod
        def json():
            return payload or {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"], sent["headers"], sent["json"] = url, headers, json
        return _R()

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    return sent


def test_brevo_success(monkeypatch):
    sent = _setup_brevo(monkeypatch)
    ok, detail = emailer.send_email_html("a@b.c", "Sujet", "<p>hi</p>")
    assert ok is True and detail == "sent(brevo)"
    assert sent["url"].endswith("/v3/smtp/email")
    assert sent["headers"]["api-key"] == "xkeysib-test"
    assert sent["json"]["to"] == [{"email": "a@b.c"}]
    assert sent["json"]["htmlContent"] == "<p>hi</p>"


def test_brevo_api_error(monkeypatch):
    _setup_brevo(monkeypatch, status=400, payload={"message": "invalid key"})
    ok, detail = emailer.send_email_html("a@b.c", "Sujet", "<p>x</p>")
    assert ok is False and "brevo_400" in detail and "invalid key" in detail


def test_brevo_network_error(monkeypatch):
    _setup_brevo(monkeypatch)
    def boom(*a, **k):
        raise emailer.requests.RequestException("down")
    monkeypatch.setattr(emailer.requests, "post", boom)
    ok, detail = emailer.send_email_html("a@b.c", "Sujet", "<p>x</p>")
    assert ok is False and detail == "brevo_network:RequestException"


def test_no_brevo_key_falls_back_to_smtp(monkeypatch):
    monkeypatch.setattr(emailer.config, "BREVO_API_KEY", "")
    _setup(monkeypatch, 587)  # SMTP factice du haut du fichier
    ok, detail = emailer.send_email("a@b.c", "s", "body")
    assert ok is True and detail == "sent"


# --- Voie Resend (HTTPS API, alternative à Brevo) ------------------------

def _setup_resend(monkeypatch, status=200, payload=None):
    monkeypatch.setattr(emailer.config, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(emailer.config, "SMTP_FROM", "u@gmail.com")
    sent = {}

    class _R:
        status_code = status
        headers = {"content-type": "application/json"}
        @staticmethod
        def json():
            return payload or {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"], sent["headers"], sent["json"] = url, headers, json
        return _R()

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    return sent


def test_resend_success_takes_priority(monkeypatch):
    _setup_brevo(monkeypatch)  # les deux configurés : resend gagne
    sent = _setup_resend(monkeypatch)  # son fake post est appliqué en dernier
    ok, detail = emailer.send_email_html("a@b.c", "Sujet", "<p>hi</p>")
    assert ok is True and detail == "sent(resend)"
    assert sent["url"].endswith("/emails")
    assert sent["headers"]["Authorization"] == "Bearer re_test"
    assert sent["json"]["to"] == ["a@b.c"]


def test_resend_error_detail(monkeypatch):
    _setup_resend(monkeypatch, status=403,
                  payload={"message": "You can only send to your own email"})
    ok, detail = emailer.send_email_html("a@b.c", "Sujet", "<p>x</p>")
    assert ok is False and "resend_403" in detail and "own email" in detail


def test_resend_plain_text_variant(monkeypatch):
    sent = _setup_resend(monkeypatch)
    ok, _ = emailer.send_email("a@b.c", "Sujet", "corps texte")
    assert ok is True
    assert sent["json"]["text"] == "corps texte"
