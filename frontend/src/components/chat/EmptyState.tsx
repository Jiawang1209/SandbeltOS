"use client";

interface ExampleGroup {
  category: string;
  items: { label: string; q: string }[];
}

const GROUPS: ExampleGroup[] = [
  {
    category: "风险 & 趋势",
    items: [
      { label: "风险评估", q: "科尔沁沙地现在风险等级如何？" },
      { label: "NDVI 趋势", q: "浑善达克近 20 年 NDVI 趋势怎样？" },
    ],
  },
  {
    category: "方法论",
    items: [
      { label: "指标解释", q: "RWEQ 公式是什么？有哪些输入？" },
      { label: "判别标准", q: "如何判断一个区域是否已沙化？" },
    ],
  },
  {
    category: "实务决策",
    items: [
      { label: "物种选择", q: "Caragana korshinskii 适合哪些区域造林？" },
      { label: "政策依据", q: "三北防护林科学绿化策略的核心原则？" },
    ],
  },
];

interface Props {
  onPick: (q: string) => void;
}

export function EmptyState({ onPick }: Props) {
  return (
    <div className="relative mx-auto flex max-w-3xl flex-col items-start px-2 pt-12 pb-8 sm:pt-20">
      <div className="bg-topo pointer-events-none absolute inset-0 -z-10 rounded-[24px] opacity-60" />

      <div className="eyebrow mb-3">Three-North Shelterbelt · RAG Copilot</div>
      <h1 className="font-serif text-[34px] font-semibold leading-tight tracking-tight text-[var(--ink-strong)] sm:text-[40px]">
        智慧生态问答
      </h1>
      <div className="mt-3 flex items-center gap-3 text-[13px] text-[var(--ink-muted)]">
        <span className="divider-stripe" />
        <span>
          基于 12 篇核心文献与实时遥感指标，为沙地治理提供有据可循的决策支持
        </span>
      </div>

      <div className="mt-10 grid w-full gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {GROUPS.map((g) => (
          <div key={g.category} className="flex flex-col gap-2">
            <div className="eyebrow pb-1">{g.category}</div>
            {g.items.map((ex) => (
              <button
                key={ex.q}
                onClick={() => onPick(ex.q)}
                className="card-surface card-hover group flex flex-col items-start gap-1 px-4 py-3 text-left"
              >
                <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--ink-soft)] group-hover:text-[var(--forest-700)]">
                  {ex.label}
                </span>
                <span className="text-sm leading-snug text-[var(--ink-strong)]">
                  {ex.q}
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
