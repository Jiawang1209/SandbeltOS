"use client";

const EXAMPLES = [
  { category: "风险评估", q: "科尔沁沙地现在风险等级如何？" },
  { category: "趋势", q: "浑善达克近 20 年 NDVI 趋势怎样？" },
  { category: "指标解释", q: "RWEQ 公式是什么？有哪些输入？" },
  { category: "物种选择", q: "Caragana korshinskii 适合哪些区域造林？" },
  { category: "政策", q: "三北防护林科学绿化策略的核心原则？" },
  { category: "方法论", q: "如何判断一个区域是否已沙化？" },
];

interface Props {
  onPick: (q: string) => void;
}

export function EmptyState({ onPick }: Props) {
  return (
    <div className="mx-auto max-w-2xl py-16 text-center">
      <h1 className="mb-2 text-2xl font-semibold text-neutral-900">
        SandbeltOS 智慧问答
      </h1>
      <p className="mb-8 text-sm text-neutral-500">
        基于 12 篇核心文献 + 实时传感器数据回答你的问题
      </p>
      <div className="grid grid-cols-2 gap-3 text-left">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.q}
            onClick={() => onPick(ex.q)}
            className="rounded-lg border border-neutral-200 p-3 text-sm hover:border-blue-400 hover:bg-blue-50"
          >
            <div className="mb-1 text-xs font-medium uppercase text-neutral-400">
              {ex.category}
            </div>
            <div className="text-neutral-800">{ex.q}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
