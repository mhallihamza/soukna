"use client";

// Écran de chargement de marque : logo + anneau de progression + message
// contextuel. Utilisé par le tableau de bord entreprise et la console admin.

export default function BrandLoader({ label }: { label: string }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-paper gap-5" role="status" aria-live="polite">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <span className="absolute inset-0 rounded-full border-2 border-greenbrand/20 border-t-greenbrand animate-spin" />
        <svg className="w-8 h-8 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
          <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
          <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
        </svg>
      </div>
      <div className="text-center">
        <span className="font-display text-xl font-bold text-ink tracking-tight">Soukna</span>
        <p className="text-xs text-muted mt-1">{label}</p>
      </div>
    </div>
  );
}
