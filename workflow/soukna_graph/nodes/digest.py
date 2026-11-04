# =====================================================================
# Nœud digest : synthèse quotidienne multi-canaux (carte digest-agent).
# - chat : construit le texte qui sera la réponse (pas d'envoi ici).
# - pipeline : dashboard toujours alimenté ; WhatsApp/email UNIQUEMENT
#   si l'entreprise a activé le canal (opt-in strict).
# =====================================================================
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

from .. import config, db
from ..state import AgentState
from ..tools.emailer import send_email
from ..tools.whatsapp import send_whatsapp
from ..tracing import traced

VERDICT_LABELS = {"go": "🟢 GO", "a_etudier": "🟡 À ÉTUDIER", "no_go": "🔴 NO-GO"}

# Bandeau apposé quand AUCUNE source réelle n'a répondu (repli seeds) :
# le contenu est celui des données de démonstration, pas du portail.
SEED_NOTICE = (
    "ℹ️ Sources momentanément indisponibles — cet aperçu repose sur des "
    "données d'exemple, pas sur le portail national. Les envois "
    "WhatsApp/email sont suspendus jusqu'au retour des sources."
)

REGISTER_HINT = (
    "Votre numéro n'est pas encore enregistré chez Soukna.\n\n"
    "Créez le compte de votre entreprise sur le dashboard en renseignant "
    "votre numéro WhatsApp, puis revenez me voir ici."
)


def _fmt_date(value: Any) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)[:10]


def build_digest_text(company: dict[str, Any] | None, items: list[dict[str, Any]]) -> str:
    company = company or {}
    header = (
        f"🏙️ SOUKNA — Synthèse du {date.today():%d/%m/%Y}\n"
        f"Profil : {company.get('name', '')}\n"
    )
    if not items:
        return header + (
            "\nAucune nouvelle opportunité correspondant à votre profil aujourd'hui.\n"
            "Analyse indicative — le dossier officiel fait foi."
        )
    type_labels = {"bon_commande": "📦 Bon de commande",
                   "consultation": "📝 Consultation",
                   "appel_offres": "📋 Appel d'offres"}
    ordered = sorted(items, key=lambda i: -int(i.get("match_score") or 0))
    lines = [header, ""]
    for rank, it in enumerate(ordered[:5], 1):
        lines.append(
            f"{rank}. {VERDICT_LABELS.get(it.get('verdict'), '—')} · "
            f"Match {it.get('match_score')}/100"
        )
        lines.append(f"   {it.get('title')}")
        loc = it.get("city") or it.get("region") or "—"
        otype = type_labels.get(it.get("opportunity_type") or "", "")
        lines.append(
            f"   📍 {loc} · ⏳ {_fmt_date(it.get('deadline'))} · Réf. {it.get('source_ref')}"
            + (f" · {otype}" if otype else "")
        )
        if it.get("risks"):
            lines.append("   ⚠️ " + " ; ".join(str(r) for r in it["risks"][:2]))
        lines.append("")
    counts = Counter(str(it.get("verdict")) for it in ordered)
    lines.append(
        f"🟢 GO : {counts.get('go', 0)} · 🟡 À étudier : {counts.get('a_etudier', 0)} · "
        f"🔴 NO-GO : {counts.get('no_go', 0)}"
    )
    lines.append("")
    lines.append("Analyse indicative — le dossier officiel fait foi. Décision humaine.")
    return "\n".join(lines)


@traced("digest", lambda r: f"digests={len(r.get('delivered') or [])}")
def digest_node(state: AgentState) -> dict[str, Any]:
    items = list(state.get("matches") or [])

    # --- Mode chat : le texte devient la réponse (envoi par `response`) ---
    if not state.get("run_pipeline"):
        company = state.get("company")
        if not company:
            return {"digest_text": REGISTER_HINT, "digest_items": [], "delivered": []}
        if not items:
            # Repli : récapituler les matches existants plutôt que rien.
            rows = db.matches_for_company(
                str(company["id"]), min_score=config.VERDICT_NOGO_MAX, limit=5,
            )
            items = [{
                "title": r.get("title"),
                "city": r.get("city"),
                "region": r.get("region"),
                "deadline": str(r.get("deadline") or ""),
                "source_ref": r.get("source_ref"),
                "match_score": r.get("match_score", 0),
                "verdict": r.get("verdict") or "",
                "risks": r.get("risks") or [],
            } for r in rows]
        return {
            "digest_text": build_digest_text(company, items),
            "digest_items": items,
            "delivered": [],
        }

    # --- Mode pipeline : un digest par entreprise, canaux opt-in ----------
    # Si TOUTES les sources ont échoué (mode "seed", ex. portail suspendu),
    # le contenu est de l'exemple : on le publie au dashboard avec un
    # bandeau mais on ne fait partir AUCUN envoi WhatsApp/email.
    seed_fallback = str(state.get("source_mode") or "") == "seed"

    delivered: list[str] = []
    by_company: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_company.setdefault(str(it.get("company_id")), []).append(it)

    for company_id, its in by_company.items():
        company = db.get_company(company_id) or {}
        text = build_digest_text(company, its)
        if seed_fallback:
            text = f"{SEED_NOTICE}\n\n{text}"
        channels = ["dashboard"]
        db.save_digest(company_id=company_id, content=text, channels=channels)
        if not seed_fallback:
            if company.get("channel_whatsapp") and company.get("phone"):
                ok, _detail = send_whatsapp(str(company["phone"]), text)
                if ok:
                    channels.append("whatsapp")
            if company.get("channel_email") and company.get("email"):
                ok, _detail = send_email(
                    str(company["email"]),
                    f"Soukna — synthèse du {date.today():%d/%m/%Y}",
                    text,
                )
                if ok:
                    channels.append("email")
        db.save_digest(company_id=company_id, content=text, channels=channels)
        delivered.append(f"{company.get('name', company_id)}:{'+'.join(channels)}")

    return {"delivered": delivered}
