export default function SiteFooter() {
  return (
    <footer
      className="mt-8 border-t border-white/5 text-[12px]"
      style={{
        background:
          "linear-gradient(180deg, var(--forest-900) 0%, var(--forest-950) 100%)",
        color: "rgba(244,241,232,0.72)",
      }}
    >
      <div className="mx-auto grid max-w-[1600px] gap-8 px-6 py-8 md:grid-cols-4">
        <div className="md:col-span-2">
          <div className="flex items-center gap-3">
            <div
              className="grid h-9 w-9 place-items-center rounded-md border border-white/15"
              aria-hidden
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2 L3 22 L21 22 Z" />
                <path d="M12 2 L12 22" opacity="0.4" />
                <path d="M7 14 L17 14" opacity="0.4" />
              </svg>
            </div>
            <div>
              <div className="font-serif text-[15px] tracking-tight text-white">
                三北防护林智慧生态决策支持系统
              </div>
              <div className="mt-0.5 text-[10.5px] tracking-[0.14em] uppercase text-white/55">
                SandbeltOS · Three-North Shelterbelt Intelligence
              </div>
            </div>
          </div>
          <p className="mt-4 max-w-xl leading-relaxed text-white/65">
            面向三北防护林工程的智慧生态决策支持平台，聚合多源遥感、气象再分析与土地覆盖产品，
            持续追踪科尔沁与浑善达克两大重点沙地的植被恢复与沙化风险演变。
          </p>
        </div>

        <div>
          <div className="text-[10.5px] uppercase tracking-[0.2em] text-white/45">
            数据来源
          </div>
          <ul className="mt-3 space-y-1.5">
            <li>NASA MODIS · MOD13Q1</li>
            <li>USGS Landsat Collection 2</li>
            <li>ECMWF ERA5-Land</li>
            <li>ESA WorldCover 10 m</li>
          </ul>
        </div>

        <div>
          <div className="text-[10.5px] uppercase tracking-[0.2em] text-white/45">
            研制单位
          </div>
          <ul className="mt-3 space-y-1.5">
            <li className="font-serif text-white/90">
              中国科学院沈阳应用生态研究所
            </li>
            <li>沙地生态监测研究中心</li>
            <li className="pt-2 text-white/50">
              Shenyang Institute of Applied Ecology, CAS
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-white/5">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-6 py-3 text-[11px] text-white/50">
          <span>
            © {new Date().getFullYear()} SandbeltOS · 保留所有权利
          </span>
          <span className="tracking-[0.1em]">
            Ver. Phase 4 · RAG-powered Copilot
          </span>
        </div>
      </div>
    </footer>
  );
}
