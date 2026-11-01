"use client";

// Tableau de bord entreprise — port du mockup soukna_dashboard.html sur
// l'API réelle : opportunités matchées, score /100, verdict, risques,
// breakdown par facteur, pipeline "Mes Dossiers", profil et alertes.
// Bilingue FR/AR avec bascule RTL.

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, clearAuth, getAuth } from "../lib";
import BrandLoader from "../brand-loader";

type Profile = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  sectors: string[];
  keywords: string[];
  regions: string[];
  size: string;
  channel_whatsapp: boolean;
  channel_email: boolean;
  max_guarantee: number | null;
  alert_min_score: number;
  plan: string;
  trial_started_at: string | null;
  trial_ends_at: string | null;
  // profil étendu (optionnel)
  budget_min: number | null;
  budget_max: number | null;
  certifications: string[] | null;
  qualification: string | null;
  experience_years: number | null;
  website: string | null;
  linkedin: string | null;
};

type Opp = {
  id: string;
  opportunity_id: string;
  opportunity_type: string | null;
  match_score: number;
  reasons: string[] | null;
  verdict: string | null; // go | a_etudier | no_go
  risks: string[] | null;
  breakdown: Record<string, number> | null;
  status: string; // new | study | prep | submitted
  saved: boolean;
  note: string | null;
  title: string;
  buyer: string | null;
  city: string | null;
  region: string | null;
  sector: string | null;
  deadline: string | null;
  amount: string | null;
  source_ref: string;
  first_seen_at: string | null;
  url: string | null;
};

type Stats = {
  total: number;
  go: number;
  study: number;
  nogo: number;
  saved: number;
  new_24h: number;
  alert_min_score: number;
};

type Notif = {
  kind: "match" | "deadline";
  score: number;
  title: string;
  city: string | null;
  created_at: string;
  deadline?: string;
  days_left?: number;
};

type Digest = {
  digest_date: string;
  content: string;
  channels: string[] | null;
  created_at: string;
};

