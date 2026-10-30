# =====================================================================
# e2e_waitlist.py — parcours complet : landing → invite → onboarding →
# essai, + vérifications de sécurité. Purge ses données à la fin.
# =====================================================================
import datetime
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, ".")
from soukna_graph import db as dbm  # noqa: E402

BASE = "http://localhost:8000"
SUPA = "https://yncuubvarfizxrxoplnb.supabase.co/rest/v1/waitlist"
PUB = "sb_publishable_PrbTctvzAoPAey_BHp-7RA_ue9_MZ9P"
EMAIL = "e2e-flow@soukna.ma"
EMAIL2 = "e2e-reject@soukna.ma"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def supa_insert(payload):
    """Insère comme la landing (return=minimal — anon n'a pas le droit de lire),
    puis relit la ligne via la connexion service."""
    req = urllib.request.Request(SUPA, method="POST")
    req.add_header("apikey", PUB)
    req.add_header("Authorization", "Bearer " + PUB)
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(req, json.dumps(payload).encode()) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, None
    email = payload.get("email", "")
    rows = dbm.query("SELECT * FROM waitlist WHERE lower(email) = %s", (email,))
    return status, rows


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)


# --- 1. Inscription landing (comme le formulaire) : status pending ---
st, wl = supa_insert({
    "company_name": "E2E Flow SARL", "email": EMAIL, "whatsapp": "+212600000011",
    "sector": "Informatique", "company_size": "pme", "lang": "fr",
    "consent": True, "source": "landing"})
ok(st == 201 and wl[0]["status"] == "pending", f"landing insert -> pending ({str(wl[0]['id'])[:8]})")
wid = str(wl[0]["id"])

st_dup, _ = supa_insert({"company_name": "X", "email": EMAIL})
ok(st_dup == 409, "email duplique rejete (409) -> « Cette adresse est deja inscrite. »")

req = urllib.request.Request(SUPA + "?select=*")
req.add_header("apikey", PUB)
req.add_header("Authorization", "Bearer " + PUB)
with urllib.request.urlopen(req) as r:
    ok(json.loads(r.read().decode()) == [], "cle publique ne peut PAS lire la waitlist (RLS)")

# --- 2. Admin : liste + invitation (email reel via Gmail) ---
st, adm = call("POST", "/auth/login", {"username": "hamzamhalli95@gmail.com",
                                       "password": "HAmza1995@@dacia"})
tok_adm = adm["token"]
ok(st == 200 and adm["role"] == "admin", "login admin")

st, lst = call("GET", "/admin/waitlist?status=pending", token=tok_adm)
ok(st == 200 and any(r["id"] == wid for r in lst["rows"]), "ligne visible dans la liste (En attente)")
ok(all(k in lst["counts"] for k in ("pending", "invited", "active", "rejected")),
   "compteurs par statut presents")

st, inv = call("POST", f"/admin/waitlist/{wid}/invite", {}, token=tok_adm)
ok(st == 200 and inv["email_sent"] is True, f"invitation -> email Gmail envoye ({inv['email_detail']})")
ok(inv["row"]["status"] == "invited" and inv["row"]["invited_by"], "statut -> invited + invited_by")
ok(inv["row"]["invited_at"] is not None, "invited_at rempli")

st, again = call("POST", f"/admin/waitlist/{wid}/resend", {}, token=tok_adm)
ok(st == 200 and again["email_sent"] is True, "renvoi (resend) -> nouveau lien + email")

# --- 3. Securite : non-admin ne peut pas invoquer l'invitation ---
st, ent_login = call("POST", "/auth/login", {"username": "demo@soukna.ma", "password": "demo1234"})
st2, _ = call("POST", f"/admin/waitlist/{wid}/reject", {}, token=ent_login["token"])
ok(st2 == 403, "entreprise (non-admin) -> 403 sur action admin")
st3, _ = call("GET", "/admin/waitlist", token=ent_login["token"])
ok(st3 == 403, "entreprise (non-admin) -> 403 sur liste admin")
st4, _ = call("GET", "/admin/waitlist")
ok(st4 == 401, "anonyme -> 401 sur liste admin")

