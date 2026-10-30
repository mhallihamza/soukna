"use client";

// Liste d'attente (admin) — parcours d'invitation : pending → invited →
// active, ou rejected. Layout exact : titre + compteurs, onglets de statut,
// recherche/secteur, tableau (plus récent d'abord), drawer latéral avec
// détails + note interne + actions par statut. Interface en français,
// mise en page compatible RTL. Accès admin uniquement : sinon page 404.

import { useCallback, useEffect, useState } from "react";
import { notFound } from "next/navigation";
import { api, clearAuth, getAuth } from "../../lib";

type WaitlistRow = {
  id: string;
  company_name: string;
  email: string;
  whatsapp: string | null;
  sector: string | null;
  company_size: string | null;
  lang: string | null;
  consent: boolean;
  source: string | null;
  status: "pending" | "invited" | "active" | "rejected";
  invited_at: string | null;
  invited_by: string | null;
  activated_at: string | null;
  admin_note: string | null;
  created_at: string;
};

type WaitlistData = {
  counts: { pending: number; invited: number; active: number; rejected: number };
  rows: WaitlistRow[];
  sectors: string[];
};

type Tab = "all" | "pending" | "invited" | "active" | "rejected";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "all", label: "Tous" },
  { key: "pending", label: "En attente" },
  { key: "invited", label: "Invités" },
  { key: "active", label: "Actifs" },
  { key: "rejected", label: "Rejetés" },
];

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  pending: { cls: "bg-amberbg text-amberbrand border border-amberbrand/20", label: "En attente" },
  invited: { cls: "bg-greenbg text-greenbrand border border-greenbrand/20", label: "Invité" },
  active: { cls: "bg-greenbg text-greenbrand border border-greenbrand/30", label: "Actif" },
  rejected: { cls: "bg-redbg text-redbrand border border-redbrand/20", label: "Rejeté" },
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

