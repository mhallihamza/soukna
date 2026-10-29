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

from soukna_graph import config, db
from soukna_graph.graph import build_graph

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
            db.finalize_request(request_id, route="pipeline", outcome="ok")
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
