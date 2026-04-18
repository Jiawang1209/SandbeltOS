"use client";

interface RegionPillOption {
  id: number | null;
  label: string;
}

interface SiteHeaderProps {
  regions: RegionPillOption[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}

export default function SiteHeader({ regions, selectedId, onSelect }: SiteHeaderProps) {
  return (
    <header className="relative z-10">
      {/* Accent stripe */}
      <div className="header-accent" />

      {/* Main header */}
      <div
        className="border-b border-[var(--line)]"
        style={{ background: "var(--surface)" }}
      >
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-6 px-6 py-4">
          {/* Identity */}
          <a href="/" className="flex items-center gap-4 group">
            <div
              className="grid h-11 w-11 place-items-center rounded-md text-white shadow-sm transition group-hover:shadow"
              style={{
                background:
                  "linear-gradient(145deg, var(--forest-700) 0%, var(--forest-900) 100%)",
              }}
              aria-hidden
            >
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2 L3 22 L21 22 Z" />
                <path d="M12 2 L12 22" opacity="0.4" />
                <path d="M7 14 L17 14" opacity="0.4" />
              </svg>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <h1 className="font-serif text-[22px] font-semibold tracking-tight text-[var(--ink-strong)]">
                  三北防护林智慧生态决策支持系统
                </h1>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-[var(--ink-muted)]">
                <span className="divider-stripe" />
                <span className="tracking-[0.08em] uppercase">
                  SandbeltOS · Three-North Shelterbelt Intelligence
                </span>
              </div>
            </div>
          </a>

          {/* Region selector + actions */}
          <div className="flex items-center gap-2">
            <div className="flex overflow-hidden rounded-md border border-[var(--line)] bg-[var(--surface-sunk)] p-0.5">
              {regions.map((r) => {
                const active = r.id === selectedId;
                return (
                  <button
                    key={r.id ?? "all"}
                    onClick={() => onSelect(r.id)}
                    className={`px-3.5 py-1.5 text-xs font-medium tracking-wide transition ${
                      active
                        ? "rounded-[5px] bg-white text-[var(--forest-900)] shadow-[0_1px_2px_rgba(10,42,28,0.1)]"
                        : "text-[var(--ink-muted)] hover:text-[var(--ink-strong)]"
                    }`}
                    style={active ? { borderBottom: "2px solid var(--forest-700)" } : undefined}
                  >
                    {r.label}
                  </button>
                );
              })}
            </div>
            <a
              href="/chat"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-md border border-[var(--forest-700)] px-3.5 py-1.5 text-xs font-medium text-[var(--forest-900)] transition hover:bg-[var(--forest-900)] hover:text-white"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span>智能助手</span>
            </a>
          </div>
        </div>
      </div>
    </header>
  );
}
