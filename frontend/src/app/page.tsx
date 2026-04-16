import BackendStatus from "@/components/BackendStatus";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-6 font-sans dark:bg-zinc-950">
      <main className="flex w-full max-w-lg flex-col items-center gap-8 text-center">
        <div className="flex flex-col items-center gap-3">
          <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
            SandbeltOS
          </h1>
          <p className="text-lg text-zinc-500 dark:text-zinc-400">
            三北防护林智慧生态决策支持系统
          </p>
          <p className="text-sm text-zinc-400 dark:text-zinc-500">
            Smart Ecological Decision Support System
          </p>
        </div>

        <BackendStatus />

        <a
          href="/dashboard"
          className="w-full rounded-lg bg-green-600 px-6 py-3 text-center font-medium text-white transition hover:bg-green-700"
        >
          进入生态监测仪表盘 →
        </a>

        <div className="grid w-full grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <div className="font-medium text-green-800">GIS 地图</div>
            <div className="mt-1 text-green-600">Phase 2 ✓</div>
          </div>
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <div className="font-medium text-green-800">生态仪表盘</div>
            <div className="mt-1 text-green-600">Phase 2 ✓</div>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="font-medium text-zinc-900 dark:text-zinc-100">
              RAG 问答
            </div>
            <div className="mt-1 text-zinc-500 dark:text-zinc-400">
              Phase 4
            </div>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="font-medium text-zinc-900 dark:text-zinc-100">
              预测分析
            </div>
            <div className="mt-1 text-zinc-500 dark:text-zinc-400">
              Phase 5
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