// ---------------------------------------------------------------- i18n
const T: Record<"fr" | "ar", Record<string, string>> = {
  fr: {
    searchPlaceholder: "Mots-clés, acheteur, ville...",
    notifTitle: "Notifications récentes",
    noNotif: "Aucune notification pour l'instant",
    tabFeed: "Tableau de bord",
    tabDossiers: "Mes Dossiers",
    tabProfile: "Profil Entreprise",
    tabAlerts: "Alertes & Synthèse",
    kpi1Title: "Nouvelles opportunités (24h)",
    kpi1Sub: "Scannées dans les avis publics",
    kpi2Title: "Matchs Élevés (GO)",
    kpi2Sub: "Match ≥ seuil de recommandation",
    kpi3Title: "Avis à étudier",
    kpi3Sub: "Points de risque à vérifier",
    kpi4Title: "Dossiers suivis",
    kpi4Tag: "Pipeline actif",
    kpi4Sub: "En cours de préparation",
    filterKeyword: "Filtrer par objet, référence...",
    allSectors: "Tous les secteurs",
    allCities: "Toutes les villes",
    allVerdicts: "Tous les verdicts",
    verdictGo: "✓ GO uniquement",
    verdictStudy: "! À étudier",
    verdictNogo: "× NO-GO",
    resetBtn: "Réinitialiser",
    oppsFound: "opportunités trouvées selon vos critères",
    sortBy: "Trier par :",
    sortMatch: "Score de Match (Décroissant)",
    sortDeadline: "Échéance imminente",
    noResultsTitle: "Aucune opportunité ne correspond à ces filtres",
    noResultsText: "Essayez de modifier votre recherche ou de réinitialiser vos filtres de sélection.",
    dossiersTitle: "Suivi des Dossiers & Candidatures",
    dossiersSub: "Organisez vos réponses aux appels d'offres et suivez vos pièces administratives.",
    colStudy: "En cours d'étude",
    colPrep: "Dossier en préparation",
    colSubmitted: "Soumis / Clôturé",
    emptyStudy: "Aucun dossier en étude",
    emptyPrep: "Aucun dossier en préparation",
    emptySubmitted: "Aucun dossier soumis pour le moment",
    notePlaceholder: "Ajouter une note d'équipe...",
    remove: "Retirer",
    statusStudy: "En étude",
    statusPrep: "En préparation",
    statusSubmitted: "Soumis",
    profileHeading: "Profil Entreprise & Capacités",
    profileDesc: "Mettez à jour vos critères d'entreprise pour recalculer l'algorithme de Match Soukna au prochain passage du pipeline.",
    profileNameLabel: "Nom de l'entreprise",
    profileSectorLabel: "Secteur Principal",
    profileSizeLabel: "Taille d'entreprise",
    profileCityLabel: "Régions d'intervention (séparées par des virgules)",
    profileGuaranteeLabel: "Capacité Garantie Provisoire Max (MAD)",
    profileKeywordsLabel: "Mots-clés d'activité (séparés par virgules)",
    profileNote: "Les recalculs s'appliqueront au prochain run du pipeline.",
    saveProfileBtn: "Enregistrer les modifications",
    alertsHeading: "Configuration des Alertes & Synthèse",
    alertsDesc: "Choisissez quand et comment recevoir vos opportunités personnalisées par email ou WhatsApp.",
    alertDailyTitle: "Synthèse (Email)",
    alertDailySub: "Recevez chaque matin les marchés filtrés pour votre entreprise.",
    alertWaTitle: "Alertes Instantanées WhatsApp",
    alertWaSub: "Soyez notifié directement sur WhatsApp dès qu'un Match dépasse votre seuil.",
    alertThreshTitle: "Seuil minimal de Match pour notification",
    lastDigest: "Dernière synthèse",
    noDigest: "Aucune synthèse reçue pour l'instant.",
    saveAlertsBtn: "Sauvegarder mes préférences",
    drawerSubtitle: "Analyse d'opportunité Soukna",
    matchLabel: "MATCH /100",
    breakdownHeader: "Détail des facteurs de Match",
    keyDeadline: "Date d'échéance",
    keyCity: "Localisation",
    keyBudget: "Budget / Montant",
    keySector: "Secteur",
    risksHeader: "Risques et points d'attention",
    noRisks: "Aucun risque particulier identifié.",
    officialSourceTitle: "Document Officiel & CPS",
    officialSourceDesc: "Le résumé Soukna est indicatif. Consultez le dossier de consultation officiel avant tout engagement.",
    openSourceBtn: "Ouvrir l'avis sur le portail",
    closeBtn: "Fermer",
    savedToast: "Opportunité enregistrée dans Mes Dossiers",
    removedToast: "Opportunité retirée de vos dossiers",
    profileSavedToast: "Profil entreprise sauvegardé ✅",
    alertSavedToast: "Préférences d'alertes enregistrées.",
    seeAnalysis: "Voir l'analyse",
    verdictGoPill: "GO — À considérer",
    verdictStudyPill: "À étudier",
    verdictNogoPill: "NO-GO",
    sectorFit: "Adéquation sectorielle",
    keywordFit: "Mots-clés & Métier",
    regionFit: "Proximité géographique",
    sizeFit: "Capacité & Taille",
    historyFit: "Historique & Références",
    notProvided: "Non renseigné",
    loading: "Préparation de vos opportunités…",
    logout: "Déconnexion",
    match: "MATCH",
    footer: "© 2026 Soukna — Intelligence des marchés publics au Maroc",
  },
  ar: {
    searchPlaceholder: "كلمات مفتاحية، جهة الشراء، المدينة...",
    notifTitle: "الإشعارات الأخيرة",
    noNotif: "لا توجد إشعارات حالياً",
    tabFeed: "لوحة القيادة",
    tabDossiers: "ملفاتي",
    tabProfile: "ملف الشركة",
    tabAlerts: "التنبيهات والملخص",
    kpi1Title: "فرص جديدة (24 ساعة)",
    kpi1Sub: "تم مسحها في الإعلانات العمومية",
    kpi2Title: "توافق مرتفع (تقدّم)",
    kpi2Sub: "توافق فوق حد التوصية",
    kpi3Title: "عروض للدراسة",
    kpi3Sub: "نقاط خطر تتطلب التحقق",
    kpi4Title: "ملفات قيد المتابعة",
    kpi4Tag: "متابعة نشطة",
    kpi4Sub: "قيد التحضير",
    filterKeyword: "تصفية حسب الموضوع أو المرجع...",
    allSectors: "جميع القطاعات",
    allCities: "جميع المدن",
    allVerdicts: "جميع التوصيات",
    verdictGo: "✓ تقدّم فقط",
    verdictStudy: "! للدراسة",
    verdictNogo: "× تجاوز",
    resetBtn: "إعادة ضبط",
    oppsFound: "فرص تم العثور عليها وفق معاييرك",
    sortBy: "ترتيب حسب:",
    sortMatch: "درجة التوافق (تنازلي)",
    sortDeadline: "الاقتراب من آخر أجل",
    noResultsTitle: "لا توجد فرص تطابق هذه المرشحات",
    noResultsText: "جرب تغيير البحث أو إعادة ضبط مرشحات الاختيار.",
    dossiersTitle: "متابعة الملفات الترشيحية",
    dossiersSub: "نظم إجاباتك على طلبات العروض وتابع الوثائق الإدارية.",
    colStudy: "قيد الدراسة",
    colPrep: "الملف قيد التحضير",
    colSubmitted: "تم الإرسال / مغلق",
    emptyStudy: "لا يوجد ملف قيد الدراسة",
    emptyPrep: "لا يوجد ملف قيد التحضير",
    emptySubmitted: "لا يوجد ملف مرسل حالياً",
    notePlaceholder: "أضف ملاحظة للفريق...",
    remove: "إزالة",
    statusStudy: "قيد الدراسة",
    statusPrep: "قيد التحضير",
    statusSubmitted: "تم الإرسال",
    profileHeading: "ملف الشركة والقدرات",
    profileDesc: "قم بتحديث معايير شركتك لإعادة حساب خوارزمية التوافق في المرور القادم.",
    profileNameLabel: "اسم الشركة",
    profileSectorLabel: "القطاع الرئيسي",
    profileSizeLabel: "حجم الشركة",
    profileCityLabel: "مناطق التدخل (مفصولة بفواصل)",
    profileGuaranteeLabel: "الحد الأقصى للضمان المؤقت (درهم)",
    profileKeywordsLabel: "الكلمات المفتاحية للنشاط (مفصولة بفواصل)",
    profileNote: "ستطبق الحسابات الجديدة في المرور القادم للنظام.",
    saveProfileBtn: "حفظ التغييرات",
    alertsHeading: "إعداد التنبيهات والملخص",
    alertsDesc: "اختر وقت وطريقة استلام الفرص المخصصة عبر البريد أو الواتساب.",
    alertDailyTitle: "الملخص (بريد إلكتروني)",
    alertDailySub: "استلم كل صباح الصفقات المفلترة لشركتك.",
    alertWaTitle: "تنبيهات فورية عبر الواتساب",
    alertWaSub: "احصل على إشعار مباشر فور تجاوز درجة التوافق لحدك.",
    alertThreshTitle: "الحد الأدنى للتوافق للإشعار",
    lastDigest: "آخر ملخص",
    noDigest: "لا يوجد ملخص مستلم حالياً.",
    saveAlertsBtn: "حفظ التفضيلات",
    drawerSubtitle: "تحليل الفرصة من Soukna",
    matchLabel: "التوافق /100",
    breakdownHeader: "تفاصيل عوامل التوافق",
    keyDeadline: "تاريخ آخر أجل",
    keyCity: "الموقع الجغرافي",
    keyBudget: "الميزانية / المبلغ",
    keySector: "القطاع",
    risksHeader: "المخاطر ونقاط الانتباه",
    noRisks: "لا توجد مخاطر خاصة تم تحديدها.",
    officialSourceTitle: "الوثيقة الرسمية ودفتر الشروط",
    officialSourceDesc: "ملخص Soukna إرشادي. يرجى الاطلاع على ملف الاستشارة الرسمي قبل أي التزام.",
    openSourceBtn: "فتح الإعلان على البوابة",
    closeBtn: "إغلاق",
    savedToast: "تم حفظ الفرصة في ملفاتي",
    removedToast: "تم إزالة الفرصة من ملفاتك",
    profileSavedToast: "تم حفظ ملف الشركة ✅",
    alertSavedToast: "تم حفظ تفضيلات التنبيهات.",
    seeAnalysis: "عرض التحليل",
    verdictGoPill: "تقدّم — ممتازة",
    verdictStudyPill: "للدراسة",
    verdictNogoPill: "تجاوز",
    sectorFit: "ملاءمة القطاع",
    keywordFit: "الكلمات المفتاحية والمهنة",
    regionFit: "القرب الجغرافي",
    sizeFit: "القدرة والحجم",
    historyFit: "السجل والخبرة السابقة",
    notProvided: "غير محدد",
    loading: "جارٍ تحضير الفرص الخاصة بك…",
    logout: "تسجيل الخروج",
    match: "التوافق",
    footer: "© 2026 Soukna — ذكاء طلبات العروض العمومية بالمغرب",
  },
};

