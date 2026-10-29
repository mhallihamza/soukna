"use client";

// Page de connexion — port du mockup "split screen" : panneau de marque
// sombre + formulaire. Auth réelle via POST /auth/login (users DB ou
// entreprises) ; SSO / lien magique : intention affichée, pas encore câblés.

import { FormEvent, useEffect, useState } from "react";
import { api, clearAuth, getAuth, setAuth, API_URL } from "../lib";

const T: Record<"fr" | "ar", Record<string, string>> = {
  fr: {
    heroHeading: "Prenez les meilleures décisions avant de répondre.",
    heroSub: "Accédez à vos scores de Match personnalisés, vos analyses de risques administratives et la synthèse quotidienne de vos marchés cibles.",
    feature1: "Précision du filtrage sectoriel",
    feature2: "Synthèse quotidienne matinale",
    feature3: "Analyse explicative des contraintes",
    trustText: "« Soukna nous fait gagner un temps précieux dans le tri quotidien des avis publics. »",
    trustAuthor: "— Directeur Général, PME Services Casablanca",
    titleSign: "Connexion à votre espace",
    subSign: "Saisissez vos identifiants professionnels pour accéder à la plateforme.",
    orDivider: "ou par email",
    emailLabel: "Email professionnel *",
    emailPlaceholder: "nom@entreprise.ma",
    passwordLabel: "Mot de passe *",
    forgotPassword: "Mot de passe oublié ?",
    rememberMe: "Se souvenir de moi",
    magicLinkOption: "Connexion par Lien Magique",
    submitBtn: "Se connecter à l'espace",
    verifying: "Vérification...",
    noAccount: "Votre entreprise n'a pas encore de compte ?",
    requestAccess: "Demander un accès anticipé",
    footerPrivacy: "Confidentialité",
    footerTerms: "Conditions d'utilisation",
    footerSupport: "Support Client",
    toastSSO: "SSO bientôt disponible — utilisez votre email professionnel.",
    toastMagic: "Lien magique envoyé ! Vérifiez votre boîte mail.",
    toastForgot: "Un lien de réinitialisation vous sera envoyé par email.",
    loginFailed: "Identifiants invalides",
  },
  ar: {
    heroHeading: "اتخذ أفضل القرارات قبل التقديم على الصفقات.",
    heroSub: "احصل على درجات توافق مخصصة، وتحليلات المخاطر الإدارية، والملخص اليومي للصفقات المستهدفة.",
    feature1: "دقة التصفية القطاعية",
    feature2: "ملخص يومي صباحي",
    feature3: "تحليل توضيحي للشروط والمتطلبات",
    trustText: "« توفر لنا Soukna وقتاً ثميناً في فرز الإعلانات العمومية يومياً. »",
    trustAuthor: "— المدير العام، شركة خدمات بالدار البيضاء",
    titleSign: "تسجيل الدخول إلى فضائك",
    subSign: "أدخل بيانات الاعتماد المهنية للوصول إلى المنصة.",
    orDivider: "أو عبر البريد الإلكتروني",
    emailLabel: "البريد الإلكتروني المهني *",
    emailPlaceholder: "nom@entreprise.ma",
    passwordLabel: "كلمة المرور *",
    forgotPassword: "نسيت كلمة المرور؟",
    rememberMe: "تذكرني",
    magicLinkOption: "الدخول عبر رابط سحري",
    submitBtn: "تسجيل الدخول",
    verifying: "جارٍ التحقق...",
    noAccount: "ليس لدى شركتك حساب بعد؟",
    requestAccess: "طلب ولوج مبكر",
    footerPrivacy: "الخصوصية",
    footerTerms: "شروط الاستخدام",
    footerSupport: "الدعم الفني",
    toastSSO: "الدخول الموحد قريباً — استخدم بريدك المهني.",
    toastMagic: "تم إرسال الرابط السحري! تفقد بريدك الإلكتروني.",
    toastForgot: "سيتم إرسال رابط إعادة الضبط إلى بريدك.",
    loginFailed: "بيانات الاعتماد غير صحيحة",
  },
};

