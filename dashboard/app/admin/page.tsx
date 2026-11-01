"use client";

// Console d'administration — port du mockup admin (Finances & Abonnés,
// Observabilité Agents & IA, Requêtes & Erreurs Pipeline) sur l'API réelle.
// Bilingue FR/AR avec bascule RTL.

import { FormEvent, useEffect, useState } from "react";
import { api, clearAuth, getAuth } from "../lib";
import BrandLoader from "../brand-loader";

type Company = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  sectors: string[];
  keywords: string[];
  regions: string[];
  size: string;
  plan: string;   // decouverte | pro | business
  status: string; // active | suspended
  channel_whatsapp: boolean;
  channel_email: boolean;
  created_at: string;
};

type AgentStat = {
  agent: string;
  calls: number;
  avg_s: number | null;
  p95_s: number | null;
  max_s: number | null;
  errors: number;
};

type Summary = {
  window_hours: number;
  requests: {
    total: number; ok: number; errors: number; pipeline_runs: number;
    avg_latency_ms: number | null; p95_latency_ms: number | null;
    tokens_in: number | string; tokens_out: number | string; llm_cost_usd: number | string;
  };
  agents: AgentStat[];
  last_pipeline_run: {
    started_at: string; finished_at: string | null; source_mode: string | null;
    ingested: number; matched: number; verdicted: number; digests: number;
    status: string; error: string | null;
  } | null;
  counts: {
    companies: number; companies_active: number; companies_paying: number;
    opportunities: number; matches: number; digests: number; waitlist: number;
  };
};

type RequestRow = {
  id: string;
  message_id: string | null;
  sender_phone: string | null;
  route: string;
  outcome: string;
  error: string | null;
  started_at: string;
  latency_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  llm_cost_usd: number | string | null;
};

type Trace = {
  request: RequestRow;
  steps: Array<{ agent: string; duration_s: number | null; detail: string | null; created_at: string }>;
};

type AdminConfig = {
  portal_enabled: boolean;
  llm_enabled: boolean;
  kill_switch: boolean;
  llm_key_present: boolean;
  email_ready: boolean;
  whatsapp_ready: boolean;
};

// Rapport de l'agent de monitoring (GET /monitoring/report, admin).
type MonitorCheck = { id: string; status: "ok" | "warn" | "crit"; value: unknown; detail: string };

type MonitorReport = {
  status: "ok" | "warn" | "crit";
  generated_at: string;
  window_hours: number;
  checks: MonitorCheck[];
  stats: Record<string, unknown> & { requests?: Record<string, unknown> };
  config: Record<string, boolean>;
  last_alert: { degraded: string[]; ts: number; status: string } | null;
};

const STATUS_BADGE: Record<string, string> = {
  ok: "bg-greenbg text-greenbrand",
  warn: "bg-amberbg text-amberbrand",
  crit: "bg-redbg text-redbrand",
};

const CHECK_LABELS: Record<string, { fr: string; ar: string }> = {
  error_rate: { fr: "Taux d'erreurs API", ar: "نسبة أخطاء الواجهة" },
  latency: { fr: "Latence p95 des agents", ar: "زمن استجابة الوكلاء" },
  llm_cost: { fr: "Coût LLM de la fenêtre", ar: "تكلفة النموذج" },
  llm_fallback: { fr: "Repli heuristique (LLM dégradé)", ar: "الرجوع عن النموذج" },
  portal_freshness: { fr: "Fraîcheur du portail", ar: "تحديث بوابة الصفقات" },
  pipeline_freshness: { fr: "Fraîcheur du pipeline", ar: "تحديث المسار" },
  digest_whatsapp: { fr: "Livraison WhatsApp du digest", ar: "تسليم الملخص عبر واتساب" },
  db_connectivity: { fr: "Base de données joignable", ar: "الاتصال بقاعدة البيانات" },
};

const PLAN_PRICE: Record<string, number> = { decouverte: 0, pro: 199, business: 499 };

const AGENT_LABELS: Record<string, { fr: string; ar: string }> = {
  sources: { fr: "ScraperAgent (Portail marchés publics)", ar: "وكيل الجمع (بوابة الصفقات)" },
  matching: { fr: "MatchingAgent (Score & Breakdown)", ar: "وكيل التوافق (النتيجة والتفصيل)" },
  verdict: { fr: "RiskAnalyzerAgent (Verdict & Risques)", ar: "وكيل المخاطر (التوصية والمخاطر)" },
  digest: { fr: "DigestAgent (Synthèse & Envois)", ar: "وكيل الملخص (الإرسال)" },
  intake: { fr: "IntakeAgent (Réception messages)", ar: "وكيل الاستقبال (الرسائل)" },
  faq: { fr: "FaqAgent (Questions standards — RAG)", ar: "وكيل الأسئلة الشائعة" },
  orchestrator: { fr: "Orchestrator (Routage)", ar: "المنسق (التوجيه)" },
  response: { fr: "ResponseAgent (Réponses)", ar: "وكيل الردود" },
};

