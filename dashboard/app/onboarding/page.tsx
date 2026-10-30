"use client";

// Onboarding client : le client clique le lien d'invitation (usage unique),
// choisit son propre mot de passe, confirme son profil pré-rempli —
// l'essai de 14 jours démarre à la confirmation. FR/AR avec bascule RTL.

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BrandLoader from "../brand-loader";
import { API_URL } from "../lib";

type Prefill = {
  email: string;
  lang: string;
  prefill: {
    company_name: string;
    sector: string;
    cities: string[];
    keywords: string[];
    size: string;
    whatsapp: string;
  };
};

const REGIONS = ["Casablanca", "Rabat", "Tanger", "Marrakech", "Agadir"];
const SECTORS = [
  "Informatique", "BTP", "Fournitures",
  "Services et maintenance", "Conseil et études",
];

const T: Record<"fr" | "ar", Record<string, string>> = {
  fr: {
    title: "Bienvenue sur Soukna",
    subtitle: "Choisissez votre mot de passe et confirmez le profil de votre entreprise pour démarrer votre essai gratuit de 14 jours.",
    password: "Choisissez votre mot de passe *",
    passwordHint: "8 caractères minimum",
    confirmPassword: "Confirmez le mot de passe *",
    accountFor: "Compte :",
    companyName: "Nom de l'entreprise *",
    sector: "Secteur d'activité *",
    cities: "Villes cibles",
    citiesHint: "Sélectionnez une ou plusieurs villes",
    keywords: "Mots-clés d'activité",
    keywordsHint: "Entrée pour ajouter · 15 maximum",
    size: "Taille de l'entreprise",
    whatsapp: "WhatsApp (facultatif)",
    confirm: "Confirmer mon profil",
    confirming: "Confirmation…",
    selectSize: "Choisir…",
    pwdMismatch: "Les mots de passe ne correspondent pas.",
    pwdShort: "Le mot de passe doit contenir au moins 8 caractères.",
    addKeyword: "Ajouter",
    trialNote: "Votre essai gratuit de 14 jours démarrera à la confirmation.",
  },
  ar: {
    title: "مرحباً بك في Soukna",
    subtitle: "اختر كلمة المرور وأكّد ملف شركتك لبدء تجربتك المجانية لمدة 14 يوماً.",
    password: "اختر كلمة المرور *",
    passwordHint: "8 أحرف على الأقل",
    confirmPassword: "تأكيد كلمة المرور *",
    accountFor: "الحساب:",
    companyName: "اسم الشركة *",
    sector: "قطاع النشاط *",
    cities: "المدن المستهدفة",
    citiesHint: "اختر مدينة واحدة أو أكثر",
    keywords: "الكلمات المفتاحية للنشاط",
    keywordsHint: "أدخل لإضافة · 15 كحد أقصى",
    size: "حجم الشركة",
    whatsapp: "واتساب (اختياري)",
    confirm: "تأكيد ملفي",
    confirming: "جارٍ التأكيد…",
    selectSize: "اختر…",
    pwdMismatch: "كلمتا المرور غير متطابقتين.",
    pwdShort: "يجب أن تحتوي كلمة المرور على 8 أحرف على الأقل.",
    addKeyword: "إضافة",
    trialNote: "تبدأ تجربتك المجانية لمدة 14 يوماً عند التأكيد.",
  },
};