export default function WaitlistPage() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [data, setData] = useState<WaitlistData | null>(null);
  const [tab, setTab] = useState<Tab>("pending");
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [selected, setSelected] = useState<WaitlistRow | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmInvite, setConfirmInvite] = useState<WaitlistRow | null>(null);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (t: Tab, query: string, sect: string) => {
    const params = new URLSearchParams();
    if (t !== "all") params.set("status", t);
    if (query) params.set("q", query);
    if (sect) params.set("sector", sect);
    const d = await api<WaitlistData>(`/admin/waitlist?${params.toString()}`);
    setData(d);
  }, []);

  useEffect(() => {
    const auth = getAuth();
    // Protection : admin uniquement, sinon page introuvable (404).
    if (!auth || auth.role !== "admin") {
      setAuthed(false);
      return;
    }
    setAuthed(true);
    load("pending", "", "").catch((e: Error) => setError(e.message));
  }, [load]);

  useEffect(() => {
    if (authed) load(tab, q, sector).catch((e: Error) => setError(e.message));
  }, [tab, q, sector, authed, load]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  }

  function openDrawer(row: WaitlistRow) {
    setSelected(row);
    setNoteDraft(row.admin_note || "");
  }

  function replaceRow(updated: WaitlistRow) {
    setData((prev) => {
      if (!prev) return prev;
      const visible =
        tab === "all" ? true : updated.status === tab;
      return {
        ...prev,
        rows: visible
          ? prev.rows.map((r) => (r.id === updated.id ? updated : r))
          : prev.rows.filter((r) => r.id !== updated.id),
        counts: prev.counts, // les compteurs globaux sont rafraîchis au reload
      };
    });
    if (selected?.id === updated.id) setSelected(updated);
  }

  async function refreshCounts() {
    try { await load(tab, q, sector); } catch { /* silencieux */ }
  }

  async function action(row: WaitlistRow, verb: "invite" | "resend" | "reject" | "restore") {
    setBusyId(row.id); setError("");
    try {
      // invite/resend renvoient un enveloppe { row, email_sent, email_detail,
      // link } ; reject/restore renvoient la ligne brute — on normalise.
      const res = await api<
        WaitlistRow & {
          row?: WaitlistRow;
          email_sent?: boolean;
          wa_sent?: boolean;
          link?: string | null;
        }
      >(`/admin/waitlist/${row.id}/${verb}`, {
        method: "POST", body: JSON.stringify({}),
      });
      const updated: WaitlistRow = res.row ?? res;
      replaceRow(updated);
      if ((verb === "invite" || verb === "resend") && res.email_sent === false) {
        showToast(
          res.wa_sent
            ? `Email non configuré — WhatsApp envoyé à ${updated.whatsapp}`
            : "Email/WhatsApp non envoyés — utilisez « Copier le lien »",
        );
      } else if (verb === "invite") {
        showToast(`Invitation envoyée à ${updated.email}`);
      } else if (verb === "resend") {
        showToast(`Nouvelle invitation envoyée à ${updated.email}`);
      } else if (verb === "reject") {
        showToast("Inscription rejetée");
      } else if (verb === "restore") {
        showToast("Remise en attente");
      }
      refreshCounts();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
      setConfirmInvite(null);
    }
  }

  async function copyLink(row: WaitlistRow) {
    setBusyId(row.id); setError("");
    try {
      const r = await api<{ link: string }>(`/admin/waitlist/${row.id}/link`, { method: "GET" });
      await navigator.clipboard.writeText(r.link);
      showToast("Lien de connexion copié (usage unique) — collez-le sur WhatsApp");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function saveNote(row: WaitlistRow) {
    if (noteDraft === (row.admin_note || "")) return;
    setBusyId(row.id); setError("");
    try {
      const updated = await api<WaitlistRow>(`/admin/waitlist/${row.id}/note`, {
        method: "PATCH", body: JSON.stringify({ admin_note: noteDraft }),
      });
      replaceRow(updated);
      showToast("Note enregistrée");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  if (authed === false) {
    notFound();
  }

  const counts = data?.counts;
  const countLine = counts
    ? `${counts.pending} en attente · ${counts.invited} invités · ${counts.active} actifs · ${counts.rejected} rejetés`
    : "";

  const actionsCell = (row: WaitlistRow) => {
    const busy = busyId === row.id;
    if (row.status === "pending") {
      return (
        <div className="flex items-center justify-end gap-1.5">
          <button onClick={(e) => { e.stopPropagation(); setConfirmInvite(row); }} disabled={busy}
                  className="bg-greenbrand hover:bg-[#18553f] text-white px-2.5 py-1 rounded text-[11px] font-bold transition-all disabled:opacity-60">
            {busy ? "…" : "Inviter"}
          </button>
          <button onClick={(e) => { e.stopPropagation(); action(row, "reject"); }} disabled={busy}
                  className="border border-line text-muted hover:text-redbrand px-2.5 py-1 rounded text-[11px] font-semibold transition-all disabled:opacity-60">
            Rejeter
          </button>
        </div>
      );
    }
    if (row.status === "invited") {
      return (
        <div className="flex items-center justify-end gap-1.5">
          <button onClick={(e) => { e.stopPropagation(); action(row, "resend"); }} disabled={busy}
                  className="bg-greenbrand hover:bg-[#18553f] text-white px-2.5 py-1 rounded text-[11px] font-bold transition-all disabled:opacity-60">
            {busy ? "…" : "Renvoyer l'invitation"}
          </button>
          <button onClick={(e) => { e.stopPropagation(); copyLink(row); }} disabled={busy}
                  className="border border-line text-ink hover:bg-paper px-2.5 py-1 rounded text-[11px] font-semibold transition-all disabled:opacity-60">
            Copier le lien
          </button>
        </div>
      );
    }
    if (row.status === "rejected") {
      return (
        <button onClick={(e) => { e.stopPropagation(); action(row, "restore"); }} disabled={busy}
                className="border border-line text-ink hover:bg-paper px-2.5 py-1 rounded text-[11px] font-semibold transition-all disabled:opacity-60">
          {busy ? "…" : "Remettre en attente"}
        </button>
      );
    }
    return <span className="text-[11px] text-muted">—</span>;
  };

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <header className="sticky top-0 z-40 bg-[#f5f0e6ed] backdrop-blur-md border-b border-[#dcd6cb] px-4 lg:px-8 py-3">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-ink text-white flex items-center justify-center font-bold font-display text-lg">SK</div>
            <div>
              <h1 className="font-display font-bold text-base text-ink leading-none">Liste d&apos;attente</h1>
              <div className="text-[11px] text-muted mt-0.5">Invitations & parcours d&apos;accès anticipé</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href="/admin" className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink transition-all">
              ← Console
            </a>
            <button onClick={() => { clearAuth(); window.location.href = "/login"; }}
                    className="text-[11px] font-semibold text-muted hover:text-redbrand">
              Déconnexion
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1400px] w-full mx-auto p-4 lg:p-8 space-y-5">
        {/* Titre + compteurs */}
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">Inscriptions en attente de décision</h2>
          <p className="text-xs text-muted mt-1">{countLine || "Chargement des compteurs…"}</p>
        </div>

        {/* Onglets de statut avec compteurs */}
        <nav className="bg-white border border-line rounded-lg px-2 flex items-center gap-1 sm:gap-2 overflow-x-auto no-scrollbar">
          {TABS.map(({ key, label }) => {
            const n = counts ? (key === "all"
              ? counts.pending + counts.invited + counts.active + counts.rejected
              : counts[key]) : 0;
            return (
              <button key={key} onClick={() => setTab(key)}
                      className={`tab-btn px-3.5 py-2.5 text-xs font-medium text-muted hover:text-ink transition-all whitespace-nowrap ${tab === key ? "active" : ""}`}>
                {label} <span className="text-[10px] font-bold opacity-70">({n})</span>
              </button>
            );
          })}
        </nav>

        {/* Recherche à gauche, filtre secteur à droite */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <input value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Rechercher par entreprise ou email…"
                 className="w-full sm:w-80 bg-white border border-line rounded-md px-3 py-2 text-xs text-ink placeholder-muted focus:border-greenbrand focus:ring-1 focus:ring-greenbrand" />
          <select value={sector} onChange={(e) => setSector(e.target.value)}
                  className="w-full sm:w-56 bg-white border border-line rounded-md px-3 py-2 text-xs text-ink focus:border-greenbrand">
            <option value="">Tous les secteurs</option>
            {(data?.sectors || []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {error && <div className="message message-err text-xs">{error}</div>}

        {/* Tableau (plus récent d'abord) */}
        <div className="bg-white border border-line rounded-lg shadow-sm overflow-x-auto">
          <table className="w-full text-xs text-left rtl:text-right">
            <thead>
              <tr className="border-b border-line text-muted uppercase text-[10px]">
                <th className="py-3 px-3">Entreprise</th>
                <th className="py-3 px-3">Email</th>
                <th className="py-3 px-3">WhatsApp</th>
                <th className="py-3 px-3">Secteur</th>
                <th className="py-3 px-3">Taille</th>
                <th className="py-3 px-3">Langue</th>
                <th className="py-3 px-3">Inscrit le</th>
                <th className="py-3 px-3">Statut</th>
                <th className="py-3 px-3 text-end">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {(data?.rows || []).length === 0 && (
                <tr><td colSpan={9} className="py-6 px-3 text-muted text-center">Aucune inscription pour ce filtre.</td></tr>
              )}
              {(data?.rows || []).map((row) => {
                const badge = STATUS_BADGE[row.status];
                return (
                  <tr key={row.id} onClick={() => openDrawer(row)}
                      className="cursor-pointer hover:bg-paper/60 transition-colors">
                    <td className="py-3 px-3 font-bold text-ink">{row.company_name}</td>
                    <td className="py-3 px-3 text-muted">{row.email}</td>
                    <td className="py-3 px-3 text-muted">{row.whatsapp || "—"}</td>
                    <td className="py-3 px-3 text-muted">{row.sector || "—"}</td>
                    <td className="py-3 px-3 text-muted">{row.company_size || "—"}</td>
                    <td className="py-3 px-3 uppercase text-muted">{(row.lang || "fr") === "ar" ? "AR" : "FR"}</td>
                    <td className="py-3 px-3 text-muted">{fmtDate(row.created_at)}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${badge.cls}`}>{badge.label}</span>
                    </td>
                    <td className="py-3 px-3 text-end" onClick={(e) => e.stopPropagation()}>
                      {actionsCell(row)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>

      {/* Drawer latéral : détails + note + actions */}
      <div className={`drawer-backdrop ${selected ? "open" : ""}`}
           onClick={(e) => { if (e.target === e.currentTarget) setSelected(null); }}>
        <aside className="drawer-panel p-6">
          {selected && (() => {
            const badge = STATUS_BADGE[selected.status];
            const busy = busyId === selected.id;
            return (
              <div className="space-y-5">
                <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-terra">Dossier d&apos;inscription</span>
                    <h2 className="font-display text-xl font-bold text-ink leading-tight mt-1">{selected.company_name}</h2>
                    <p className="text-xs text-muted mt-1">{selected.email}</p>
                  </div>
                  <button onClick={() => setSelected(null)} type="button"
                          className="border border-line rounded-md p-1.5 hover:bg-paper text-ink transition-all">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    ["Statut", badge.label],
                    ["Secteur", selected.sector || "—"],
                    ["Taille", selected.company_size || "—"],
                    ["Langue", (selected.lang || "fr") === "ar" ? "Arabe" : "Français"],
                    ["WhatsApp", selected.whatsapp || "—"],
                    ["Source", selected.source || "—"],
                    ["Inscrit le", fmtDate(selected.created_at)],
                    ["Invité le", fmtDate(selected.invited_at)],
                    ["Activé le", fmtDate(selected.activated_at)],
                    ["Invité par", selected.invited_by || "—"],
                  ].map(([k, v], i) => (
                    <div key={i} className="bg-paper p-2.5 rounded border border-line">
                      <span className="text-[10px] text-muted block">{k}</span>
                      <strong className="text-ink font-semibold">{v}</strong>
                    </div>
                  ))}
                </div>

                {selected.status === "active" && (
                  <div className="p-3 bg-greenbg border border-greenbrand/20 rounded text-xs text-greenbrand font-semibold">
                    Client actif — le compte et l&apos;essai sont déjà configurés.
                  </div>
                )}

                {/* Note interne */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-ink">Note interne (admin)</label>
                  <textarea value={noteDraft} onChange={(e) => setNoteDraft(e.target.value)} rows={3}
                            placeholder="Contexte, échanges, motivation…"
                            className="w-full bg-paper/40 border border-line rounded-lg px-3 py-2 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand" />
                  <button onClick={() => saveNote(selected)} disabled={busy}
                          className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded text-[11px] font-semibold text-ink disabled:opacity-60">
                    Enregistrer la note
                  </button>
                </div>

                {/* Actions par statut */}
                <div className="pt-4 border-t border-line space-y-2">
                  {selected.status === "pending" && (
                    <div className="flex gap-2">
                      <button onClick={() => setConfirmInvite(selected)} disabled={busy}
                              className="flex-1 bg-greenbrand hover:bg-[#18553f] text-white py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-60">
                        Inviter
                      </button>
                      <button onClick={() => action(selected, "reject")} disabled={busy}
                              className="flex-1 border border-line text-muted hover:text-redbrand py-2.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-60">
                        Rejeter
                      </button>
                    </div>
                  )}
                  {selected.status === "invited" && (
                    <div className="flex gap-2">
                      <button onClick={() => action(selected, "resend")} disabled={busy}
                              className="flex-1 bg-greenbrand hover:bg-[#18553f] text-white py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-60">
                        Renvoyer l&apos;invitation
                      </button>
                      <button onClick={() => copyLink(selected)} disabled={busy}
                              className="flex-1 border border-line text-ink hover:bg-paper py-2.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-60">
                        Copier le lien de connexion
                      </button>
                    </div>
                  )}
                  {selected.status === "rejected" && (
                    <button onClick={() => action(selected, "restore")} disabled={busy}
                            className="w-full border border-line text-ink hover:bg-paper py-2.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-60">
                      Remettre en attente
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
        </aside>
      </div>

      {/* Dialogue de confirmation d'invitation */}
      {confirmInvite && (
        <div className="fixed inset-0 z-[70] bg-[rgba(8,19,29,0.6)] backdrop-blur-[2px] flex items-center justify-center p-4"
             onClick={() => setConfirmInvite(null)}>
          <div className="bg-white border border-line rounded-xl shadow-2xl max-w-sm w-full p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display text-lg font-bold text-ink">Confirmer l&apos;invitation</h3>
            <p className="text-xs text-muted leading-relaxed">
              Un email d&apos;invitation (valable 7 jours, usage unique) sera envoyé à :
            </p>
            <div className="bg-paper rounded-lg p-3 text-xs space-y-1 border border-line">
              <div className="font-bold text-ink">{confirmInvite.company_name}</div>
              <div className="text-muted">{confirmInvite.email}</div>
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={() => setConfirmInvite(null)}
                      className="flex-1 border border-line text-ink hover:bg-paper py-2 rounded-lg text-xs font-semibold">
                Annuler
              </button>
              <button onClick={() => action(confirmInvite, "invite")} disabled={busyId === confirmInvite.id}
                      className="flex-1 bg-greenbrand hover:bg-[#18553f] text-white py-2 rounded-lg text-xs font-bold disabled:opacity-60">
                {busyId === confirmInvite.id ? "Envoi…" : "Confirmer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-5 right-5 z-[80] bg-ink text-white text-xs px-4 py-3 rounded-lg shadow-2xl max-w-xs flex items-center gap-2">
          <span className="text-greenbg">✓</span> {toast}
        </div>
      )}
    </div>
  );
}
