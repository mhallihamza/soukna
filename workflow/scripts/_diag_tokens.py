# Diagnostic temporaire : la base locale est-elle celle de prod ? (à supprimer)
from soukna_graph import config, db

host = config.DATABASE_URL.split("@")[-1].split("/")[0]
print("DB host       :", host)
for table in ("waitlist", "invite_tokens", "companies", "users"):
    n = db.query(f"SELECT count(*) AS n FROM {table}")[0]["n"]
    print(f"{table:<14}: {n} lignes")
last = db.query("SELECT company_name, email, status, created_at FROM waitlist "
                "ORDER BY created_at DESC LIMIT 3")
for r in last:
    print("waitlist      :", r)