# --- 4. Lien copie (WhatsApp) : usage unique, visible admin seul ---
st, lk = call("GET", f"/admin/waitlist/{wid}/link", token=tok_adm)
ok(st == 200 and "/onboarding?token=" in lk["link"], "lien de connexion genere (admin only)")
token_val = lk["link"].split("token=")[1]

# --- 5. Onboarding : pre-rempli puis confirmation (essai demarre) ---
st, pre = call("GET", f"/onboarding/{token_val}")
ok(st == 200 and pre["prefill"]["company_name"] == "E2E Flow SARL",
   "onboarding pre-rempli depuis la waitlist")
ok("password" not in json.dumps(pre), "aucun mot de passe dans la reponse")

st, act = call("POST", f"/onboarding/{token_val}", {
    "password": "MotDePasseE2E!2026", "company_name": "E2E Flow SARL",
    "sector": "Informatique", "cities": ["Rabat", "Casablanca"],
    "keywords": ["maintenance", "informatique"], "size": "pme",
    "whatsapp": "+212600000011", "lang": "fr"})
ok(st == 200 and act.get("role") == "entreprise", "onboarding confirme -> compte cree + session")

st2, _ = call("GET", f"/onboarding/{token_val}")
ok(st2 == 410, "lien usage unique -> 410 a la 2e utilisation")

# --- 6. Verifications post-activation ---
st, prof = call("GET", "/profile", token=act["token"])
ok(st == 200 and prof["plan"] == "trial", "plan = trial")
ok(prof.get("trial_started_at") and prof.get("trial_ends_at"),
   "trial_started_at / trial_ends_at remplis")
gap = (datetime.datetime.fromisoformat(prof["trial_ends_at"].replace("Z", "+00:00"))
       - datetime.datetime.fromisoformat(prof["trial_started_at"].replace("Z", "+00:00"))).days
ok(gap == 14, f"essai = 14 jours exactement ({gap})")
ok(prof["regions"] == ["Rabat", "Casablanca"], "villes confirmees enregistrees")

st, client_login = call("POST", "/auth/login",
                        {"username": EMAIL, "password": "MotDePasseE2E!2026"})
ok(st == 200 and client_login["role"] == "entreprise",
   "le client se connecte avec SON mot de passe")

st, demo_prof = call("GET", "/profile", token=ent_login["token"])
ok(demo_prof["email"] != EMAIL, "isolation : demo@soukna.ma ne voit pas le profil E2E")

# --- 7. Rejeter / remettre en attente (2e inscription) ---
st, wl2raw = supa_insert({
    "company_name": "E2E Reject Test", "email": EMAIL2, "sector": "BTP",
    "company_size": "pme", "lang": "ar", "consent": True, "source": "landing"})
wl2 = wl2raw[0]
st, rej = call("POST", f"/admin/waitlist/{wl2['id']}/reject", {}, token=tok_adm)
ok(st == 200 and rej["status"] == "rejected", "rejet -> statut rejected")
st, res = call("POST", f"/admin/waitlist/{wl2['id']}/restore", {}, token=tok_adm)
ok(st == 200 and res["status"] == "pending", "remise en attente -> pending")

# --- 8. Journal d'audit ---
logs = dbm.query(
    "SELECT actor, action FROM audit_log WHERE waitlist_id = %s ORDER BY created_at",
    (wid,))
actions = [row["action"] for row in logs]
ok("invite" in actions and "copy_link" in actions and "activate" in actions,
   f"journal d'audit : {actions}")

# --- Purge des donnees de test ---
dbm.execute("DELETE FROM users WHERE email IN (%s,%s)", (EMAIL, EMAIL2))
dbm.execute("DELETE FROM companies WHERE email IN (%s,%s)", (EMAIL, EMAIL2))
dbm.execute("DELETE FROM waitlist WHERE email IN (%s,%s)", (EMAIL, EMAIL2))
dbm._pool.close()
print("purge test : done")
