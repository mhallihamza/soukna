# =====================================================================
# API Soukna : webhook WhatsApp (format Meta) + REST du dashboard.
# Auth : token HMAC signé (AUTH_SECRET), rôles admin / entreprise.
# =====================================================================
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from soukna_graph import config, db, monitoring
from soukna_graph.graph import build_graph
from soukna_graph.tools import emailer

app = FastAPI(title="Soukna Workflow API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH = build_graph()


@app.on_event("startup")
def startup() -> None:
    try:
        db.init_db()
        # Seed du compte admin en base (table users) si vide : les
        # credentials dashboard vivent en DB, l'env ne sert qu'au bootstrap.
        if db.count_users() == 0:
            db.create_user(
                config.ADMIN_USERNAME,
                _hash_password(config.ADMIN_PASSWORD),
                role="admin",
            )
            print(f"[soukna] admin user créé en base : {config.ADMIN_USERNAME}")
    except Exception as exc:  # Supabase indisponible : l'API reste debout
        print(f"[soukna] init_db warning: {exc}")


# -----------------------------------------------------------------------
# Auth (token HMAC : payload_b64.signature)
# -----------------------------------------------------------------------

def _sign(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    sig = hmac.new(config.AUTH_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _verify(token: str) -> dict[str, Any] | None:
    try:
        b64, sig = token.rsplit(".", 1)
        expected = hmac.new(config.AUTH_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padding = "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(b64 + padding))
        if float(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except (ValueError, KeyError, TypeError):
        return None


_bearer = HTTPBearer(auto_error=False)


def _check(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(401, "Token manquant")
    payload = _verify(creds.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    return payload


def require_admin(payload: dict[str, Any] = Depends(_check)) -> dict[str, Any]:
    if payload.get("role") != "admin":
        raise HTTPException(403, "Réservé au rôle admin")
    return payload


def require_entreprise(payload: dict[str, Any] = Depends(_check)) -> dict[str, Any]:
    if payload.get("role") != "entreprise":
        raise HTTPException(403, "Réservé au rôle entreprise")
    company = db.get_company(payload.get("company_id", ""))
    if not company:
        raise HTTPException(401, "Entreprise introuvable")
    return company


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _public_company(company: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in company.items() if k != "password_hash"}


class LoginBody(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str


class CompanyBody(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str | None = None
    sectors: list[str] = []
    keywords: list[str] = []
    regions: list[str] = []
    size: str = "pme"
    plan: str = "decouverte"
    channel_whatsapp: bool = False
    channel_email: bool = False


class CompanyAdminPatch(BaseModel):
    plan: str | None = None    # decouverte | pro | business
    status: str | None = None  # active | suspended


class ConfigPatch(BaseModel):
    portal_enabled: bool | None = None
    llm_enabled: bool | None = None
    kill_switch: bool | None = None


class WaitlistNoteBody(BaseModel):
    admin_note: str


class OnboardingBody(BaseModel):
    password: str
    company_name: str
    sector: str
    cities: list[str] = []
    keywords: list[str] = []
    size: str = "pme"
    whatsapp: str | None = None
    lang: str = "fr"


class ProfilePatch(BaseModel):
    name: str | None = None
    sectors: list[str] | None = None
    keywords: list[str] | None = None
    regions: list[str] | None = None
    size: str | None = None
    channel_whatsapp: bool | None = None
    channel_email: bool | None = None
    max_guarantee: int | None = None
    alert_min_score: int | None = None


class MatchPatch(BaseModel):
    saved: bool | None = None
    status: str | None = None   # study | prep | submitted | new
    note: str | None = None


@app.post("/auth/login")
def login(body: LoginBody) -> dict[str, Any]:
    exp = time.time() + config.TOKEN_TTL_HOURS * 3600
    # Le formulaire n'a qu'un champ : username sert aussi d'email entreprise.
    email = body.email or body.username

    # 1) Users dashboard (table users, rôles en base).
    if email:
        user = db.get_user_by_email(email)
        if user and user.get("password_hash") == _hash_password(body.password):
            return {"token": _sign({
                "role": user.get("role", "admin"), "sub": email, "exp": exp,
            }), "role": user.get("role", "admin")}

    # 2) Repli admin via .env (bootstrap avant premier seed).
    if body.username and body.username == config.ADMIN_USERNAME \
            and body.password == config.ADMIN_PASSWORD:
        return {"token": _sign({"role": "admin", "sub": body.username, "exp": exp}),
                "role": "admin"}

    # 3) Entreprises (table companies).
    if email:
        rows = db.query("SELECT * FROM companies WHERE email = %s", (email,))
        if rows and rows[0].get("password_hash") == _hash_password(body.password):
            company = rows[0]
            if company.get("status") == "suspended":
                raise HTTPException(403, "Compte suspendu — contactez Soukna")
            return {
                "token": _sign({
                    "role": "entreprise",
                    "sub": email,
                    "company_id": str(company["id"]),
                    "exp": exp,
                }),
                "role": "entreprise",
            }
    raise HTTPException(401, "Identifiants invalides")


# -----------------------------------------------------------------------
# Webhook WhatsApp (format Meta Cloud API)
# -----------------------------------------------------------------------

def extract_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {}) or {}
            contacts = value.get("contacts") or [{}]
            name = (contacts[0].get("profile") or {}).get("name", "")
            for msg in value.get("messages") or []:
                out.append({
                    "message_id": msg.get("id", ""),
                    "sender": msg.get("from", ""),
                    "text": (msg.get("text") or {}).get("body", ""),
                    "name": name,
                })
    return out


@app.get("/webhook")
def webhook_verify(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge or 0)
    raise HTTPException(403, "verify token invalide")


async def process_incoming(msg: dict[str, str]) -> None:
    state: dict[str, Any] = {
        "message": msg["text"],
        "sender_phone": msg["sender"],
        "sender_name": msg.get("name", ""),
        "message_id": msg["message_id"],
    }
    try:
        result = await GRAPH.ainvoke(state)
        request_id = result.get("request_id")
        if request_id:
            db.finalize_request(
                request_id, route=result.get("route", "?"), outcome="ok",
                llm_usage=result.get("llm_usage"),
            )
    except Exception as exc:
        try:
            rid = db.start_request(
                msg.get("message_id") or f"err-{uuid.uuid4()}", msg.get("sender", ""),
            )
            db.finalize_request(rid, route="error", outcome="error", error=str(exc)[:300])
        except Exception:
            pass


@app.post("/webhook")
async def webhook(payload: dict[str, Any], tasks: BackgroundTasks) -> dict[str, bool]:
    for msg in extract_messages(payload):
        if msg["text"]:
            tasks.add_task(process_incoming, msg)
    return {"received": True}


# -----------------------------------------------------------------------
# Pipeline (admin)
# -----------------------------------------------------------------------

@app.post("/run")
async def run_pipeline_endpoint(_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    run_id = db.start_pipeline_run()
    try:
        result = await GRAPH.ainvoke({
            "run_pipeline": True,
            "sender_phone": "system",
            "message_id": f"pipeline-{uuid.uuid4()}",
        })
        matches = result.get("matches") or []
        db.finish_pipeline_run(
            run_id,
            source_mode=result.get("source_mode", "?"),
            ingested=result.get("ingested", 0),
            matched=len(matches),
            verdicted=len(matches),
            digests=len(result.get("delivered") or []),
        )
        request_id = result.get("request_id")
        if request_id:
            db.finalize_request(request_id, route="pipeline", outcome="ok",
                                llm_usage=result.get("llm_usage"))
        return {
            "status": "ok",
            "source_mode": result.get("source_mode"),
            "ingested": result.get("ingested", 0),
            "matches": len(matches),
            "digests": len(result.get("delivered") or []),
        }
    except Exception as exc:
        db.finish_pipeline_run(
            run_id, source_mode="?", ingested=0, matched=0, verdicted=0,
            digests=0, status="error", error=str(exc)[:300],
        )
        raise HTTPException(500, str(exc)[:300]) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "soukna-workflow"}


# -----------------------------------------------------------------------
# Dashboard : profil, opportunités, digests (entreprise)
# -----------------------------------------------------------------------

@app.get("/profile")
def get_profile(company: dict[str, Any] = Depends(require_entreprise)) -> dict[str, Any]:
    return _public_company(company)


@app.patch("/profile")
def patch_profile(patch: ProfilePatch,
                  company: dict[str, Any] = Depends(require_entreprise)) -> dict[str, Any]:
    company_id = str(company["id"])
    if any(v is not None for v in (patch.name, patch.sectors, patch.keywords,
                                   patch.regions, patch.size, patch.max_guarantee,
                                   patch.alert_min_score)):
        db.update_company_profile(
            company_id,
            name=patch.name,
            sectors=patch.sectors,
            keywords=patch.keywords,
            regions=patch.regions,
            size=patch.size,
            max_guarantee=patch.max_guarantee,
            alert_min_score=patch.alert_min_score,
        )
    if patch.channel_whatsapp is not None or patch.channel_email is not None:
        db.set_channel_prefs(
            company_id,
            patch.channel_whatsapp if patch.channel_whatsapp is not None
            else bool(company["channel_whatsapp"]),
            patch.channel_email if patch.channel_email is not None
            else bool(company["channel_email"]),
        )
    return _public_company(db.get_company(company_id) or company)


@app.get("/opportunities")
def get_opportunities(
    min_score: int = 0,
    limit: int = 100,
    company: dict[str, Any] = Depends(require_entreprise),
) -> list[dict[str, Any]]:
    return db.matches_for_company(str(company["id"]), min_score=min_score, limit=limit)


@app.get("/digests")
def get_digests(company: dict[str, Any] = Depends(require_entreprise)) -> list[dict[str, Any]]:
    return db.digests_for_company(str(company["id"]))


@app.get("/company/stats")
def company_stats(company: dict[str, Any] = Depends(require_entreprise)) -> dict[str, Any]:
    stats = db.company_stats(str(company["id"]))
    stats["alert_min_score"] = company.get("alert_min_score") or 70
    return stats


@app.get("/notifications")
def notifications(company: dict[str, Any] = Depends(require_entreprise)) -> list[dict[str, Any]]:
    return db.notifications_for_company(str(company["id"]))


@app.patch("/matches/{match_id}")
def patch_match(match_id: str, patch: MatchPatch,
                company: dict[str, Any] = Depends(require_entreprise)) -> dict[str, Any]:
    if patch.status is not None and patch.status not in {"new", "study", "prep", "submitted"}:
        raise HTTPException(422, "status invalide (new|study|prep|submitted)")
    row = db.update_match(
        match_id, str(company["id"]),
        saved=patch.saved, status=patch.status, note=patch.note,
    )
    if not row:
        raise HTTPException(404, "Match introuvable pour cette entreprise")
    return row


# -----------------------------------------------------------------------
# Dashboard : administration (admin)
# -----------------------------------------------------------------------

@app.get("/companies")
def list_companies(_user: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return [_public_company(c) for c in db.list_companies()]


@app.post("/companies")
def create_company(body: CompanyBody,
                   _user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    company = db.upsert_company(
        name=body.name,
        email=body.email,
        phone=body.phone,
        password_hash=_hash_password(body.password) if body.password else None,
        sectors=body.sectors,
        keywords=body.keywords,
        regions=body.regions,
        size=body.size,
    )
    db.set_channel_prefs(str(company["id"]), body.channel_whatsapp, body.channel_email)
    if body.plan != "decouverte":
        db.update_company_admin(str(company["id"]), plan=body.plan)
    return _public_company(db.get_company(str(company["id"])) or company)


@app.patch("/companies/{company_id}")
def patch_company(company_id: str, patch: CompanyAdminPatch,
                  _user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    if patch.plan is not None and patch.plan not in {"decouverte", "pro", "business"}:
        raise HTTPException(422, "plan invalide (decouverte|pro|business)")
    if patch.status is not None and patch.status not in {"active", "suspended"}:
        raise HTTPException(422, "status invalide (active|suspended)")
    row = db.update_company_admin(company_id, plan=patch.plan, status=patch.status)
    if not row:
        raise HTTPException(404, "Entreprise introuvable")
    return _public_company(row)


@app.get("/admin/config")
def get_admin_config(_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return {
        "portal_enabled": bool(config.PORTAL_ENABLED),
        "llm_enabled": bool(config.LLM_ENABLED),
        "kill_switch": bool(config.KILL_SWITCH),
        "llm_key_present": bool(config.MISTRAL_API_KEY),
        "email_ready": config.email_ready(),
        "whatsapp_ready": bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID),
    }


@app.patch("/admin/config")
def patch_admin_config(patch: ConfigPatch,
                       _user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Interrupteurs runtime (sans redémarrage, non persistés en base)."""
    if patch.portal_enabled is not None:
        config.PORTAL_ENABLED = patch.portal_enabled
    if patch.llm_enabled is not None:
        config.LLM_ENABLED = patch.llm_enabled
    if patch.kill_switch is not None:
        config.KILL_SWITCH = patch.kill_switch
    return get_admin_config()


@app.get("/observability")
def observability(
    hours: float = 24,
    _user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    return {
        "requests": db.requests_since(hours),
        "logs": db.logs_since(hours),
    }


@app.get("/observability/summary")
def observability_summary(
    hours: float = 24,
    _user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Agrégats pour l'onglet Observabilité : agents, latences, pipeline."""
    requests = db.request_stats(hours)
    agents = db.agent_stats(hours)
    last_run = db.query(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    )
    return {
        "window_hours": hours,
        "requests": requests,
        "agents": agents,
        "last_pipeline_run": last_run[0] if last_run else None,
        "counts": db.query(
            """
            SELECT (SELECT count(*) FROM companies) AS companies,
                   (SELECT count(*) FROM companies WHERE status = 'active') AS companies_active,
                   (SELECT count(*) FROM companies WHERE plan IN ('pro','business')) AS companies_paying,
                   (SELECT count(*) FROM opportunities) AS opportunities,
                   (SELECT count(*) FROM matches) AS matches,
                   (SELECT count(*) FROM digests) AS digests,
                   (SELECT count(*) FROM waitlist) AS waitlist
            """
        )[0],
    }


@app.get("/monitoring/report")
def monitoring_report(_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Rapport de santé complet de l'agent de monitoring.

    Les alertes (email/WhatsApp) ne sont envoyées que par la tâche
    planifiée (scripts/monitor.py) — pas par la consultation du rapport.
    """
    report = monitoring.run_checks()
    report["last_alert"] = db.get_state("monitoring_alert")
    return report


@app.get("/observability/requests/{request_id}/logs")
def observability_trace(
    request_id: str,
    _user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Trace détaillée d'une requête : étapes agent par agent."""
    rows = db.query(
        "SELECT id, message_id, sender_phone, route, outcome, error, "
        "started_at, finished_at, latency_ms FROM lg_requests WHERE id = %s",
        (request_id,),
    )
    if not rows:
        raise HTTPException(404, "Requête introuvable")
    return {"request": rows[0], "steps": db.logs_for_request(request_id)}


# -----------------------------------------------------------------------
# Parcours client : waitlist → invitation → onboarding → essai 14 jours
# -----------------------------------------------------------------------

INVITE_DAYS = 7  # durée de validité du lien d'invitation
TRIAL_DAYS = 14


def _invite_email_html(company_name: str, link: str, lang: str) -> tuple[str, str]:
    """Email d'invitation court, dans la langue du client, un seul bouton."""
    if lang == "ar":
        subject = "فعّل حسابك على Soukna"
        html = f"""
        <div style="font-family:Arial,sans-serif;direction:rtl;text-align:right;max-width:520px;margin:auto;padding:24px;background:#fffdf9;border:1px solid #dcd6cb;border-radius:12px">
          <h2 style="color:#0f1e2e;margin:0 0 8px">مرحباً {company_name}،</h2>
          <p style="color:#66717b;font-size:14px;line-height:1.6">
            تمت دعوتك للانضمام إلى Soukna، منصة ذكاء طلبات العروض العمومية بالمغرب.
            اضغط على الزر لتأكيد ملف شركتك والبدء في تجربتك المجانية (14 يوماً).
          </p>
          <p style="text-align:center;margin:28px 0">
            <a href="{link}" style="background:#1f6b52;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">الدخول إلى Soukna</a>
          </p>
          <p style="color:#66717b;font-size:12px">هذا الرابط صالح لمدة {INVITE_DAYS} أيام ولمرة واحدة. إذا لم تطلب هذا الدعوة، تجاهل هذه الرسالة.</p>
        </div>"""
    else:
        subject = "Votre accès Soukna — activez votre compte"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:24px;background:#fffdf9;border:1px solid #dcd6cb;border-radius:12px">
          <h2 style="color:#0f1e2e;margin:0 0 8px">Bonjour {company_name},</h2>
          <p style="color:#66717b;font-size:14px;line-height:1.6">
            Vous êtes invité à rejoindre Soukna, l'intelligence des marchés publics
            au Maroc. Cliquez sur le bouton pour confirmer le profil de votre
            entreprise et démarrer votre essai gratuit (14 jours).
          </p>
          <p style="text-align:center;margin:28px 0">
            <a href="{link}" style="background:#1f6b52;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">Accéder à Soukna</a>
          </p>
          <p style="color:#66717b;font-size:12px">Ce lien est valable {INVITE_DAYS} jours et à usage unique. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>
        </div>"""
    return subject, html


def _do_invite(wid: str, admin_email: str) -> dict[str, Any]:
    """Logique partagée inviter / renvoyer : email + profil + statut + audit."""
    row = db.waitlist_row(wid)
    if not row:
        raise HTTPException(404, "Ligne d'attente introuvable")
    email = (row["email"] or "").strip().lower()
    lang = row.get("lang") or "fr"

    if row["status"] == "active":
        raise HTTPException(409, "Ce client est déjà actif — aucune nouvelle invitation.")
    if db.email_taken(email, exclude_waitlist_id=wid):
        raise HTTPException(
            409, "Un compte existe déjà pour cet email — invitation impossible (pas de doublon)."
        )

    # 1. Lien d'invitation à usage unique.
    token = db.create_invite_token(wid, email, days=INVITE_DAYS, created_by=admin_email)
    link = f"{config.APP_URL}/onboarding?token={token}"

    # 2. Email d'invitation dans la langue du client.
    subject, html = _invite_email_html(row["company_name"], link, lang)
    sent, detail = emailer.send_email_html(email, subject, html)

    # 3. Profil entreprise pré-rempli (échec email ⇒ statut inchangé).
    if sent:
        company = db.upsert_company(
            name=row["company_name"], email=email, phone=row.get("whatsapp"),
            sectors=[row["sector"]] if row.get("sector") else [],
            keywords=[], regions=[],
            size=row.get("company_size") or "pme",
        )
        db.execute(
            "UPDATE companies SET lang = %s, owner_email = %s, waitlist_id = %s, "
            "plan = 'trial' WHERE id = %s",
            (lang, email, wid, str(company["id"])),
        )
        db.waitlist_update(
            wid, status="invited", invited_at=db.utcnow(), invited_by=admin_email
        )
        db.audit(admin_email, "invite", wid, f"email envoyé à {email}")

    return {
        "row": db.waitlist_row(wid),
        "email_sent": sent,
        "email_detail": detail,
        "link": link if not sent else None,  # lien visible seulement si l'email a échoué
    }


@app.get("/admin/waitlist")
def admin_waitlist(
    status: str = "",
    q: str = "",
    sector: str = "",
    _user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    rows = db.waitlist_list(
        status=status or None, q=q or None, sector=sector or None
    )
    return {"counts": db.waitlist_counts(), "rows": rows,
            "sectors": db.waitlist_sectors()}


@app.post("/admin/waitlist/{wid}/invite")
def admin_waitlist_invite(
    wid: str, _user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    return _do_invite(wid, _user.get("sub", "admin"))


@app.post("/admin/waitlist/{wid}/resend")
def admin_waitlist_resend(
    wid: str, _user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    """Renvoi : nouveau lien à usage unique (l'ancien reste valable jusqu'à
    expiration, celui-ci remplace l'invitation en cours)."""
    return _do_invite(wid, _user.get("sub", "admin"))


@app.get("/admin/waitlist/{wid}/link")
def admin_waitlist_link(
    wid: str, _user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    """Lien de connexion à usage unique, jamais envoyé — pour WhatsApp."""
    row = db.waitlist_row(wid)
    if not row:
        raise HTTPException(404, "Ligne introuvable")
    if db.email_taken((row["email"] or "").strip().lower(), exclude_waitlist_id=wid):
        raise HTTPException(409, "Un compte existe déjà pour cet email.")
    token = db.create_invite_token(wid, row["email"], days=INVITE_DAYS,
                                   created_by=_user.get("sub", "admin"))
    db.audit(_user.get("sub", "admin"), "copy_link", wid, "lien généré (WhatsApp)")
    return {"link": f"{config.APP_URL}/onboarding?token={token}"}


@app.post("/admin/waitlist/{wid}/reject")
def admin_waitlist_reject(
    wid: str, _user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    row = db.waitlist_update(wid, status="rejected")
    if not row:
        raise HTTPException(404, "Ligne introuvable")
    db.audit(_user.get("sub", "admin"), "reject", wid)
    return row


@app.post("/admin/waitlist/{wid}/restore")
def admin_waitlist_restore(
    wid: str, _user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    row = db.waitlist_update(wid, status="pending")
    if not row:
        raise HTTPException(404, "Ligne introuvable")
    db.audit(_user.get("sub", "admin"), "restore", wid)
    return row


@app.patch("/admin/waitlist/{wid}/note")
def admin_waitlist_note(
    wid: str, body: WaitlistNoteBody,
    _user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    row = db.waitlist_update(wid, admin_note=body.admin_note)
    if not row:
        raise HTTPException(404, "Ligne introuvable")
    db.audit(_user.get("sub", "admin"), "note", wid, body.admin_note[:200])
    return row


@app.get("/onboarding/{token}")
def onboarding_prefill(token: str) -> dict[str, Any]:
    """Données pré-remplies pour le lien d'invitation (public, sans secret)."""
    inv = db.consume_invite_token(token)
    if not inv:
        raise HTTPException(410, "Ce lien d'invitation est expiré ou déjà utilisé.")
    row = db.waitlist_row(str(inv["waitlist_id"]))
    if not row:
        raise HTTPException(404, "Inscription introuvable")
    return {
        "email": row["email"],
        "lang": row.get("lang") or "fr",
        "prefill": {
            "company_name": row["company_name"],
            "sector": row.get("sector") or "",
            "cities": [],
            "keywords": [],
            "size": row.get("company_size") or "pme",
            "whatsapp": row.get("whatsapp") or "",
        },
    }


@app.post("/onboarding/{token}")
def onboarding_confirm(token: str, body: OnboardingBody) -> dict[str, Any]:
    """Le client définit son mot de passe et confirme son profil.
    L'essai de 14 jours démarre à cet instant précis."""
    inv = db.consume_invite_token(token)
    if not inv:
        raise HTTPException(410, "Ce lien d'invitation est expiré ou déjà utilisé.")
    email = (inv["email"] or "").strip().lower()
    if len(body.password) < 8:
        raise HTTPException(422, "Le mot de passe doit contenir au moins 8 caractères.")
    if db.email_taken(email, exclude_waitlist_id=str(inv["waitlist_id"])):
        raise HTTPException(409, "Un compte existe déjà pour cet email.")
    if len(body.keywords) > 15:
        raise HTTPException(422, "15 mots-clés maximum.")
    lang = "ar" if body.lang == "ar" else "fr"

    wid = str(inv["waitlist_id"])
    # Compte client (mot de passe choisi par le client, jamais généré ni envoyé).
    db.create_user(email, _hash_password(body.password), role="entreprise")
    company = db.upsert_company(
        name=body.company_name, email=email, phone=body.whatsapp or None,
        sectors=[body.sector] if body.sector else [],
        keywords=body.keywords, regions=body.cities,
        size=body.size or "pme",
    )
    db.activate_trial_company(str(company["id"]), waitlist_id=wid,
                              owner_email=email, lang=lang, trial_days=TRIAL_DAYS)
    db.waitlist_update(wid, status="active", activated_at=db.utcnow())
    db.mark_token_used(token)
    db.audit(email, "activate", wid,
             f"essai démarré ({TRIAL_DAYS} jours), entreprise {company['id']}")

    exp = time.time() + config.TOKEN_TTL_HOURS * 3600
    return {
        "token": _sign({"role": "entreprise", "sub": email,
                        "company_id": str(company["id"]), "exp": exp}),
        "role": "entreprise",
        "company_id": str(company["id"]),
    }


@app.get("/stats")
def stats(_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    counts = db.query(
        """
        SELECT (SELECT count(*) FROM companies) AS companies,
               (SELECT count(*) FROM opportunities) AS opportunities,
               (SELECT count(*) FROM matches) AS matches,
               (SELECT count(*) FROM digests) AS digests
        """
    )[0]
    recent = db.query(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE outcome = 'error') AS errors
        FROM lg_requests WHERE started_at > now() - INTERVAL '24 hours'
        """
    )[0]
    last_run = db.query(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    )
    return {"counts": counts, "last_24h": recent, "last_run": last_run[0] if last_run else None}
