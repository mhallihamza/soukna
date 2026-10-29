"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, clearAuth, getAuth } from "../lib";

type Stats = Record<string, number | string>;

type Company = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  sectors: string[];
  regions: string[];
  size: string;
  whatsapp_enabled: boolean;
  email_enabled: boolean;
  created_at: string;
};

type LogRow = {
  id: number;
  agent: string;
  event: string;
  error: string | null;
  created_at: string;
};

type RequestRow = {
  id: number;
  route: string;
  intent: string | null;
  message_id: string | null;
  duration_ms: number | null;
  status: string;
  created_at: string;
};

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [requests, setRequests] = useState<RequestRow[]>([]);
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Formulaire de création entreprise.
  const [cName, setCName] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [cPassword, setCPassword] = useState("");
  const [cSectors, setCSectors] = useState("");

  async function loadAll() {
    const [s, c, r, l] = await Promise.all([
      api<Stats>("/stats"),
      api<Company[]>("/companies"),
      api<RequestRow[]>("/observability?hours=24"),
      api<LogRow[]>("/observability/logs?hours=24"),
    ]);
    setStats(s);
    setCompanies(c || []);
    setRequests(r || []);
    setLogs(l || []);
  }

  useEffect(() => {
    const auth = getAuth();
    if (!auth) {
      window.location.href = "/login";
      return;
    }
    if (auth.role !== "admin") {
      window.location.href = "/dashboard";
      return;
    }
    (async () => {
      try {
        await loadAll();
      } catch (exc) {
        setErr((exc as Error).message);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  async function runPipeline() {
    setMsg("");
    setErr("");
    setBusy(true);
    try {
      const r = await api<{
        status: string;
        opportunities_found: number;
        matches_created: number;
        digests_sent: number;
      }>("/run", { method: "POST", body: JSON.stringify({}) });
      setMsg(
        `Pipeline ${r.status} : ${r.opportunities_found} opportunités, ` +
          `${r.matches_created} matchs, ${r.digests_sent} synthèses.`,
      );
      await loadAll();
    } catch (exc) {
      setErr((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createCompany(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    setErr("");
    setBusy(true);
    try {
      await api<Company>("/companies", {
        method: "POST",
        body: JSON.stringify({
          name: cName,
          email: cEmail,
          phone: cPhone || null,
          password: cPassword,
          sectors: cSectors.split(",").map((x) => x.trim()).filter(Boolean),
        }),
      });
      setMsg(`Entreprise « ${cName} » créée ✅`);
      setCName("");
      setCEmail("");
      setCPhone("");
      setCPassword("");
      setCSectors("");
      await loadAll();
    } catch (exc) {
      setErr((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) {
    return (
      <main className="page container">
        <p className="subtitle">Chargement…</p>
      </main>
    );
  }

  const kpis: Array<[string, string | number]> = stats
    ? Object.entries(stats).map(([k, v]) => [k, v])
    : [];

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a className="brand" href="/">
            Souk<span>na</span> <span style={{ fontSize: 12 }}>admin</span>
          </a>
          <nav className="topnav">
            <button
              className="btn btn-primary"
              onClick={runPipeline}
              disabled={busy}
            >
              {busy ? "Exécution…" : "Lancer le pipeline"}
            </button>
            <button
              className="btn"
              onClick={() => {
                clearAuth();
                window.location.href = "/login";
              }}
            >
              Déconnexion
            </button>
          </nav>
        </div>
      </header>

      <main className="page container">
        <h1>Console d&apos;administration</h1>
        <p className="subtitle">
          Pipeline, entreprises, observabilité — 24 dernières heures.
        </p>

        {msg && <div className="message message-ok">{msg}</div>}
        {err && <div className="message message-err">{err}</div>}

        <div className="cards">
          {kpis.map(([label, value]) => (
            <div className="card" key={label}>
              <div className="kpi">{String(value)}</div>
              <div className="label">{label}</div>
            </div>
          ))}
          {kpis.length === 0 && (
            <div className="card">
              <div className="label">Aucune statistique disponible</div>
            </div>
          )}
        </div>

        <h2>Entreprises ({companies.length})</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Nom</th>
                <th>Email</th>
                <th>Téléphone</th>
                <th>Secteurs</th>
                <th>Régions</th>
                <th>WhatsApp</th>
                <th>Email</th>
                <th>Inscrite le</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.email}</td>
                  <td>{c.phone || "—"}</td>
                  <td>{(c.sectors || []).join(", ") || "—"}</td>
                  <td>{(c.regions || []).join(", ") || "—"}</td>
                  <td>
                    <span
                      className={`badge ${c.whatsapp_enabled ? "badge-go" : "badge-neutral"}`}
                    >
                      {c.whatsapp_enabled ? "oui" : "non"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${c.email_enabled ? "badge-go" : "badge-neutral"}`}
                    >
                      {c.email_enabled ? "oui" : "non"}
                    </span>
                  </td>
                  <td className="hint">{c.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
              {companies.length === 0 && (
                <tr>
                  <td colSpan={8} className="hint">
                    Aucune entreprise inscrite.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <h2>Créer une entreprise</h2>
        <form className="panel" onSubmit={createCompany}>
          <div className="form-grid">
            <label className="field">
              Nom
              <input
                value={cName}
                onChange={(e) => setCName(e.target.value)}
                required
              />
            </label>
            <label className="field">
              Email (identifiant)
              <input
                type="email"
                value={cEmail}
                onChange={(e) => setCEmail(e.target.value)}
                required
              />
            </label>
            <label className="field">
              Téléphone WhatsApp (optionnel)
              <input
                value={cPhone}
                onChange={(e) => setCPhone(e.target.value)}
                placeholder="+2126…"
              />
            </label>
            <label className="field">
              Mot de passe initial
              <input
                type="password"
                value={cPassword}
                onChange={(e) => setCPassword(e.target.value)}
                required
                minLength={6}
              />
            </label>
            <label className="field">
              Secteurs (virgules)
              <input
                value={cSectors}
                onChange={(e) => setCSectors(e.target.value)}
                placeholder="Informatique, Travaux"
              />
            </label>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              Créer l&apos;entreprise
            </button>
          </div>
        </form>

        <h2>Requêtes (24h)</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Route</th>
                <th>Intent</th>
                <th>Message ID</th>
                <th>Durée</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td className="hint">
                    {new Date(r.created_at).toLocaleString("fr-FR")}
                  </td>
                  <td>{r.route}</td>
                  <td>{r.intent || "—"}</td>
                  <td className="hint">{r.message_id || "—"}</td>
                  <td>{r.duration_ms != null ? `${r.duration_ms} ms` : "—"}</td>
                  <td>
                    <span
                      className={`badge ${r.status === "ok" ? "badge-go" : "badge-nogo"}`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
              {requests.length === 0 && (
                <tr>
                  <td colSpan={6} className="hint">
                    Aucune requête enregistrée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <h2>Journal des agents (24h)</h2>
        <div className="panel logs">
          {logs.map((l) => (
            <div className={`log-line ${l.error ? "log-err" : ""}`} key={l.id}>
              <span className="log-agent">[{l.agent}]</span>{" "}
              {new Date(l.created_at).toLocaleTimeString("fr-FR")} {l.event}
              {l.error ? ` — ${l.error}` : ""}
            </div>
          ))}
          {logs.length === 0 && (
            <div className="log-line">Aucun événement enregistré.</div>
          )}
        </div>
      </main>

      <footer className="footer">
        Soukna — HAMZA MHALLI · Aba technology · © 2026
      </footer>
    </>
  );
}