const SECTOR_OPTIONS = [
  "Informatique",
  "BTP",
  "Fournitures",
  "Services et maintenance",
  "Conseil et études",
];

const RING_LEN = 251.2;
const ringOffset = (score: number) => RING_LEN - (Math.max(0, Math.min(100, score)) * RING_LEN) / 100;

function fmtDate(d: string | null | undefined, lang: "fr" | "ar"): string {
  if (!d) return "—";
  const date = new Date(d.length === 10 ? `${d}T12:00:00` : d);
  if (isNaN(date.getTime())) return d;
  return new Intl.DateTimeFormat(lang === "fr" ? "fr-MA" : "ar-MA", {
    day: "numeric", month: "short", year: "numeric",
  }).format(date);
}

export default function DashboardPage() {
  const [lang, setLang] = useState<"fr" | "ar">("fr");
  const [tab, setTab] = useState<"feed" | "dossiers" | "profile" | "alerts">("feed");
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [opps, setOpps] = useState<Opp[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [digests, setDigests] = useState<Digest[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);

  // Filtres du flux
  const [kw, setKw] = useState("");
  const [sector, setSector] = useState("all");
  const [city, setCity] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [otype, setOtype] = useState("all");
  const [fNew, setFNew] = useState(false);
  const [sort, setSort] = useState("score");

  // Drawer
  const [activeId, setActiveId] = useState<string | null>(null);

  // Formulaire profil
  const [fName, setFName] = useState("");
  const [fSector, setFSector] = useState("");
  const [fKeywords, setFKeywords] = useState("");
  const [fRegions, setFRegions] = useState("");
  const [fSize, setFSize] = useState("pme");
  const [fGuarantee, setFGuarantee] = useState("");
  const [fBudgetMin, setFBudgetMin] = useState("");
  const [fBudgetMax, setFBudgetMax] = useState("");
  const [fCerts, setFCerts] = useState("");
  const [fQualif, setFQualif] = useState("");
  const [fExp, setFExp] = useState("");

  // Alertes
  const [waEnabled, setWaEnabled] = useState(true);
  const [mailEnabled, setMailEnabled] = useState(true);
  const [thresh, setThresh] = useState(70);

  const t = (key: string) => T[lang][key] ?? key;

  useEffect(() => {
    const auth = getAuth();
    if (!auth) {
      window.location.href = "/login";
      return;
    }
    if (auth.role !== "entreprise") {
      window.location.href = "/admin";
      return;
    }
    (async () => {
      try {
        const p = await api<Profile>("/profile");
        setProfile(p);
        setFName(p.name);
        setFSector((p.sectors || [])[0] || "");
        setFKeywords((p.keywords || []).join(", "));
        setFRegions((p.regions || []).join(", "));
        setFSize(p.size || "pme");
        setFGuarantee(p.max_guarantee != null ? String(p.max_guarantee) : "");
        setFBudgetMin(p.budget_min != null ? String(p.budget_min) : "");
        setFBudgetMax(p.budget_max != null ? String(p.budget_max) : "");
        setFCerts((p.certifications || []).join(", "));
        setFQualif(p.qualification || "");
        setFExp(p.experience_years != null ? String(p.experience_years) : "");
        setWaEnabled(!!p.channel_whatsapp);
        setMailEnabled(!!p.channel_email);
        setThresh(p.alert_min_score || 70);
        const [o, s, n, d] = await Promise.all([
          api<Opp[]>(fNew ? "/opportunities?new_since_hours=24" : "/opportunities"),
          api<Stats>("/company/stats"),
          api<Notif[]>("/notifications"),
          api<Digest[]>("/digests"),
        ]);
        setOpps(o || []);
        setStats(s);
        setNotifs(n || []);
        setDigests(d || []);
      } catch (exc) {
        setErr((exc as Error).message);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  // Re-fetch des opportunités quand le filtre « nouveaux 24 h » change
  useEffect(() => {
    if (!loaded) return;
    (async () => {
      try {
        setOpps(await api<Opp[]>(
          fNew ? "/opportunities?new_since_hours=24" : "/opportunities"));
      } catch (exc) { setErr((exc as Error).message); }
    })();
  }, [fNew, loaded]);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3000);
  }

  function toggleLang() {
    const next = lang === "fr" ? "ar" : "fr";
    setLang(next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
  }

  const verdictKey = (v: string | null) =>
    v === "go" ? "go" : v === "no_go" ? "nogo" : "study";

  function verdictPill(v: string | null): { cls: string; label: string } {
    const key = verdictKey(v);
    if (key === "go") return { cls: "bg-greenbg text-greenbrand border border-greenbrand/20", label: `✓ ${t("verdictGoPill")}` };
    if (key === "study") return { cls: "bg-amberbg text-amberbrand border border-amberbrand/20", label: `! ${t("verdictStudyPill")}` };
    return { cls: "bg-redbg text-redbrand border border-redbrand/20", label: `× ${t("verdictNogoPill")}` };
  }

  // ------------------------------------------------ filtrage & tri
  const sectors = useMemo(
    () => Array.from(new Set(opps.map((o) => o.sector).filter((s): s is string => !!s))).sort(),
    [opps],
  );
  const cities = useMemo(
    () => Array.from(new Set(opps.map((o) => o.city).filter((c): c is string => !!c))).sort(),
    [opps],
  );

  const filtered = useMemo(() => {
    const needle = kw.trim().toLowerCase();
    const out = opps.filter((o) => {
      const matchKw =
        !needle ||
        o.title.toLowerCase().includes(needle) ||
        (o.buyer || "").toLowerCase().includes(needle) ||
        (o.city || "").toLowerCase().includes(needle) ||
        o.source_ref.toLowerCase().includes(needle);
      const matchSector = sector === "all" || o.sector === sector;
      const matchCity = city === "all" || o.city === city;
      const matchVerdict = verdict === "all" || verdictKey(o.verdict) === verdict;
      const matchType = otype === "all" || (o.opportunity_type || "appel_offres") === otype;
      return matchKw && matchSector && matchCity && matchVerdict && matchType;
    });
    out.sort((a, b) => {
      if (sort === "deadline") {
        return (a.deadline || "9999").localeCompare(b.deadline || "9999");
      }
      return b.match_score - a.match_score;
    });
    return out;
  }, [opps, kw, sector, city, verdict, sort, lang, otype]);

  const saved = useMemo(() => opps.filter((o) => o.saved), [opps]);
  const activeOpp = activeId ? opps.find((o) => o.id === activeId) : null;

  // ------------------------------------------------ mutations API
  async function patchMatch(id: string, patch: Record<string, unknown>) {
    const updated = await api<Opp>(`/matches/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    setOpps((prev) => prev.map((o) => (o.id === id ? { ...o, ...updated } : o)));
    return updated;
  }

  async function toggleSave(o: Opp) {
    setErr("");
    try {
      await patchMatch(o.id, { saved: !o.saved });
      showToast(!o.saved ? t("savedToast") : t("removedToast"));
    } catch (exc) {
      setErr((exc as Error).message);
    }
  }

  async function changeStatus(o: Opp, status: string) {
    setErr("");
    try {
      await patchMatch(o.id, { status });
    } catch (exc) {
      setErr((exc as Error).message);
    }
  }

  async function saveNote(o: Opp, note: string) {
    if (note === (o.note || "")) return;
    setErr("");
    try {
      await patchMatch(o.id, { note });
    } catch (exc) {
      setErr((exc as Error).message);
    }
  }

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    const split = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
    try {
      const p = await api<Profile>("/profile", {
        method: "PATCH",
        body: JSON.stringify({
          name: fName,
          sectors: fSector ? [fSector] : [],
          keywords: split(fKeywords),
          regions: split(fRegions),
          size: fSize,
          max_guarantee: fGuarantee ? parseInt(fGuarantee, 10) : null,
          budget_min: fBudgetMin ? Number(fBudgetMin) : null,
          budget_max: fBudgetMax ? Number(fBudgetMax) : null,
          certifications: split(fCerts),
          qualification: fQualif || null,
          experience_years: fExp ? parseInt(fExp, 10) : null,
        }),
      });
      setProfile(p);
      showToast(t("profileSavedToast"));
    } catch (exc) {
      setErr((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveAlerts() {
    setErr("");
    setBusy(true);
    try {
      const p = await api<Profile>("/profile", {
        method: "PATCH",
        body: JSON.stringify({
          channel_whatsapp: waEnabled,
          channel_email: mailEnabled,
          alert_min_score: thresh,
        }),
      });
      setProfile(p);
      showToast(t("alertSavedToast"));
    } catch (exc) {
      setErr((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function resetFilters() {
    setKw("");
    setSector("all");
    setCity("all");
    setVerdict("all");
    setOtype("all");
    setSort("score");
  }

  // ------------------------------------------------ vues
  const headerEl = (
    <header className="sticky top-0 z-40 bg-[#f5f0e6ed] backdrop-blur-md border-b border-[#dcd6cb] px-4 lg:px-8 py-3">
      <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <a href="/" className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
            <svg className="w-8 h-8 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
              <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
              <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
              <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
            </svg>
            <span className="font-display">Soukna</span>
            <span className="text-[10px] uppercase tracking-wider bg-greenbg text-greenbrand px-2 py-0.5 rounded font-bold border border-greenbrand/20 hidden sm:inline-block">
              Espace Pro
            </span>
          </a>
          <div className="hidden md:flex items-center relative w-64 lg:w-80">
            <svg className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 rtl:right-3 rtl:left-auto text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={kw}
              onChange={(e) => { setKw(e.target.value); setTab("feed"); }}
              placeholder={t("searchPlaceholder")}
              className="w-full bg-white border border-line rounded-lg pl-9 rtl:pr-9 rtl:pl-3 pr-3 py-1.5 text-xs text-ink placeholder-muted focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleLang}
            type="button"
            className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink transition-all flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
            </svg>
            <span>{lang === "fr" ? "العربية" : "Français"}</span>
          </button>

          <div className="relative">
            <button
              onClick={() => setNotifOpen((v) => !v)}
              type="button"
              className="border border-line bg-white hover:bg-paper p-2 rounded-md text-ink relative transition-all"
              aria-label="Notifications"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {notifs.length > 0 && (
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-terra rounded-full ring-2 ring-white" />
              )}
            </button>
            {notifOpen && (
              <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-80 bg-white border border-line rounded-lg shadow-xl p-3 z-50">
                <div className="flex items-center justify-between border-b border-line pb-2 mb-2">
                  <span className="text-xs font-bold text-ink">{t("notifTitle")}</span>
                  {notifs.length > 0 && (
                    <span className="text-[10px] bg-greenbg text-greenbrand px-1.5 py-0.5 rounded font-bold">
                      {notifs.length}
                    </span>
                  )}
                </div>
                <div className="space-y-2 text-xs max-h-72 overflow-y-auto">
                  {notifs.length === 0 && (
                    <p className="text-muted py-3 text-center">{t("noNotif")}</p>
                  )}
                  {notifs.map((n, i) => (
                    <div key={i} className="p-2 bg-paper/60 rounded border border-line/50">
                      <p className="font-semibold text-ink">
                        {n.kind === "deadline"
                          ? `${t("keyDeadline")} · ${n.days_left}j — ${n.title}`
                          : `${t("match")} ${n.score}% — ${n.title}`}
                      </p>
                      <span className="text-[10px] text-muted">
                        {n.city ? `${n.city} · ` : ""}{fmtDate(n.created_at, lang)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pl-2 border-l rtl:border-l-0 rtl:border-r rtl:pl-0 rtl:pr-2 border-line">
            <div className="w-8 h-8 rounded-full bg-greenbrand text-white flex items-center justify-center font-bold text-xs shadow-sm">
              {(profile?.name || "S").slice(0, 2).toUpperCase()}
            </div>
            <div className="hidden lg:block text-left rtl:text-right">
              <div className="text-xs font-bold text-ink leading-none">{profile?.name}</div>
              <div className="text-[10px] text-muted mt-0.5">{profile?.email}</div>
            </div>
            <button
              onClick={() => { clearAuth(); window.location.href = "/login"; }}
              className="text-[11px] font-semibold text-muted hover:text-redbrand transition-colors ms-2"
            >
              {t("logout")}
            </button>
          </div>
        </div>
      </div>
    </header>
  );

  const tabsEl = (
    <nav className="bg-white border-b border-line px-4 lg:px-8">
      <div className="max-w-[1400px] mx-auto flex items-center gap-1 sm:gap-6 overflow-x-auto no-scrollbar py-1">
        {([
          ["feed", t("tabFeed")],
          ["dossiers", t("tabDossiers")],
          ["profile", t("tabProfile")],
          ["alerts", t("tabAlerts")],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`tab-btn px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium text-muted hover:text-ink transition-all flex items-center gap-2 whitespace-nowrap ${tab === id ? "active" : ""}`}
          >
            {label}
            {id === "dossiers" && (
              <span className="bg-paper text-ink border border-line text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {saved.length}
              </span>
            )}
          </button>
        ))}
      </div>
    </nav>
  );

  const kpisEl = (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { id: "kpiTotal", value: stats?.new_24h ?? 0, cls: "text-ink", tag: "+24h", tagCls: "text-greenbrand bg-greenbg", title: t("kpi1Title"), sub: t("kpi1Sub") },
        { id: "kpiGo", value: stats?.go ?? 0, cls: "text-greenbrand", tag: "GO", tagCls: "text-greenbrand bg-greenbg", title: t("kpi2Title"), sub: t("kpi2Sub") },
        { id: "kpiStudy", value: stats?.study ?? 0, cls: "text-amberbrand", tag: "60-79%", tagCls: "text-amberbrand bg-amberbg", title: t("kpi3Title"), sub: t("kpi3Sub") },
        { id: "kpiSaved", value: stats?.saved ?? 0, cls: "text-terra", tag: t("kpi4Tag"), tagCls: "text-muted bg-paper", title: t("kpi4Title"), sub: t("kpi4Sub") },
      ].map((k) => (
        <div key={k.id} className="bg-white border border-line rounded-lg p-4 shadow-sm">
          <div className="text-[11px] font-bold text-muted uppercase tracking-wider mb-1">{k.title}</div>
          <div className="flex items-baseline justify-between">
            <span className={`text-3xl font-bold font-display ${k.cls}`}>{k.value}</span>
            <span className={`text-xs px-2 py-0.5 rounded font-semibold ${k.tagCls}`}>{k.tag}</span>
          </div>
          <div className="text-[11px] text-muted mt-2">{k.sub}</div>
        </div>
      ))}
    </section>
  );

  function oppCard(o: Opp) {
    const pill = verdictPill(o.verdict);
    const risks = (o.risks || []).slice(0, 3);
    return (
      <article key={o.id} className="bg-white border border-line rounded-lg p-4 shadow-sm hover:shadow-md transition-all flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between gap-2 border-b border-line/60 pb-3 mb-3">
            <div>
              <span className="text-[10px] uppercase font-bold text-terra tracking-wider block">{o.source_ref}</span>
              <h3 className="font-display font-bold text-sm text-ink leading-snug mt-0.5 line-clamp-2">{o.title}</h3>
              <div className="text-[11px] text-muted mt-1">{o.buyer || "—"}</div>
              {o.first_seen_at && (Date.now() - new Date(o.first_seen_at).getTime()) < 24 * 3600 * 1000 && (
                <span className="inline-block mr-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-greenbrand text-white">
                  {lang === "ar" ? "جديد" : "NOUVEAU"}
                </span>
              )}
              {o.opportunity_type && o.opportunity_type !== "appel_offres" && (
                <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                  {o.opportunity_type === "bon_commande"
                    ? (lang === "ar" ? "أمر بالتأدية" : "Bon de commande")
                    : (lang === "ar" ? "استشارة" : "Consultation")}
                </span>
              )}
            </div>
            <div className="flex flex-col items-center justify-center flex-shrink-0">
              <div className="w-12 h-12 relative flex items-center justify-center">
                <svg className="ring-svg w-full h-full" viewBox="0 0 100 100">
                  <circle className="ring-track" cx="50" cy="50" r="40" />
                  <circle className="ring-value" cx="50" cy="50" r="40" style={{ strokeDashoffset: ringOffset(o.match_score) }} />
                </svg>
                <span className="absolute font-display font-bold text-xs text-ink">{o.match_score}</span>
              </div>
              <span className="text-[9px] font-bold text-muted uppercase mt-0.5">{t("match")}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] text-muted mb-3 bg-paper/50 p-2 rounded">
            <div>
              <span className="block text-[9px] font-bold uppercase text-muted">{t("keyDeadline")}</span>
              <strong className="text-ink font-semibold">◷ {fmtDate(o.deadline, lang)}</strong>
            </div>
            <div>
              <span className="block text-[9px] font-bold uppercase text-muted">{t("keyCity")}</span>
              <strong className="text-ink font-semibold">⌖ {o.city || o.region || t("notProvided")}</strong>
            </div>
          </div>

          {risks.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {risks.map((r, i) => (
                <span key={i} className="text-[10px] bg-paper border border-line px-1.5 py-0.5 rounded text-muted line-clamp-1">
                  ! {r}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="pt-3 border-t border-line flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${pill.cls}`}>{pill.label}</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => toggleSave(o)}
              className="p-1.5 rounded border border-line hover:bg-paper transition-all"
              aria-label="save"
            >
              <span className={o.saved ? "text-terra font-bold" : "text-muted"}>★</span>
            </button>
            <button
              onClick={() => setActiveId(o.id)}
              className="bg-greenbrand hover:bg-[#18553f] text-white text-xs font-bold px-3 py-1.5 rounded transition-all"
            >
              {t("seeAnalysis")}
            </button>
          </div>
        </div>
      </article>
    );
  }

  const feedEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-4 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="w-full md:w-1/3 relative">
            <input
              type="text"
              value={kw}
              onChange={(e) => setKw(e.target.value)}
              placeholder={t("filterKeyword")}
              className="w-full bg-paper/50 border border-line rounded-md px-3 py-2 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all"
            />
          </div>
          <div className="w-full md:w-2/3 flex flex-wrap items-center justify-end gap-2 text-xs">
            <select value={sector} onChange={(e) => setSector(e.target.value)} className="flex-1 min-w-[130px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand">
              <option value="all">{t("allSectors")}</option>
              {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={city} onChange={(e) => setCity(e.target.value)} className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand">
              <option value="all">{t("allCities")}</option>
              {cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={verdict} onChange={(e) => setVerdict(e.target.value)} className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand">
              <option value="all">{t("allVerdicts")}</option>
              <option value="go">{t("verdictGo")}</option>
              <option value="study">{t("verdictStudy")}</option>
              <option value="nogo">{t("verdictNogo")}</option>
            </select>
            <select value={otype} onChange={(e) => setOtype(e.target.value)} className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand">
              <option value="all">{lang === "ar" ? "كل الأنواع" : "Tous les types"}</option>
              <option value="appel_offres">{lang === "ar" ? "مناقصة" : "Appel d'offres"}</option>
              <option value="bon_commande">{lang === "ar" ? "أمر بالتأدية" : "Bon de commande"}</option>
              <option value="consultation">{lang === "ar" ? "استشارة" : "Consultation"}</option>
            </select>
            <button onClick={() => { setFNew(!fNew); }}
                    className={`px-3 py-2 rounded-md text-xs font-bold border transition-all ${fNew ? "bg-greenbrand text-white border-greenbrand" : "bg-paper/50 border-line text-muted hover:text-ink"}`}>
              {lang === "ar" ? "🆕 جديد 24س" : "🆕 Nouveaux 24h"}
            </button>
            <button onClick={resetFilters} className="bg-paper hover:bg-line border border-line text-muted hover:text-ink px-3 py-2 rounded-md font-semibold transition-all">
              {t("resetBtn")}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-line/60 text-xs text-muted">
          <div>
            <span className="font-bold text-ink">{filtered.length}</span> {t("oppsFound")}
          </div>
          <div className="flex items-center gap-2">
            <span>{t("sortBy")}</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="bg-transparent border-0 text-ink font-semibold focus:ring-0 cursor-pointer p-0 text-xs">
              <option value="score">{t("sortMatch")}</option>
              <option value="deadline">{t("sortDeadline")}</option>
            </select>
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white border border-dashed border-line rounded-lg p-12 text-center text-muted">
          <h3 className="text-base font-bold text-ink">{t("noResultsTitle")}</h3>
          <p className="text-xs mt-1">{t("noResultsText")}</p>
          <button onClick={resetFilters} className="mt-4 bg-greenbrand text-white text-xs font-bold px-4 py-2 rounded hover:bg-[#18553f] transition-all">
            {t("resetBtn")}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(oppCard)}
        </div>
      )}
    </section>
  );

  function dossierCard(o: Opp) {
    return (
      <div key={o.id} className="bg-white border border-line rounded p-3 shadow-sm space-y-2 text-xs">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-bold text-ink leading-tight">{o.title}</h4>
          <span className="font-display font-bold text-greenbrand text-xs">{o.match_score}%</span>
        </div>
        <div className="text-[11px] text-muted">
          {o.city || "—"} · {fmtDate(o.deadline, lang)}
        </div>
        <input
          type="text"
          defaultValue={o.note || ""}
          onBlur={(e) => saveNote(o, e.target.value)}
          placeholder={t("notePlaceholder")}
          className="w-full bg-paper/50 border border-line rounded px-2 py-1 text-[11px] text-ink placeholder-muted focus:bg-white"
        />
        <div className="flex items-center justify-between pt-1 text-[10px]">
          <select
            value={o.status === "new" ? "study" : o.status}
            onChange={(e) => changeStatus(o, e.target.value)}
            className="bg-paper border border-line rounded px-1.5 py-0.5 text-ink font-semibold"
          >
            <option value="study">{t("statusStudy")}</option>
            <option value="prep">{t("statusPrep")}</option>
            <option value="submitted">{t("statusSubmitted")}</option>
          </select>
          <button onClick={() => toggleSave(o)} className="text-redbrand font-bold hover:underline">
            {t("remove")}
          </button>
        </div>
      </div>
    );
  }

  const dossiersEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-4 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-bold text-ink">{t("dossiersTitle")}</h2>
          <p className="text-xs text-muted">{t("dossiersSub")}</p>
        </div>
        <button onClick={() => setTab("feed")} className="bg-greenbrand text-white px-3 py-1.5 rounded text-xs font-bold hover:bg-[#18553f] transition-all">
          + {t("tabFeed")}
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {([
          ["study", t("colStudy"), t("emptyStudy"), "bg-amberbrand"],
          ["prep", t("colPrep"), t("emptyPrep"), "bg-terra"],
          ["submitted", t("colSubmitted"), t("emptySubmitted"), "bg-greenbrand"],
        ] as const).map(([status, label, empty, dot]) => {
          const list = saved.filter((o) => (o.status === "new" ? "study" : o.status) === status);
          return (
            <div key={status} className="bg-paper/60 border border-line rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <span className="text-xs font-bold text-ink flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${dot}`} />
                  {label}
                </span>
                <span className="text-xs font-bold text-muted">{list.length}</span>
              </div>
              <div className="space-y-3">
                {list.length === 0
                  ? <div className="text-center text-xs text-muted py-4">{empty}</div>
                  : list.map(dossierCard)}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );

  const profileEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-6 shadow-sm max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">{t("profileHeading")}</h2>
          <p className="text-xs text-muted mt-1">{t("profileDesc")}</p>
        </div>
        <form onSubmit={saveProfile} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block text-xs font-bold text-ink">
              {t("profileNameLabel")}
              <input value={fName} onChange={(e) => setFName(e.target.value)} required
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileSectorLabel")}
              <select value={fSector} onChange={(e) => setFSector(e.target.value)}
                      className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink">
                <option value="">—</option>
                {SECTOR_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileSizeLabel")}
              <select value={fSize} onChange={(e) => setFSize(e.target.value)}
                      className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink">
                <option value="petite">TPE / petite entreprise</option>
                <option value="pme">PME</option>
                <option value="grande">Grande entreprise</option>
              </select>
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileCityLabel")}
              <input value={fRegions} onChange={(e) => setFRegions(e.target.value)} placeholder="Casablanca, Rabat"
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileGuaranteeLabel")}
              <input type="number" min={0} value={fGuarantee} onChange={(e) => setFGuarantee(e.target.value)}
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {lang === "ar" ? "الميزانية الدنيا (درهم)" : "Budget min (MAD)"}
              <input type="number" min={0} value={fBudgetMin} onChange={(e) => setFBudgetMin(e.target.value)}
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {lang === "ar" ? "الميزانية القصوى (درهم)" : "Budget max (MAD)"}
              <input type="number" min={0} value={fBudgetMax} onChange={(e) => setFBudgetMax(e.target.value)}
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {lang === "ar" ? "الشهادات (مفصولة بفواصل)" : "Certifications (séparées par ,)"}
              <input value={fCerts} onChange={(e) => setFCerts(e.target.value)} placeholder="ISO 9001, ISO 14001"
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {lang === "ar" ? "التصنيف" : "Qualification / classement"}
              <input value={fQualif} onChange={(e) => setFQualif(e.target.value)} placeholder="Classe II — Travaux publics"
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {lang === "ar" ? "سنوات الخبرة" : "Années d'expérience"}
              <input type="number" min={0} value={fExp} onChange={(e) => setFExp(e.target.value)}
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileKeywordsLabel")}
              <input value={fKeywords} onChange={(e) => setFKeywords(e.target.value)} placeholder="maintenance, informatique"
                     className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
          </div>
          <div className="pt-4 border-t border-line flex items-center justify-between">
            <span className="text-[11px] text-muted">{t("profileNote")}</span>
            <button type="submit" disabled={busy}
                    className="bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded text-xs font-bold transition-all shadow-sm disabled:opacity-60">
              {t("saveProfileBtn")}
            </button>
          </div>
        </form>
      </div>
    </section>
  );

  const alertsEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-6 shadow-sm max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">{t("alertsHeading")}</h2>
          <p className="text-xs text-muted mt-1">{t("alertsDesc")}</p>
        </div>
        <div className="space-y-4 text-xs">
          <div className="p-4 bg-paper/50 border border-line rounded-lg flex items-center justify-between">
            <div>
              <div className="font-bold text-ink">{t("alertDailyTitle")}</div>
              <div className="text-muted text-[11px]">{t("alertDailySub")}</div>
            </div>
            <input type="checkbox" checked={mailEnabled} onChange={(e) => setMailEnabled(e.target.checked)}
                   className="w-4 h-4 accent-greenbrand cursor-pointer" />
          </div>
          <div className="p-4 bg-paper/50 border border-line rounded-lg flex items-center justify-between">
            <div>
              <div className="font-bold text-ink">{t("alertWaTitle")}</div>
              <div className="text-muted text-[11px]">{t("alertWaSub")}</div>
            </div>
            <input type="checkbox" checked={waEnabled} onChange={(e) => setWaEnabled(e.target.checked)}
                   className="w-4 h-4 accent-greenbrand cursor-pointer" />
          </div>
          <div className="p-4 bg-paper/50 border border-line rounded-lg space-y-2">
            <div className="flex items-center justify-between font-bold text-ink">
              <span>{t("alertThreshTitle")}</span>
              <span className="text-greenbrand font-extrabold text-sm">{thresh}%</span>
            </div>
            <input type="range" min={50} max={90} step={5} value={thresh}
                   onChange={(e) => setThresh(parseInt(e.target.value, 10))}
                   className="w-full accent-greenbrand cursor-pointer" />
            <div className="flex justify-between text-[10px] text-muted">
              <span>50%</span>
              <span>70%</span>
              <span>90%</span>
            </div>
          </div>
        </div>
        <div className="pt-4 border-t border-line text-right">
          <button onClick={saveAlerts} disabled={busy}
                  className="bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded text-xs font-bold transition-all shadow-sm disabled:opacity-60">
            {t("saveAlertsBtn")}
          </button>
        </div>
        <div className="pt-4 border-t border-line">
          <h3 className="text-xs font-bold text-ink uppercase tracking-wider mb-2">{t("lastDigest")}</h3>
          {digests.length === 0 ? (
            <p className="hint">{t("noDigest")}</p>
          ) : (
            <div className="panel !m-0">
              <div className="hint mb-2">
                {fmtDate(digests[0].digest_date, lang)} · {(digests[0].channels || []).join(", ")}
              </div>
              <pre className="digest-pre">{digests[0].content}</pre>
            </div>
          )}
        </div>
      </div>
    </section>
  );

  // ------------------------------------------------ drawer
  const breakdownKeys: Array<[string, string]> = [
    ["sector", "sectorFit"],
    ["keywords", "keywordFit"],
    ["region", "regionFit"],
    ["size", "sizeFit"],
    ["history", "historyFit"],
  ];

  const drawerEl = (
    <div
      className={`drawer-backdrop ${activeOpp ? "open" : ""}`}
      onClick={(e) => { if (e.target === e.currentTarget) setActiveId(null); }}
      aria-hidden={!activeOpp}
    >
      <aside className="drawer-panel p-6">
        {activeOpp && (() => {
          const pill = verdictPill(activeOpp.verdict);
          const bd = activeOpp.breakdown || {};
          const bdEntries = breakdownKeys
            .filter(([k]) => typeof bd[k] === "number")
            .map(([k, label]) => [k, label, bd[k] as number] as const);
          return (
            <div className="flex flex-col justify-between min-h-full">
              <div className="space-y-6">
                <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-terra">{t("drawerSubtitle")}</span>
                    <h2 className="font-display text-xl font-bold text-ink leading-tight mt-1">{activeOpp.title}</h2>
                    <p className="text-xs text-muted mt-1">{activeOpp.buyer || "—"} · {activeOpp.source_ref}</p>
                  </div>
                  <button onClick={() => setActiveId(null)} type="button"
                          className="border border-line rounded-md p-1.5 hover:bg-paper text-ink transition-all">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="bg-paper/60 border border-line rounded-lg p-4 flex items-center gap-4">
                  <div className="relative w-20 h-20 flex-shrink-0">
                    <svg className="ring-svg w-full h-full" viewBox="0 0 100 100">
                      <circle className="ring-track" cx="50" cy="50" r="40" />
                      <circle className="ring-value" cx="50" cy="50" r="40" style={{ strokeDashoffset: ringOffset(activeOpp.match_score) }} />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                      <span className="font-display font-bold text-xl text-ink leading-none">{activeOpp.match_score}</span>
                      <span className="text-[8px] font-bold text-muted uppercase mt-0.5">{t("matchLabel")}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className={`inline-flex items-center gap-1 font-bold text-xs px-2 py-0.5 rounded ${pill.cls}`}>
                      {pill.label}
                    </span>
                    <p className="text-xs text-muted leading-snug">
                      {(activeOpp.reasons || []).join(" ") || "—"}
                    </p>
                  </div>
                </div>

                {bdEntries.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">
                      {t("breakdownHeader")}
                    </h3>
                    <div className="space-y-2 text-xs">
                      {bdEntries.map(([k, label, val]) => (
                        <div key={k} className="space-y-0.5">
                          <div className="flex justify-between font-semibold text-ink">
                            <span>{t(label)}</span>
                            <span>{val}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-paper rounded-full overflow-hidden border border-line/40">
                            <div className="h-full bg-greenbrand" style={{ width: `${val}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    [t("keyDeadline"), fmtDate(activeOpp.deadline, lang)],
                    [t("keyCity"), activeOpp.city || activeOpp.region || t("notProvided")],
                    [t("keyBudget"), activeOpp.amount || t("notProvided")],
                    [t("keySector"), activeOpp.sector || t("notProvided")],
                  ].map(([label, value], i) => (
                    <div key={i} className="bg-paper p-2.5 rounded border border-line">
                      <span className="text-[10px] text-muted block">{label}</span>
                      <strong className="text-ink font-bold">{value}</strong>
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">
                    {t("risksHeader")}
                  </h3>
                  <div className="space-y-2">
                    {(activeOpp.risks || []).length === 0 ? (
                      <p className="text-xs text-muted">{t("noRisks")}</p>
                    ) : (
                      activeOpp.risks!.map((r, i) => (
                        <div key={i} className="p-2 bg-paper/60 border border-line rounded flex items-center gap-2 text-xs">
                          <span className="text-amberbrand font-bold">!</span>
                          <span className="font-semibold text-ink">{r}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="p-3 bg-paper/40 border border-line rounded text-xs space-y-1">
                  <span className="font-bold text-ink block">{t("officialSourceTitle")}</span>
                  <p className="text-[11px] text-muted">{t("officialSourceDesc")}</p>
                  {activeOpp.url && (
                    <a href={activeOpp.url} target="_blank" rel="noreferrer"
                       className="text-greenbrand font-bold text-xs inline-flex items-center gap-1 hover:underline mt-1">
                      {t("openSourceBtn")} ↗
                    </a>
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-line mt-6 flex items-center justify-between gap-2">
                <button
                  onClick={() => toggleSave(activeOpp)}
                  className={`flex-1 py-2 rounded text-xs font-bold transition-all border ${activeOpp.saved
                    ? "bg-greenbg text-greenbrand border-greenbrand/30"
                    : "bg-paper hover:bg-line border-line text-ink"}`}
                >
                  ★ {activeOpp.saved ? (lang === "fr" ? "Dossier Enregistré" : "تم حفظ الملف")
                               : (lang === "fr" ? "Enregistrer dans Mes Dossiers" : "حفظ في ملفاتي")}
                </button>
                <button onClick={() => setActiveId(null)}
                        className="flex-1 bg-greenbrand hover:bg-[#18553f] text-white py-2 rounded text-xs font-bold transition-all">
                  {t("closeBtn")}
                </button>
              </div>
            </div>
          );
        })()}
      </aside>
    </div>
  );

  // ------------------------------------------------ page
  if (!loaded) {
    return <BrandLoader label={t("loading")} />;
  }

  return (
    <>
      {headerEl}
      {tabsEl}
      <main className="max-w-[1400px] w-full mx-auto p-4 lg:p-8 space-y-6 flex-1">
        {err && <div className="message message-err">{err}</div>}
        {profile?.plan === "trial" && profile.trial_started_at && profile.trial_ends_at && (() => {
          const start = new Date(profile.trial_started_at).getTime();
          const end = new Date(profile.trial_ends_at).getTime();
          const now = Date.now();
          if (now > end) return null;
          const day = Math.max(1, Math.floor((now - start) / 86400000) + 1);
          const total = Math.max(1, Math.ceil((end - start) / 86400000));
          return (
            <div className="bg-greenbg border border-greenbrand/25 rounded-lg px-4 py-3 flex items-center justify-between gap-3">
              <span className="text-xs font-bold text-greenbrand">
                🎁 {lang === "fr" ? `Essai gratuit : jour ${day} sur ${total}` : `التجربة المجانية: اليوم ${day} من ${total}`}
              </span>
              <span className="text-[11px] text-muted">
                {new Date(profile.trial_ends_at!).toLocaleDateString(lang === "fr" ? "fr-FR" : "ar-MA")}
              </span>
            </div>
          );
        })()}
        {kpisEl}
        {tab === "feed" && feedEl}
        {tab === "dossiers" && dossiersEl}
        {tab === "profile" && profileEl}
        {tab === "alerts" && alertsEl}
      </main>
      {drawerEl}
      {toast && (
        <div className="fixed bottom-5 right-5 rtl:right-auto rtl:left-5 z-[60] bg-ink text-white text-xs px-4 py-3 rounded-lg shadow-2xl max-w-xs">
          {toast}
        </div>
      )}
      <footer className="footer">{t("footer")}</footer>
    </>
  );
}