const T: Record<"fr" | "ar", Record<string, string>> = {
  fr: {
    subtitle: "Supervision financière, abonnés et télémétrie des agents IA",
    tabFinances: "Finances & Abonnés",
    tabAgents: "Observabilité Agents & IA",
    tabLogs: "Requêtes & Erreurs Pipeline",
    tabMonitor: "Monitoring Plateforme",
    tabSources: "Sources de données",
    sourcesSub: "Registre des portails surveillés — activer, ajouter, tester sans redéploiement.",
    thSource: "Source", thKind: "Type", thAdapter: "Adaptateur", thCadence: "Cadence",
    thLastRun: "Dernier run", thEnabled: "Active",
    addSourceBtn: "+ Ajouter une source", testBtn: "Tester", delBtn: "Supprimer",
    srcName: "Nom", srcUrl: "URL de base", srcKind: "Type (portal_html / rss)",
    srcAdapter: "Adaptateur (marchespublics / generic_rss)", srcCadence: "Cadence (h)",
    saveSrcBtn: "Enregistrer", cancelBtn: "Annuler", noSources: "Aucune source configurée.",
    srcAdded: "Source ajoutée ✓", srcUpdated: "Source mise à jour ✓",
    srcDeleted: "Source supprimée ✓", testOk: "Harvest OK :", testKo: "Harvest en échec :",
    monStatus: "Statut global",
    monWindow: "Fenêtre analysée",
    monChecks: "Vérifications",
    monCheckId: "Vérification",
    monValue: "Valeur",
    monDetail: "Détail",
    monRefresh: "Rafraîchir le rapport",
    monLastAlert: "Dernière alerte envoyée",
    monNever: "aucune (plateforme saine) ",
    monStats: "Activité sur la fenêtre",
    monCompanies: "Entreprises actives",
    monOpportunities: "Opportunités (total)",
    monMatches: "Nouveaux matchs",
    monDigests: "Synthèses livrées",
    monSnapshot: "État des composants",
    monNoReport: "Rapport indisponible.",
    monGenerated: "Rapport généré",
    kpiMrr: "Revenu Mensuel (MRR)",
    kpiMrrSub: "Pro 199 DH · Business 499 DH",
    kpiSubs: "Abonnés Payants Actifs",
    kpiCompanies: "Entreprises Inscrites",
    kpiCompaniesSub: "actives sur le total",
    kpiConv: "Taux de Conversion",
    kpiConvSub: "Essai gratuit → Payant",
    subHeader: "Dernières Souscriptions & Comptes",
    liveUpdate: "Mise à jour en direct",
    thDate: "Date",
    thCompany: "Entreprise",
    thPlan: "Plan",
    thAmount: "MRR",
    thStatus: "Statut",
    thActions: "Actions",
    manage: "Gérer",
    suspend: "Suspendre",
    reactivate: "Réactiver",
    newCompany: "+ Nouvelle entreprise",
    createTitle: "Créer une entreprise",
    fName: "Nom", fEmail: "Email", fPhone: "Téléphone WhatsApp",
    fPassword: "Mot de passe initial", fSectors: "Secteurs (virgules)",
    fPlan: "Plan", create: "Créer l'entreprise",
    active: "Active", suspended: "Suspendu",
    runPipeline: "Lancer le pipeline",
    running: "Exécution…",
    agentKpiCalls: "Appels Agents (24h)",
    agentKpiLatency: "Latence Moyenne Pipeline",
    agentKpiCost: "Coût LLM Estimé (24h)",
    agentKpiBreakers: "Circuit Breakers",
    allActive: "Tous Actifs",
    someOff: "coupé(s)",
    latencyHeader: "Performance Latence par Agent IA",
    latencySub: "La barre représente la moyenne, le trait violet indique le P95.",
    noAgentData: "Aucun appel d'agent sur la période. Lancez le pipeline pour générer de la télémétrie.",
    breakerHeader: "Commandes & Interrupteurs (Circuit Breakers)",
    breakerSub: "Désactivez temporairement un canal ou une source en cas d'incident. Non persisté (reset au redémarrage).",
    thAgent: "Agent ID",
    thSourceStatus: "État Source",
    thSwitch: "Interrupteur",
    breakerPortal: "ScraperAgent (Portail)",
    breakerPortalOn: "Collecte portail active",
    breakerPortalOff: "Repli sur les seeds",
    breakerLlm: "LLM (Mistral)",
    breakerLlmOn: "Scoring IA actif",
    breakerLlmOff: "Mode heuristique",
    breakerKill: "Kill Switch Envois",
    breakerKillOn: "Envois bloqués (sauf test)",
    breakerKillOff: "Envois réels autorisés",
    channelsReady: "Canaux",
    emailOk: "Email prêt", emailKo: "Email non configuré",
    waOk: "WhatsApp prêt", waKo: "Token WhatsApp manquant",
    logsHeader: "Journal des Requêtes & Incidents Bloquants",
    logsSub: "Inspection détaillée des corrélations d'exécution et diagnostics d'erreurs en temps réel.",
    refreshLogsBtn: "Actualiser les traces",
    thTime: "Heure",
    thCorrId: "Correlation ID",
    thAction: "Action / Tâche Pipeline",
    thDuration: "Durée",
    thTokens: "Tokens (in/out)",
    thCost: "Coût",
    thDiag: "Diagnostic",
    inspectBtn: "Inspecter ↗",
    noRequests: "Aucune requête sur la fenêtre.",
    drawerTelemetry: "Télémétrie & Logs Agent",
    executionSteps: "Exécution étape par étape",
    noSteps: "Aucune étape enregistrée pour cette requête.",
    closeBtn: "Fermer le diagnostic",
    lastRun: "Dernier run pipeline",
    logout: "Déconnexion",
    loading: "Initialisation de la console d'administration…",
    footer: "© 2026 Soukna — Console d'administration · Intelligence des marchés publics",
  },
  ar: {
    subtitle: "الإشراف المالي والمشتركون وقياس وكلاء الذكاء الاصطناعي",
    tabFinances: "المالية والمشتركون",
    tabAgents: "مرقبة الوكلاء والذكاء الاصطناعي",
    tabLogs: "الطلبات وأخطاء المسار",
    tabMonitor: "مراقبة المنصة",
    tabSources: "مصادر البيانات",
    sourcesSub: "سجل البوابات المراقَبة — تفعيل وإضافة واختبار دون إعادة نشر.",
    thSource: "المصدر", thKind: "النوع", thAdapter: "المحوّل", thCadence: "الوتيرة",
    thLastRun: "آخر تشغيل", thEnabled: "مفعّلة",
    addSourceBtn: "+ إضافة مصدر", testBtn: "اختبار", delBtn: "حذف",
    srcName: "الاسم", srcUrl: "الرابط الأساسي", srcKind: "النوع (portal_html / rss)",
    srcAdapter: "المحوّل (marchespublics / generic_rss)", srcCadence: "الوتيرة (ساعة)",
    saveSrcBtn: "حفظ", cancelBtn: "إلغاء", noSources: "لا توجد مصادر مُعدّة.",
    srcAdded: "أُضيف المصدر ✓", srcUpdated: "حُدّث المصدر ✓",
    srcDeleted: "حُذف المصدر ✓", testOk: "الجلب نجح :", testKo: "فشل الجلب :",
    monStatus: "الحالة العامة",
    monWindow: "نطاق التحليل",
    monChecks: "الفحوصات",
    monCheckId: "الفحص",
    monValue: "القيمة",
    monDetail: "التفاصيل",
    monRefresh: "تحديث التقرير",
    monLastAlert: "آخر تنبيه مُرسل",
    monNever: "لا شيء (المنصة سليمة)",
    monStats: "النشاط في النطاق",
    monCompanies: "الشركات النشطة",
    monOpportunities: "الفرص (المجموع)",
    monMatches: "توافقات جديدة",
    monDigests: "ملخصات مُسلَّمة",
    monSnapshot: "حالة المكونات",
    monNoReport: "التقرير غير متوفر.",
    monGenerated: "توليد التقرير",
    kpiMrr: "الإيراد الشهري المتكرر",
    kpiMrrSub: "Pro 199 درهم · Business 499 درهم",
    kpiSubs: "المشتركون النشطون",
    kpiCompanies: "الشركات المسجلة",
    kpiCompaniesSub: "نشطة من الإجمالي",
    kpiConv: "معدل التحويل",
    kpiConvSub: "تجربة مجانية ← مدفوعة",
    subHeader: "آخر الاشتراكات والحسابات",
    liveUpdate: "تحديث مباشر",
    thDate: "التاريخ",
    thCompany: "الشركة",
    thPlan: "الباقة",
    thAmount: "الإيراد",
    thStatus: "الحالة",
    thActions: "إجراءات",
    manage: "إدارة",
    suspend: "تعليق",
    reactivate: "إعادة تفعيل",
    newCompany: "+ شركة جديدة",
    createTitle: "إنشاء شركة",
    fName: "الاسم", fEmail: "البريد", fPhone: "هاتف واتساب",
    fPassword: "كلمة المرور الأولية", fSectors: "القطاعات (فواصل)",
    fPlan: "الباقة", create: "إنشاء الشركة",
    active: "نشطة", suspended: "معلقة",
    runPipeline: "تشغيل المسار",
    running: "جارٍ التنفيذ…",
    agentKpiCalls: "اتصالات الوكلاء (24 ساعة)",
    agentKpiLatency: "متوسط تأخير المسار",
    agentKpiCost: "تكلفة نموذج اللغة (24 ساعة)",
    agentKpiBreakers: "قواطع الدائرة",
    allActive: "جميعها نشطة",
    someOff: "مقطوع",
    latencyHeader: "أداء التأخير لكل وكيل ذكاء اصطناعي",
    latencySub: "يمثل الشريط المتوسط، ويشير الخط البنفسجي إلى النسبة المئوية 95.",
    noAgentData: "لا توجد اتصالات وكلاء في هذه الفترة. شغّل المسار لتوليد القياسات.",
    breakerHeader: "الأوامر وقواطع الدائرة",
    breakerSub: "عطّل قناة أو مصدراً مؤقتاً عند حدوث خلل. غير محفوظ (يُعاد ضبطه عند إعادة التشغيل).",
    thAgent: "معرف الوكيل",
    thSourceStatus: "حالة المصدر",
    thSwitch: "المفتاح",
    breakerPortal: "وكيل الجمع (البوابة)",
    breakerPortalOn: "جمع البوابة نشط",
    breakerPortalOff: "الرجوع للبيانات التجريبية",
    breakerLlm: "نموذج اللغة (Mistral)",
    breakerLlmOn: "التقييم الذكي نشط",
    breakerLlmOff: "الوضع الاستدلالي",
    breakerKill: "مفتاح إيقاف الإرسال",
    breakerKillOn: "الإرسال محجوب (عدا الاختبار)",
    breakerKillOff: "الإرسال الحقيقي مسموح",
    channelsReady: "القنوات",
    emailOk: "البريد جاهز", emailKo: "البريد غير مهيأ",
    waOk: "واتساب جاهز", waKo: "رمز واتساب مفقود",
    logsHeader: "سجل الطلبات والحوادث المعرقلة",
    logsSub: "فحص تفصيلي لارتباطات التنفيذ وتشخيص الأخطاء في الوقت الفعلي.",
    refreshLogsBtn: "تحديث السجلات",
    thTime: "الوقت",
    thCorrId: "معرف الارتباط",
    thAction: "مهمة المسار",
    thDuration: "المدة",
    thTokens: "الرموز (داخل/خارج)",
    thCost: "التكلفة",
    thDiag: "التشخيص",
    inspectBtn: "فحص ↗",
    noRequests: "لا توجد طلبات في هذه الفترة.",
    drawerTelemetry: "القياس عن بعد وسجلات الوكيل",
    executionSteps: "التنفيذ خطوة بخطوة",
    noSteps: "لا توجد خطوات مسجلة لهذا الطلب.",
    closeBtn: "إغلاق التشخيص",
    lastRun: "آخر تشغيل للمسار",
    logout: "تسجيل الخروج",
    loading: "جارٍ تهيئة لوحة الإدارة…",
    footer: "© 2026 Soukna — لوحة الإدارة · ذكاء طلبات العروض العمومية",
  },
};