export default function LoginPage() {
  const [lang, setLang] = useState<"fr" | "ar">("fr");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  const t = (k: string) => T[lang][k] ?? k;

  useEffect(() => {
    const auth = getAuth();
    if (auth) {
      window.location.href = auth.role === "admin" ? "/admin" : "/dashboard";
    }
  }, []);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  }

  function toggleLang() {
    const next = lang === "fr" ? "ar" : "fr";
    setLang(next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api<{ token: string; role: "admin" | "entreprise" }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ username: email, password }) },
      );
      setAuth({ token: data.token, role: data.role }, remember);
      showToast(lang === "fr" ? "Authentification réussie ! Redirection..." : "تم التحقق بنجاح! جاري التوجيه...");
      setTimeout(() => {
        window.location.href = data.role === "admin" ? "/admin" : "/dashboard";
      }, 600);
    } catch (exc) {
      setError((exc as Error).message || t("loginFailed"));
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      {/* TOP HEADER */}
      <header className="w-full px-6 py-4 flex items-center justify-between border-b border-line/60 bg-[#f5f0e6ed] backdrop-blur-md sticky top-0 z-30">
        <a href="/landing.html" className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
          <svg className="w-8 h-8 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
            <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
            <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
          </svg>
          <span className="font-display">Soukna</span>
          <span className="text-[10px] uppercase font-bold tracking-wider bg-greenbg text-greenbrand px-2 py-0.5 rounded border border-greenbrand/20 hidden sm:inline-block">
            Espace Pro
          </span>
        </a>
        <button onClick={toggleLang} type="button"
                className="border border-line bg-white hover:bg-paper px-3.5 py-1.5 rounded-md text-xs font-semibold text-ink transition-all flex items-center gap-2 shadow-sm">
          <svg className="w-3.5 h-3.5 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
          </svg>
          <span>{lang === "fr" ? "العربية" : "Français"}</span>
        </button>
      </header>

      {/* SPLIT SCREEN MAIN */}
      <main className="flex-1 flex items-center justify-center p-4 lg:p-12">
        <div className="max-w-5xl w-full bg-white border border-line rounded-2xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12 min-h-[600px]">

          {/* LEFT BRAND PANEL */}
          <div className="lg:col-span-5 bg-ink text-white p-8 lg:p-10 flex flex-col justify-between relative overflow-hidden">
            <div className="absolute inset-0 opacity-10 pointer-events-none bg-[radial-gradient(#1f6b52_1px,transparent_1px)] [background-size:16px_16px]" />
            <div className="relative z-10 space-y-6">
              <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1 rounded-full text-xs font-semibold text-[#a8d0bb] border border-white/10">
                <span>✓ Intelligence Marchés Publics</span>
              </div>
              <h2 className="font-display text-2xl lg:text-3xl font-bold leading-tight">{t("heroHeading")}</h2>
              <p className="text-xs text-[#bbc4ca] leading-relaxed">{t("heroSub")}</p>
              <div className="space-y-3 pt-4 border-t border-white/10 text-xs">
                {[
                  ["98%", "bg-greenbrand/30 border-greenbrand text-greenbg", t("feature1")],
                  ["08h", "bg-terra/30 border-terra text-terra", t("feature2")],
                  ["CPS", "bg-amberbrand/30 border-amberbrand text-amberbg", t("feature3")],
                ].map(([badge, cls, label]) => (
                  <div key={badge} className="flex items-center gap-3">
                    <div className={`w-7 h-7 rounded-full border flex items-center justify-center font-bold text-[10px] ${cls}`}>{badge}</div>
                    <span className="text-[#d4d9dc]">{label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="relative z-10 pt-6 border-t border-white/10 text-[11px] text-[#8ea0bf]">
              <p>{t("trustText")}</p>
              <span className="font-bold text-white block mt-1">{t("trustAuthor")}</span>
            </div>
          </div>

          {/* RIGHT FORM PANEL */}
          <div className="lg:col-span-7 p-6 sm:p-10 lg:p-12 flex flex-col justify-between bg-white">
            <div>
              <div className="mb-8">
                <h1 className="font-display text-2xl lg:text-3xl font-bold text-ink">{t("titleSign")}</h1>
                <p className="text-xs text-muted mt-1.5">{t("subSign")}</p>
              </div>

              {error && <div className="message message-err !mt-0 !mb-4 text-xs">{error}</div>}

              {/* SSO (intention — pas encore de backend SSO) */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                <button type="button" onClick={() => showToast(t("toastSSO"))}
                        className="flex items-center justify-center gap-2 border border-line bg-paper/50 hover:bg-paper py-2.5 px-3 rounded-lg text-xs font-semibold text-ink transition-all shadow-sm">
                  <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" /><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" /><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" /></svg>
                  <span>Google Workspace</span>
                </button>
                <button type="button" onClick={() => showToast(t("toastSSO"))}
                        className="flex items-center justify-center gap-2 border border-line bg-paper/50 hover:bg-paper py-2.5 px-3 rounded-lg text-xs font-semibold text-ink transition-all shadow-sm">
                  <svg className="w-4 h-4" viewBox="0 0 23 23"><path fill="#f35325" d="M1 1h10v10H1z" /><path fill="#81bc06" d="M12 1h10v10H12z" /><path fill="#05a6f0" d="M1 12h10v10H1z" /><path fill="#ffba08" d="M12 12h10v10H12z" /></svg>
                  <span>Microsoft 365</span>
                </button>
              </div>

              <div className="relative my-6 text-center">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-line" /></div>
                <span className="relative px-3 bg-white text-[11px] text-muted uppercase tracking-wider font-semibold">{t("orDivider")}</span>
              </div>

              <form onSubmit={onSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-ink mb-1.5" htmlFor="login-email">{t("emailLabel")}</label>
                  <input id="login-email" type="text" required value={email} onChange={(e) => setEmail(e.target.value)}
                         autoComplete="username" placeholder={t("emailPlaceholder")}
                         className="w-full bg-paper/40 border border-line rounded-lg px-3.5 py-2.5 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all" />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-bold text-ink" htmlFor="login-password">{t("passwordLabel")}</label>
                    <button type="button" onClick={() => showToast(t("toastForgot"))}
                            className="text-[11px] text-greenbrand font-semibold hover:underline">
                      {t("forgotPassword")}
                    </button>
                  </div>
                  <div className="relative">
                    <input id="login-password" type={showPwd ? "text" : "password"} required value={password}
                           onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
                           placeholder="••••••••••••"
                           className="w-full bg-paper/40 border border-line rounded-lg px-3.5 pr-10 py-2.5 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all rtl:pr-3.5 rtl:pl-10" />
                    <button type="button" onClick={() => setShowPwd((v) => !v)}
                            className="absolute right-3 rtl:right-auto rtl:left-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink text-xs"
                            aria-label="toggle password">
                      {showPwd ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)}
                           className="w-4 h-4 rounded border-line accent-greenbrand cursor-pointer" />
                    <span className="text-xs text-muted">{t("rememberMe")}</span>
                  </label>
                  <button type="button" onClick={() => {
                    if (!email) { setError(lang === "fr" ? "Veuillez d'abord renseigner votre email." : "يرجى إدخال البريد الإلكتروني أولاً."); return; }
                    showToast(t("toastMagic"));
                  }} className="text-[11px] text-terra font-semibold hover:underline">
                    {t("magicLinkOption")}
                  </button>
                </div>

                <button type="submit" disabled={busy}
                        className="w-full bg-greenbrand hover:bg-[#18553f] text-white py-3 rounded-lg text-xs font-bold transition-all shadow-md flex items-center justify-center gap-2 mt-2 disabled:opacity-70">
                  <span>{busy ? t("verifying") : t("submitBtn")}</span>
                  {busy && <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />}
                </button>
              </form>
            </div>

            <div className="pt-6 mt-6 border-t border-line text-center text-xs text-muted">
              <span>{t("noAccount")}</span>
              <a href="/landing.html#acces" className="text-greenbrand font-bold hover:underline ms-1">
                {t("requestAccess")}
              </a>
            </div>
          </div>
        </div>
      </main>

      {/* FOOTER */}
      <footer className="w-full py-4 px-6 text-center text-[11px] text-muted border-t border-line/60 bg-[#f5f0e6ed]">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© 2026 Soukna — Service d&apos;intelligence marchés publics.</span>
          <div className="flex gap-4">
            <a href="/landing.html#mentions" className="hover:underline">{t("footerPrivacy")}</a>
            <a href="/landing.html#mentions" className="hover:underline">{t("footerTerms")}</a>
            <a href="/landing.html#mentions" className="hover:underline">{t("footerSupport")}</a>
          </div>
        </div>
      </footer>

      {toast && (
        <div className="fixed bottom-5 right-5 rtl:right-auto rtl:left-5 z-50 bg-ink text-white text-xs px-4 py-3 rounded-lg shadow-2xl max-w-xs flex items-center gap-2">
          <span>✓</span><span>{toast}</span>
        </div>
      )}
    </div>
  );
}
