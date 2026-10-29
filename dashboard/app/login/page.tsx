"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, clearAuth, getAuth, setAuth, API_URL } from "../lib";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Déjà connecté ? Rediriger selon le rôle.
    const auth = getAuth();
    if (auth) {
      window.location.href = auth.role === "admin" ? "/admin" : "/dashboard";
    }
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api<{ token: string; role: "admin" | "entreprise" }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ username, password }) },
      );
      setAuth({ token: data.token, role: data.role });
      window.location.href = data.role === "admin" ? "/admin" : "/dashboard";
    } catch (exc) {
      setError((exc as Error).message || "Connexion impossible");
      setBusy(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a className="brand" href="/">
            Souk<span>na</span>
          </a>
          <nav className="topnav">
            <a href="/">← Retour à l&apos;accueil</a>
          </nav>
        </div>
      </header>

      <main className="page container">
        <div className="login-box panel">
          <h1>Connexion</h1>
          <p className="subtitle">
            Espace réservé aux entreprises inscrites et à l&apos;équipe Soukna.
          </p>

          {error && <div className="message message-err">{error}</div>}

          <form onSubmit={onSubmit}>
            <div className="form-grid" style={{ gridTemplateColumns: "1fr" }}>
              <label className="field">
                Email entreprise ou nom d&apos;utilisateur admin
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
              <label className="field">
                Mot de passe
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
            </div>
            <div style={{ marginTop: 18, display: "flex", gap: 12 }}>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={busy}
                style={{ flex: 1 }}
              >
                {busy ? "Connexion…" : "Se connecter"}
              </button>
              <button
                className="btn btn-danger"
                type="button"
                onClick={() => clearAuth()}
              >
                Effacer
              </button>
            </div>
          </form>

          <p className="hint" style={{ marginTop: 18 }}>
            Pas encore de compte ? L&apos;équipe Soukna crée votre accès
            entreprise après votre inscription. API : <code>{API_URL}</code>
          </p>
        </div>
      </main>

      <footer className="footer">
        Soukna — HAMZA MHALLI · Aba technology · © 2026
      </footer>
    </>
  );
}