function fmtMs(ms: number | string | null | undefined): string {
  const n = Number(ms);
  if (ms == null || isNaN(n)) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n)} ms`;
}

function fmtS(s: number | string | null | undefined): string {
  const n = Number(s);
  if (s == null || isNaN(n)) return "—";
  return n >= 1 ? `${n.toFixed(1)} s` : `${Math.round(n * 1000)} ms`;
}

export default function AdminPage() {
  const [lang, setLang] = useState<"fr" | "ar">("fr");
  const [tab, setTab] = useState<"finances" | "agents" | "logs" | "monitor" | "sources">("finances");
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  type SourceRow = {
    id: string; name: string; base_url: string; kind: string; adapter: string;
    cadence_hours: number; enabled: boolean; last_run_at: string | null; last_status: string | null;
  };

  const [summary, setSummary] = useState<Summary | null>(null);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [showSrcForm, setShowSrcForm] = useState(false);
  const [srcEditId, setSrcEditId] = useState<string | null>(null);
  const [sName, setSName] = useState("");
  const [sUrl, setSUrl] = useState("");
  const [sKind, setSKind] = useState("rss");
  const [sAdapter, setSAdapter] = useState("generic_rss");
  const [sCadence, setSCadence] = useState(24);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [requests, setRequests] = useState<RequestRow[]>([]);
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [monitor, setMonitor] = useState<MonitorReport | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const [cName, setCName] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [cPassword, setCPassword] = useState("");
  const [cSectors, setCSectors] = useState("");
  const [cPlan, setCPlan] = useState("decouverte");

  const t = (k: string) => T[lang][k] ?? k;

  useEffect(() => {
    const auth = getAuth();
    if (!auth) { window.location.href = "/login"; return; }
    if (auth.role !== "admin") { window.location.href = "/dashboard"; return; }
    (async () => {
      try { await loadAll(); }
      catch (exc) { setErr((exc as Error).message); }
      finally { setLoaded(true); }
    })();
  }, []);

  async function loadAll() {
    const [s, c, o, cfg, mon, srcs] = await Promise.all([
      api<Summary>("/observability/summary?hours=24"),
      api<Company[]>("/companies"),
      api<{ requests: RequestRow[] }>("/observability?hours=24"),
      api<AdminConfig>("/admin/config"),
      api<MonitorReport>("/monitoring/report"),
      api<SourceRow[]>("/admin/sources"),
    ]);
    setSummary(s);
    setSources(srcs || []);
    setCompanies(c || []);
    setRequests((o && o.requests) || []);
    setConfig(cfg);
    setMonitor(mon);
  }

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }

  function resetSrcForm() {
    setSrcEditId(null); setSName(""); setSUrl("");
    setSKind("rss"); setSAdapter("generic_rss"); setSCadence(24);
    setShowSrcForm(false);
  }

  async function saveSource() {
    setErr(""); setMsg(""); setBusy(true);
    try {
      const payload = { name: sName, base_url: sUrl, kind: sKind,
                        adapter: sAdapter, cadence_hours: sCadence };
      if (srcEditId) {
        await api(`/admin/sources/${srcEditId}`, { method: "PATCH", body: JSON.stringify(payload) });
        showToast(t("srcUpdated"));
      } else {
        await api("/admin/sources", { method: "POST", body: JSON.stringify(payload) });
        showToast(t("srcAdded"));
      }
      resetSrcForm();
      setSources(await api<SourceRow[]>("/admin/sources"));
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  async function toggleSource(row: SourceRow) {
    setBusy(true);
    try {
      await api(`/admin/sources/${row.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !row.enabled }) });
      setSources(await api<SourceRow[]>("/admin/sources"));
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  async function testSource(row: SourceRow) {
    setBusy(true); setMsg(""); setErr("");
    try {
      const r = await api<{ ok: boolean; items: number }>(`/admin/sources/${row.id}/test`, { method: "POST" });
      showToast(`${t("testOk")} ${r.items}`);
      setSources(await api<SourceRow[]>("/admin/sources"));
    } catch (exc) { showToast(`${t("testKo")} ${(exc as Error).message.slice(0, 90)}`); }
    finally { setBusy(false); }
  }

  async function deleteSource(row: SourceRow) {
    setBusy(true);
    try {
      await api(`/admin/sources/${row.id}`, { method: "DELETE" });
      showToast(t("srcDeleted"));
      setSources(await api<SourceRow[]>("/admin/sources"));
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  function toggleLang() {
    const next = lang === "fr" ? "ar" : "fr";
    setLang(next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
  }

  async function runPipeline() {
    setMsg(""); setErr(""); setBusy(true);
    try {
      const r = await api<{ status: string; ingested: number; matches: number; digests: number }>(
        "/run", { method: "POST", body: JSON.stringify({}) },
      );
      setMsg(`Pipeline ${r.status} : ${r.ingested} opportunités, ${r.matches} matchs, ${r.digests} synthèses.`);
      await loadAll();
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  async function patchCompany(c: Company, patch: { plan?: string; status?: string }) {
    setErr(""); setBusy(true);
    try {
      const updated = await api<Company>(`/companies/${c.id}`, {
        method: "PATCH", body: JSON.stringify(patch),
      });
      setCompanies((prev) => prev.map((x) => (x.id === c.id ? { ...x, ...updated } : x)));
      showToast(patch.status ? (patch.status === "active" ? "Compte réactivé" : "Compte suspendu")
                             : `Plan mis à jour : ${patch.plan}`);
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  async function createCompany(e: FormEvent) {
    e.preventDefault();
    setMsg(""); setErr(""); setBusy(true);
    try {
      await api<Company>("/companies", {
        method: "POST",
        body: JSON.stringify({
          name: cName, email: cEmail, phone: cPhone || null, password: cPassword,
          sectors: cSectors.split(",").map((x) => x.trim()).filter(Boolean), plan: cPlan,
        }),
      });
      setMsg(`Entreprise « ${cName} » créée ✅`);
      setCName(""); setCEmail(""); setCPhone(""); setCPassword(""); setCSectors(""); setCPlan("decouverte");
      setShowCreate(false);
      await loadAll();
    } catch (exc) { setErr((exc as Error).message); }
    finally { setBusy(false); }
  }

  async function patchConfig(patch: Partial<AdminConfig>) {
    setErr("");
    try {
      const updated = await api<AdminConfig>("/admin/config", {
        method: "PATCH", body: JSON.stringify(patch),
      });
      setConfig(updated);
      showToast("Circuit Breaker mis à jour");
    } catch (exc) { setErr((exc as Error).message); }
  }

  async function openTrace(id: string) {
    setErr("");
    try { setTrace(await api<Trace>(`/observability/requests/${id}/logs`)); }
    catch (exc) { setErr((exc as Error).message); }
  }

  // KPIs finances (calculés sur les vraies entreprises)
  const mrr = companies.reduce((acc, c) => acc + (PLAN_PRICE[c.plan] || 0), 0);
  const paying = companies.filter((c) => c.plan !== "decouverte").length;
  const active = companies.filter((c) => c.status === "active").length;
  const conversion = companies.length ? Math.round((paying / companies.length) * 1000) / 10 : 0;

  const agentCalls = (summary?.agents || []).reduce((a, x) => a + x.calls, 0);
  const agentErrors = (summary?.agents || []).reduce((a, x) => a + x.errors, 0);
  const maxAvg = Math.max(0.001, ...(summary?.agents || []).map((a) => Number(a.avg_s) || 0));

  const headerEl = (
    <header className="sticky top-0 z-40 bg-[#f5f0e6ed] backdrop-blur-md border-b border-[#dcd6cb] px-4 lg:px-8 py-3">
      <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-ink text-white flex items-center justify-center font-bold font-display text-lg">SK</div>
          <div>
            <h1 className="font-display font-bold text-base text-ink leading-none">Soukna Administration &amp; Observabilité</h1>
            <div className="text-[11px] text-muted mt-0.5">{t("subtitle")}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a href="/admin/attente"
             className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink transition-all flex items-center gap-1.5">
            📋 Liste d&apos;attente
          </a>
          <button onClick={runPipeline} disabled={busy}
                  className="bg-greenbrand hover:bg-[#18553f] text-white px-3 py-1.5 rounded-md text-xs font-bold transition-all disabled:opacity-60">
            {busy ? t("running") : t("runPipeline")}
          </button>
          <button onClick={toggleLang} type="button"
                  className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink transition-all">
            🌐 <span>{lang === "fr" ? "العربية" : "Français"}</span>
          </button>
          <div className="flex items-center gap-2 pl-3 border-l border-line">
            <div className="w-7 h-7 rounded-full bg-terra text-white flex items-center justify-center font-bold text-xs">AD</div>
            <button onClick={() => { clearAuth(); window.location.href = "/login"; }}
                    className="text-[11px] font-semibold text-muted hover:text-redbrand">
              {t("logout")}
            </button>
          </div>
        </div>
      </div>
    </header>
  );

  const tabsEl = (
    <nav className="bg-white border-b border-line px-4 lg:px-8">
      <div className="max-w-[1400px] mx-auto flex items-center gap-2 sm:gap-6 overflow-x-auto no-scrollbar py-1">
        {([
          ["finances", "📊", t("tabFinances")],
          ["agents", "🤖", t("tabAgents")],
          ["logs", "🔍", t("tabLogs")],
          ["monitor", "🩺", t("tabMonitor")],
          ["sources", "📡", t("tabSources")],
        ] as const).map(([id, icon, label]) => (
          <button key={id} onClick={() => setTab(id)}
                  className={`tab-btn px-4 py-3 text-xs sm:text-sm font-medium text-muted hover:text-ink transition-all flex items-center gap-2 whitespace-nowrap ${tab === id ? "active" : ""}`}>
            <span>{icon}</span> {label}
          </button>
        ))}
      </div>
    </nav>
  );

  function kpi(title: string, value: string, sub: string, valueCls = "text-ink") {
    return (
      <div className="bg-white border border-line rounded-lg p-4 shadow-sm">
        <div className="text-[11px] font-bold text-muted uppercase tracking-wider mb-1">{title}</div>
        <div className={`text-2xl font-bold font-display ${valueCls}`}>{value}</div>
        <div className="text-[11px] text-muted mt-1">{sub}</div>
      </div>
    );
  }

  const financesEl = (
    <section className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpi(t("kpiMrr"), `${mrr.toLocaleString("fr-MA")} MAD`, t("kpiMrrSub"), "text-greenbrand")}
        {kpi(t("kpiSubs"), String(paying), `${companies.length - paying} ${lang === "fr" ? "en Découverte (0 DH)" : "في باقة الاكتشاف (0 درهم)"}`)}
        {kpi(t("kpiCompanies"), String(companies.length), `${active}/${companies.length} ${t("kpiCompaniesSub")}`)}
        {kpi(t("kpiConv"), `${conversion} %`, t("kpiConvSub"), "text-terra")}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-line rounded-lg p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-base text-ink">{t("subHeader")}</h3>
            <span className="text-xs text-muted">{t("liveUpdate")}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left rtl:text-right">
              <thead>
                <tr className="border-b border-line text-muted uppercase text-[10px]">
                  <th className="py-2.5 px-3">{t("thDate")}</th>
                  <th className="py-2.5 px-3">{t("thCompany")}</th>
                  <th className="py-2.5 px-3">{t("thPlan")}</th>
                  <th className="py-2.5 px-3">{t("thAmount")}</th>
                  <th className="py-2.5 px-3">{t("thStatus")}</th>
                  <th className="py-2.5 px-3">{t("thActions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/40">
                {companies.length === 0 && (
                  <tr><td colSpan={8} className="py-4 px-3 text-muted text-center">{t("noRequests")}</td></tr>
                )}
                {[...companies].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).map((c) => (
                  <tr key={c.id}>
                    <td className="py-3 px-3 text-muted">{new Date(c.created_at).toLocaleDateString(lang === "fr" ? "fr-FR" : "ar-MA")}</td>
                    <td className="py-3 px-3 font-bold text-ink">{c.name}<div className="text-[10px] text-muted font-normal">{c.email}</div></td>
                    <td className="py-3 px-3">
                      <select value={c.plan} onChange={(e) => patchCompany(c, { plan: e.target.value })} disabled={busy}
                              className="bg-paper border border-line rounded px-1.5 py-0.5 text-[10px] font-bold text-ink">
                        <option value="decouverte">DÉCOUVERTE</option>
                        <option value="pro">PRO</option>
                        <option value="business">BUSINESS</option>
                      </select>
                    </td>
                    <td className="py-3 px-3 font-semibold">{PLAN_PRICE[c.plan] || 0} MAD</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${c.status === "active" ? "bg-greenbg text-greenbrand" : "bg-redbg text-redbrand"}`}>
                        {c.status === "active" ? t("active") : t("suspended")}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <button onClick={() => patchCompany(c, { status: c.status === "active" ? "suspended" : "active" })}
                              disabled={busy}
                              className={`font-bold hover:underline ${c.status === "active" ? "text-redbrand" : "text-terra"}`}>
                        {c.status === "active" ? t("suspend") : t("reactivate")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white border border-line rounded-lg p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-base text-ink">{t("createTitle")}</h3>
            <button onClick={() => setShowCreate((v) => !v)} className="text-greenbrand font-bold text-xs hover:underline">
              {t("newCompany")}
            </button>
          </div>
          {showCreate && (
            <form onSubmit={createCompany} className="space-y-2 text-xs">
              <input value={cName} onChange={(e) => setCName(e.target.value)} required placeholder={t("fName")}
                     className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink" />
              <input type="email" value={cEmail} onChange={(e) => setCEmail(e.target.value)} required placeholder={t("fEmail")}
                     className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink" />
              <input value={cPhone} onChange={(e) => setCPhone(e.target.value)} placeholder={`${t("fPhone")} +2126…`}
                     className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink" />
              <input type="password" value={cPassword} onChange={(e) => setCPassword(e.target.value)} required minLength={6} placeholder={t("fPassword")}
                     className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink" />
              <input value={cSectors} onChange={(e) => setCSectors(e.target.value)} placeholder={t("fSectors")}
                     className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink" />
              <select value={cPlan} onChange={(e) => setCPlan(e.target.value)}
                      className="w-full bg-paper/50 border border-line rounded px-2.5 py-2 text-ink">
                <option value="decouverte">DÉCOUVERTE</option>
                <option value="pro">PRO</option>
                <option value="business">BUSINESS</option>
              </select>
              <button type="submit" disabled={busy}
                      className="w-full bg-greenbrand hover:bg-[#18553f] text-white px-4 py-2 rounded text-xs font-bold transition-all disabled:opacity-60">
                {t("create")}
              </button>
            </form>
          )}
          {config && (
            <div className="pt-3 border-t border-line space-y-2 text-xs">
              <div className="font-bold text-ink">{t("channelsReady")}</div>
              <div className="flex items-center justify-between">
                <span className="text-muted">{t("emailOk")}</span>
                <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${config.email_ready ? "bg-greenbg text-greenbrand" : "bg-redbg text-redbrand"}`}>
                  {config.email_ready ? "✓" : "×"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">{config.whatsapp_ready ? t("waOk") : t("waKo")}</span>
                <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${config.whatsapp_ready ? "bg-greenbg text-greenbrand" : "bg-amberbg text-amberbrand"}`}>
                  {config.whatsapp_ready ? "✓" : "!"}
                </span>
              </div>
              {summary?.last_pipeline_run && (
                <div className="pt-2 border-t border-line text-[11px] text-muted">
                  <span className="font-bold text-ink">{t("lastRun")} :</span>{" "}
                  {summary.last_pipeline_run.status === "ok"
                    ? `${summary.last_pipeline_run.ingested} opportunisés · ${summary.last_pipeline_run.matched} matchs`
                    : `erreur — ${summary.last_pipeline_run.error || "?"}`}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );

  const agentsEl = (
    <section className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpi(t("agentKpiCalls"), agentCalls.toLocaleString("fr-FR"),
             `${agentCalls ? Math.round((1 - agentErrors / agentCalls) * 1000) / 10 : 100} % ${lang === "fr" ? "de réussite" : "نسبة النجاح"}`)}
        {kpi(t("agentKpiLatency"), fmtMs(summary?.requests.avg_latency_ms),
             `P95 ${fmtMs(summary?.requests.p95_latency_ms)}`)}
        {kpi(t("agentKpiCost"),
             `$ ${Number(summary?.requests.llm_cost_usd || 0).toFixed(4)}`,
             `≈ ${Number(summary?.requests.tokens_in || 0).toLocaleString("fr-FR")} in · ${Number(summary?.requests.tokens_out || 0).toLocaleString("fr-FR")} out tokens`)}
        {kpi(t("agentKpiBreakers"),
             config && !config.portal_enabled ? "1 " + t("someOff") : t("allActive"),
             config?.llm_key_present ? (lang === "fr" ? "LLM Mistral disponible" : "نموذج Mistral متاح") : (lang === "fr" ? "Mode heuristique" : "الوضع الاستدلالي"),
             config && !config.portal_enabled ? "text-amberbrand" : "text-greenbrand")}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-line rounded-lg p-5 shadow-sm space-y-4">
          <h3 className="font-display font-bold text-base text-ink">{t("latencyHeader")}</h3>
          <p className="text-xs text-muted">{t("latencySub")}</p>
          <div className="space-y-4 text-xs pt-2">
            {(summary?.agents || []).length === 0 && (
              <p className="text-muted py-4">{t("noAgentData")}</p>
            )}
            {(summary?.agents || []).map((a) => {
              const label = AGENT_LABELS[a.agent]?.[lang] || a.agent;
              const w = Math.min(100, ((Number(a.avg_s) || 0) / maxAvg) * 100);
              const p95 = Math.min(100, ((Number(a.p95_s) || 0) / maxAvg) * 100);
              return (
                <div key={a.agent}>
                  <div className="flex justify-between font-semibold text-ink mb-1">
                    <span><strong>{a.agent}</strong> — {label.split(" (")[1]?.replace(")", "") || ""}</span>
                    <span>{fmtS(a.avg_s)} moy · p95 {fmtS(a.p95_s)}</span>
                  </div>
                  <div className="h-2 w-full bg-paper rounded-full overflow-hidden border border-line relative">
                    <div className="h-full bg-greenbrand" style={{ width: `${w}%` }} />
                    <div className="absolute top-0 bottom-0 w-0.5 bg-purple-600" style={{ left: `${p95}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white border border-line rounded-lg p-5 shadow-sm space-y-4">
          <h3 className="font-display font-bold text-base text-ink">{t("breakerHeader")}</h3>
          <p className="text-xs text-muted">{t("breakerSub")}</p>
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-xs text-left rtl:text-right">
              <thead>
                <tr className="border-b border-line text-muted uppercase text-[10px]">
                  <th className="py-2 px-2">{t("thAgent")}</th>
                  <th className="py-2 px-2">{t("thSourceStatus")}</th>
                  <th className="py-2 px-2 text-center">{t("thSwitch")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/40">
                {config && [
                  {
                    key: "portal", label: t("breakerPortal"), on: config.portal_enabled,
                    onLabel: t("breakerPortalOn"), offLabel: t("breakerPortalOff"),
                    set: (v: boolean) => patchConfig({ portal_enabled: v }),
                  },
                  {
                    key: "llm", label: t("breakerLlm"), on: config.llm_enabled,
                    onLabel: config.llm_key_present ? t("breakerLlmOn") : t("breakerLlmOff"),
                    offLabel: t("breakerLlmOff"),
                    set: (v: boolean) => patchConfig({ llm_enabled: v }),
                  },
                  {
                    key: "kill", label: t("breakerKill"), on: !config.kill_switch,
                    onLabel: t("breakerKillOff"), offLabel: t("breakerKillOn"),
                    set: (v: boolean) => patchConfig({ kill_switch: !v }),
                  },
                ].map((row) => (
                  <tr key={row.key}>
                    <td className="py-3 px-2 font-bold text-ink">{row.label}</td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${row.on ? "bg-greenbg text-greenbrand" : "bg-amberbg text-amberbrand"}`}>
                        {row.on ? row.onLabel : row.offLabel}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-center">
                      <label className="toggle-sw">
                        <input type="checkbox" checked={row.on} onChange={(e) => row.set(e.target.checked)} />
                        <span className="slider" />
                      </label>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );

  const logsEl = (
    <section className="space-y-6">
      <div className="bg-white border border-line rounded-lg p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-display font-bold text-base text-ink">{t("logsHeader")}</h3>
            <p className="text-xs text-muted mt-0.5">{t("logsSub")}</p>
          </div>
          <button onClick={loadAll}
                  className="bg-paper hover:bg-line border border-line text-ink text-xs font-bold px-3 py-1.5 rounded transition-all">
            {t("refreshLogsBtn")}
          </button>
        </div>
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-xs text-left rtl:text-right">
            <thead>
              <tr className="border-b border-line text-muted uppercase text-[10px]">
                <th className="py-3 px-3">{t("thTime")}</th>
                <th className="py-3 px-3">{t("thCorrId")}</th>
                <th className="py-3 px-3">{t("thAction")}</th>
                <th className="py-3 px-3">{t("thStatus")}</th>
                <th className="py-3 px-3">{t("thDuration")}</th>
                <th className="py-3 px-3">{t("thTokens")}</th>
                <th className="py-3 px-3">{t("thCost")}</th>
                <th className="py-3 px-3 text-center">{t("thDiag")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {requests.length === 0 && (
                <tr><td colSpan={8} className="py-4 px-3 text-muted text-center">{t("noRequests")}</td></tr>
              )}
              {requests.map((r) => (
                <tr key={r.id}>
                  <td className="py-3 px-3 text-muted">{new Date(r.started_at).toLocaleTimeString(lang === "fr" ? "fr-FR" : "ar-MA")}</td>
                  <td className="py-3 px-3 font-mono text-muted text-[11px]">{r.id.slice(0, 8)}</td>
                  <td className="py-3 px-3 font-semibold text-ink">
                    {r.route === "pipeline" ? (lang === "fr" ? "Pipeline complet (collecte → matchs → synthèses)" : "المسار الكامل (جمع ← توافق ← ملخصات)")
                      : `${r.route} · ${r.message_id || "—"}`}
                    {r.error && <div className="text-[10px] text-redbrand font-normal">{r.error.slice(0, 90)}</div>}
                  </td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${r.outcome === "ok" ? "bg-greenbg text-greenbrand" : "bg-redbg text-redbrand"}`}>
                      {r.outcome}
                    </span>
                  </td>
                  <td className="py-3 px-3">{fmtMs(r.latency_ms)}</td>
                  <td className="py-3 px-3 font-mono text-[11px] text-muted">
                    {(Number(r.tokens_in) || 0).toLocaleString("fr-FR")} / {(Number(r.tokens_out) || 0).toLocaleString("fr-FR")}
                  </td>
                  <td className="py-3 px-3 font-mono">${Number(r.llm_cost_usd || 0).toFixed(4)}</td>
                  <td className="py-3 px-3 text-center">
                    <button onClick={() => openTrace(r.id)}
                            className={`font-bold hover:underline ${r.outcome === "ok" ? "text-greenbrand" : "text-terra"}`}>
                      {t("inspectBtn")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );

  // Valeur d'un check : nombre, liste d'entreprises ou objet (agent le plus lent)
  function fmtCheckValue(v: unknown): string {
    if (v == null) return "—";
    if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
    if (typeof v === "object") return Object.entries(v as Record<string, unknown>)
      .map(([k, x]) => `${k}=${x}`).join(" · ");
    return String(v);
  }

  const monitoringEl = !monitor ? (
    <section className="bg-white border border-line rounded-lg p-5 shadow-sm">
      <h3 className="font-display font-bold text-base text-ink">{t("tabMonitor")}</h3>
      <p className="text-xs text-muted mt-1">{t("monNoReport")}</p>
    </section>
  ) : (
    <section className="space-y-6">
      {/* Statut global + fenêtre + rafraîchissement */}
      <div className="bg-white border border-line rounded-lg p-5 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-terra">{t("monStatus")}</span>
            <div className="flex items-center gap-3 mt-1">
              <span className={`px-3 py-1 rounded font-bold text-sm ${STATUS_BADGE[monitor.status] || ""}`}>
                {monitor.status.toUpperCase()}
              </span>
              <span className="text-xs text-muted">
                {t("monWindow")} : {monitor.window_hours}h · {t("monGenerated")} {new Date(monitor.generated_at).toLocaleString(lang === "fr" ? "fr-FR" : "ar-MA")}
              </span>
            </div>
            <p className="text-[11px] text-muted mt-2">
              {t("monLastAlert")} : {monitor.last_alert
                ? `${monitor.last_alert.degraded?.join(", ") || "—"} (${new Date(monitor.last_alert.ts * 1000).toLocaleString(lang === "fr" ? "fr-FR" : "ar-MA")})`
                : t("monNever")}
            </p>
          </div>
          <button onClick={loadAll}
                  className="bg-paper hover:bg-line border border-line text-ink text-xs font-bold px-3 py-1.5 rounded transition-all">
            {t("monRefresh")}
          </button>
        </div>
      </div>

      {/* Table des checks */}
      <div className="bg-white border border-line rounded-lg p-5 shadow-sm">
        <h3 className="font-display font-bold text-sm text-ink mb-3">{t("monChecks")}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left rtl:text-right">
            <thead>
              <tr className="border-b border-line text-muted uppercase text-[10px]">
                <th className="py-3 px-3">{t("monCheckId")}</th>
                <th className="py-3 px-3">{t("thStatus")}</th>
                <th className="py-3 px-3">{t("monValue")}</th>
                <th className="py-3 px-3">{t("monDetail")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {monitor.checks.map((c) => (
                <tr key={c.id}>
                  <td className="py-3 px-3 font-semibold text-ink">{CHECK_LABELS[c.id]?.[lang] || c.id}</td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${STATUS_BADGE[c.status] || ""}`}>{c.status}</span>
                  </td>
                  <td className="py-3 px-3 font-mono text-[11px]">{fmtCheckValue(c.value)}</td>
                  <td className="py-3 px-3 text-muted">{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activité de la fenêtre */}
        <div className="bg-white border border-line rounded-lg p-5 shadow-sm">
          <h3 className="font-display font-bold text-sm text-ink mb-3">{t("monStats")}</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              [t("monCompanies"), monitor.stats?.companies_active],
              [t("monOpportunities"), monitor.stats?.opportunities],
              [t("monMatches"), monitor.stats?.matches_new],
              [t("monDigests"), monitor.stats?.digests_sent],
            ].map(([label, v]) => (
              <div key={String(label)} className="border border-line rounded-lg p-3">
                <div className="text-[10px] font-bold text-muted uppercase tracking-wider">{String(label)}</div>
                <div className="text-xl font-bold font-display text-ink mt-1">{Number(v ?? 0).toLocaleString("fr-FR")}</div>
              </div>
            ))}
          </div>
        </div>

        {/* État des composants (snapshot config) */}
        <div className="bg-white border border-line rounded-lg p-5 shadow-sm">
          <h3 className="font-display font-bold text-sm text-ink mb-3">{t("monSnapshot")}</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(monitor.config || {}).map(([k, v]) => (
              <span key={k} className={`px-2 py-1 rounded font-bold text-[10px] ${v ? "bg-greenbg text-greenbrand" : "bg-redbg text-redbrand"}`}>
                {k} : {v ? "✓" : "✗"}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );

  const drawerEl = (
    <div className={`drawer-backdrop ${trace ? "open" : ""}`}
         onClick={(e) => { if (e.target === e.currentTarget) setTrace(null); }}
         aria-hidden={!trace}>
      <aside className="drawer-panel p-6">
        {trace && (
          <div className="flex flex-col justify-between min-h-full">
            <div className="space-y-6">
              <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-terra">{t("drawerTelemetry")}</span>
                  <h2 className="font-display font-bold text-xl text-ink leading-tight mt-1">Trace {trace.request.id.slice(0, 8)}</h2>
                  <p className="text-xs text-muted mt-1">
                    {trace.request.route} · {trace.request.outcome} · {fmtMs(trace.request.latency_ms)}
                  </p>
                  <p className="text-[11px] font-semibold text-ink mt-1">
                    Tokens : {(Number(trace.request.tokens_in) || 0).toLocaleString("fr-FR")} in · {(Number(trace.request.tokens_out) || 0).toLocaleString("fr-FR")} out
                    {" "}· Coût : ${Number(trace.request.llm_cost_usd || 0).toFixed(4)}
                  </p>
                </div>
                <button onClick={() => setTrace(null)} type="button"
                        className="border border-line rounded-md p-1.5 hover:bg-paper text-ink transition-all">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">{t("executionSteps")}</h3>
                <div className="bg-ink text-[#a8d0bb] font-mono text-[11px] p-3 rounded-lg leading-relaxed space-y-1 overflow-x-auto">
                  {trace.steps.length === 0 && (
                    <div className="text-[#91a3b0]">{t("noSteps")}</div>
                  )}
                  {trace.steps.map((s, i) => {
                    const dur = Number(s.duration_s);
                    return (
                      <div key={i} className={s.detail?.startsWith("error:") ? "text-red-400" : ""}>
                        {new Date(s.created_at).toLocaleTimeString("fr-FR")} [{s.agent}]
                        {" "}{s.detail || "—"}{!isNaN(dur) && s.duration_s != null ? ` (${dur.toFixed(2)}s)` : ""}
                      </div>
                    );
                  })}
                  {trace.request.error && (
                    <div className="text-red-400">[error] {trace.request.error}</div>
                  )}
                  {trace.steps.length > 0 && (
                    <div className="text-green-300">[Pipeline] {trace.request.outcome === "ok" ? (lang === "fr" ? "Terminé avec succès." : "اكتمل بنجاح.") : (lang === "fr" ? "Terminé avec erreur." : "اكتمل بخطأ.")}</div>
                  )}
                </div>
              </div>
            </div>
            <div className="pt-4 border-t border-line mt-6 text-right">
              <button onClick={() => setTrace(null)}
                      className="bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded text-xs font-bold transition-all shadow-sm">
                {t("closeBtn")}
              </button>
            </div>
          </div>
        )}
      </aside>
    </div>
  );

  const sourcesEl = (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-display font-bold text-base text-ink">{t("tabSources")}</h3>
          <p className="text-xs text-muted mt-1">{t("sourcesSub")}</p>
        </div>
        <button className="btn-primary text-sm px-4 py-2"
                onClick={() => { setSrcEditId(null); setSName(""); setSUrl("");
                  setSKind("rss"); setSAdapter("generic_rss"); setSCadence(24);
                  setShowSrcForm(true); }}>
          {t("addSourceBtn")}
        </button>
      </div>

      {showSrcForm && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl border border-line bg-white">
          <input className="input" placeholder={t("srcName")} value={sName} onChange={e => setSName(e.target.value)} />
          <input className="input" placeholder={t("srcUrl")} value={sUrl} onChange={e => setSUrl(e.target.value)} />
          <select className="input" value={sKind} onChange={e => setSKind(e.target.value)}>
            <option value="portal_html">portal_html</option>
            <option value="rss">rss</option>
            <option value="api_json">api_json</option>
          </select>
          <select className="input" value={sAdapter} onChange={e => setSAdapter(e.target.value)}>
            <option value="marchespublics">marchespublics</option>
            <option value="generic_rss">generic_rss</option>
          </select>
          <input className="input" type="number" min={1} placeholder={t("srcCadence")}
                 value={sCadence} onChange={e => setSCadence(Number(e.target.value) || 24)} />
          <div className="flex gap-2 items-end">
            <button className="btn-primary px-4 py-2 text-sm" disabled={busy} onClick={saveSource}>{t("saveSrcBtn")}</button>
            <button className="px-4 py-2 text-sm text-muted" onClick={resetSrcForm}>{t("cancelBtn")}</button>
          </div>
        </div>
      )}

      {!sources.length ? (
        <p className="text-sm text-muted">{t("noSources")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2 px-3">{t("thSource")}</th>
                <th className="py-2 px-3">{t("thKind")}</th>
                <th className="py-2 px-3">{t("thCadence")}</th>
                <th className="py-2 px-3">{t("thLastRun")}</th>
                <th className="py-2 px-3">{t("thStatus")}</th>
                <th className="py-2 px-3">{t("thEnabled")}</th>
                <th className="py-2 px-3"></th>
              </tr>
            </thead>
            <tbody>
              {sources.map(s => (
                <tr key={s.id} className="border-b border-line/60">
                  <td className="py-3 px-3">
                    <div className="font-medium text-ink">{s.name}</div>
                    <div className="text-xs text-muted truncate max-w-[240px]">{s.base_url}</div>
                  </td>
                  <td className="py-3 px-3 text-xs">{s.kind}<br /><span className="text-muted">{s.adapter}</span></td>
                  <td className="py-3 px-3">{s.cadence_hours}h</td>
                  <td className="py-3 px-3 text-xs">{s.last_run_at ? new Date(s.last_run_at).toLocaleString(lang === "ar" ? "ar" : "fr-FR") : "—"}</td>
                  <td className="py-3 px-3 text-xs">
                    <span className={s.last_status && s.last_status.startsWith("ok") ? "text-green-700" : "text-red-600"}>
                      {s.last_status || "—"}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <button onClick={() => toggleSource(s)} disabled={busy}
                            className={`px-2 py-1 rounded-full text-xs ${s.enabled ? "bg-green-100 text-green-800" : "bg-gray-200 text-gray-600"}`}>
                      {s.enabled ? "ON" : "OFF"}
                    </button>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex gap-2 text-xs">
                      <button className="underline" onClick={() => { setSrcEditId(s.id); setSName(s.name);
                        setSUrl(s.base_url); setSKind(s.kind); setSAdapter(s.adapter);
                        setSCadence(s.cadence_hours); setShowSrcForm(true); }}>✏️</button>
                      <button className="underline" onClick={() => testSource(s)} disabled={busy}>▶ {t("testBtn")}</button>
                      <button className="underline text-red-600" onClick={() => deleteSource(s)} disabled={busy}>{t("delBtn")}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  if (!loaded) {
    return <main className="page container"><p className="subtitle">{t("loading")}</p></main>;
  }

  return (
    <>
      {headerEl}
      {tabsEl}
      <main className="max-w-[1400px] w-full mx-auto p-4 lg:p-8 space-y-6 flex-1">
        {msg && <div className="message message-ok">{msg}</div>}
        {err && <div className="message message-err">{err}</div>}
        {tab === "finances" && financesEl}
        {tab === "agents" && agentsEl}
        {tab === "logs" && logsEl}
        {tab === "monitor" && monitoringEl}
        {tab === "sources" && sourcesEl}
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