function OnboardingInner() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") || "";
  const [lang, setLang] = useState<"fr" | "ar">("fr");
  const [data, setData] = useState<Prefill | null>(null);
  const [fatal, setFatal] = useState("");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [sector, setSector] = useState("");
  const [cities, setCities] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [kwInput, setKwInput] = useState("");
  const [size, setSize] = useState("pme");
  const [whatsapp, setWhatsapp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const t = (k: string) => T[lang][k] ?? k;

  useEffect(() => {
    if (!token) { setFatal("Lien d'invitation invalide."); return; }
    (async () => {
      try {
        const r = await fetch(`${API_URL}/onboarding/${encodeURIComponent(token)}`);
        if (!r.ok) {
          const body = await r.json().catch(() => null);
          setFatal(body?.detail || "Ce lien d'invitation est expiré ou déjà utilisé.");
          return;
        }
        const d = (await r.json()) as Prefill;
        setData(d);
        setLang(d.lang === "ar" ? "ar" : "fr");
        setName(d.prefill.company_name);
        setSector(d.prefill.sector);
        setKeywords(d.prefill.keywords || []);
        setSize(d.prefill.size || "pme");
        setWhatsapp(d.prefill.whatsapp || "");
      } catch {
        setFatal("Service indisponible — réessayez plus tard.");
      }
    })();
  }, [token]);

  function toggleLang() {
    const next = lang === "fr" ? "ar" : "fr";
    setLang(next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
  }

  function addKeyword() {
    const kw = kwInput.trim();
    if (!kw) return;
    if (keywords.length >= 15) { setError(t("keywordsHint")); return; }
    if (!keywords.includes(kw)) setKeywords([...keywords, kw]);
    setKwInput("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError(t("pwdShort")); return; }
    if (password !== confirm) { setError(t("pwdMismatch")); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/onboarding/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password, company_name: name, sector, cities, keywords,
          size, whatsapp: whatsapp || null, lang,
        }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) { setError(body?.detail || "Une erreur est survenue."); setBusy(false); return; }
      // Session immédiate : le client est connecté après confirmation.
      localStorage.setItem("soukna_auth", JSON.stringify({ token: body.token, role: body.role }));
      router.push("/dashboard");
    } catch {
      setError("Service indisponible — réessayez plus tard.");
      setBusy(false);
    }
  }

  if (fatal) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper p-4">
        <div className="bg-white border border-line rounded-2xl shadow-lg max-w-md w-full p-8 text-center space-y-3">
          <span className="text-3xl">⏳</span>
          <h1 className="font-display text-xl font-bold text-ink">Lien d&apos;invitation</h1>
          <p className="text-xs text-muted">{fatal}</p>
          <a href="/login" className="inline-block bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded-lg text-xs font-bold transition-all">
            Aller à la connexion
          </a>
        </div>
      </div>
    );
  }

  if (!data) {
    return <BrandLoader label={lang === "fr" ? "Validation de votre invitation…" : "جارٍ التحقق من الدعوة…"} />;
  }

  return (
    <div className="min-h-screen bg-paper py-8 px-4" dir={lang === "ar" ? "rtl" : "ltr"}>
      <div className="max-w-2xl mx-auto space-y-5">
        <div className="flex items-center justify-between">
          <a href="/landing.html" className="flex items-center gap-2 text-lg font-bold text-ink">
            <svg className="w-7 h-7 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
              <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
              <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
              <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
            </svg>
            <span className="font-display">Soukna</span>
          </a>
          <button onClick={toggleLang} type="button"
                  className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink shadow-sm">
            {lang === "fr" ? "العربية" : "Français"}
          </button>
        </div>

        <div className="bg-white border border-line rounded-2xl shadow-xl p-6 sm:p-8 space-y-5">
          <div>
            <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
            <p className="text-xs text-muted mt-1.5">{t("subtitle")}</p>
            <p className="text-[11px] text-greenbrand font-semibold mt-2">
              {t("accountFor")} {data.email}
            </p>
          </div>

          {error && <div className="message message-err text-xs">{error}</div>}

          <form onSubmit={onSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block text-xs font-bold text-ink">
                {t("password")}
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                       autoComplete="new-password" placeholder="••••••••"
                       className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand" />
                <span className="block text-[10px] text-muted font-normal mt-0.5">{t("passwordHint")}</span>
              </label>
              <label className="block text-xs font-bold text-ink">
                {t("confirmPassword")}
                <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                       autoComplete="new-password" placeholder="••••••••"
                       className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand" />
              </label>
            </div>

            <div className="pt-3 border-t border-line grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block text-xs font-bold text-ink">
                {t("companyName")}
                <input required value={name} onChange={(e) => setName(e.target.value)}
                       className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink focus:bg-white focus:border-greenbrand" />
              </label>
              <label className="block text-xs font-bold text-ink">
                {t("sector")}
                <select required value={sector} onChange={(e) => setSector(e.target.value)}
                        className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink focus:bg-white focus:border-greenbrand">
                  <option value="">{t("selectSize")}</option>
                  {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            </div>

            <div>
              <span className="block text-xs font-bold text-ink">{t("cities")}</span>
              <span className="block text-[10px] text-muted font-normal">{t("citiesHint")}</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {REGIONS.map((c) => {
                  const on = cities.includes(c);
                  return (
                    <button key={c} type="button"
                            onClick={() => setCities(on ? cities.filter((x) => x !== c) : [...cities, c])}
                            className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-all ${on
                              ? "bg-greenbg text-greenbrand border-greenbrand/40"
                              : "bg-paper/40 text-muted border-line hover:border-greenbrand/40"}`}>
                      {on ? "✓ " : ""}{c}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <span className="block text-xs font-bold text-ink">{t("keywords")}</span>
              <span className="block text-[10px] text-muted font-normal">{t("keywordsHint")}</span>
              <div className="flex gap-2 mt-2">
                <input value={kwInput} onChange={(e) => setKwInput(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addKeyword(); } }}
                       className="flex-1 bg-paper/40 border border-line rounded-lg px-3 py-2 text-xs text-ink focus:bg-white focus:border-greenbrand" />
                <button type="button" onClick={addKeyword}
                        className="border border-line bg-white hover:bg-paper px-4 rounded-lg text-xs font-semibold text-ink">
                  {t("addKeyword")}
                </button>
              </div>
              {keywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {keywords.map((k) => (
                    <span key={k} className="inline-flex items-center gap-1 bg-greenbg text-greenbrand border border-greenbrand/20 px-2 py-0.5 rounded-full text-[11px] font-semibold">
                      {k}
                      <button type="button" onClick={() => setKeywords(keywords.filter((x) => x !== k))}
                              className="hover:text-redbrand" aria-label={`remove ${k}`}>×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block text-xs font-bold text-ink">
                {t("size")}
                <select value={size} onChange={(e) => setSize(e.target.value)}
                        className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink focus:bg-white focus:border-greenbrand">
                  <option value="petite">TPE / petite entreprise</option>
                  <option value="pme">PME</option>
                  <option value="grande">Grande entreprise</option>
                </select>
              </label>
              <label className="block text-xs font-bold text-ink">
                {t("whatsapp")}
                <input value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="+212 6…"
                       className="mt-1 w-full bg-paper/40 border border-line rounded-lg px-3 py-2.5 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand" />
              </label>
            </div>

            <div className="pt-2 space-y-2">
              <button type="submit" disabled={busy}
                      className="w-full bg-greenbrand hover:bg-[#18553f] text-white py-3 rounded-lg text-xs font-bold transition-all shadow-md disabled:opacity-70">
                {busy ? t("confirming") : t("confirm")}
              </button>
              <p className="text-center text-[10px] text-muted">{t("trialNote")}</p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<BrandLoader label="…" />}>
      <OnboardingInner />
    </Suspense>
  );
}
