"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ScenarioControls from "@/components/ScenarioControls";
import ScenarioChart from "@/components/ScenarioChart";
import DemoDataBadge from "@/components/DemoDataBadge";
import {
  fetchScenarioDefaults,
  postScenario,
  RISK_LEVEL_COLORS,
  RISK_LEVEL_LABELS,
  type ScenarioBaseline,
  type ScenarioDefaultsResponse,
  type ScenarioResponse,
  type ScenarioSpecies,
  type SpeciesOption,
} from "@/lib/api";

interface ScenarioPanelProps {
  regionId: number;
  /** Optional explicit className for the outer container. */
  className?: string;
  style?: React.CSSProperties;
}

const DEBOUNCE_MS = 400;
const DEFAULT_SPECIES: ScenarioSpecies = "caragana";
const DEFAULT_DENSITY = 600;
const DEFAULT_YEARS = 5;

export default function ScenarioPanel({
  regionId,
  className,
  style,
}: ScenarioPanelProps) {
  const [species, setSpecies] = useState<ScenarioSpecies>(DEFAULT_SPECIES);
  const [density, setDensity] = useState<number>(DEFAULT_DENSITY);
  const [years, setYears] = useState<number>(DEFAULT_YEARS);

  const [speciesOptions, setSpeciesOptions] = useState<SpeciesOption[]>([]);
  const [baseline, setBaseline] = useState<ScenarioBaseline | null>(null);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Defaults — fetched once per region. Provides the species catalog
  // (with localized labels) and the baseline starting state shown next
  // to the chart.
  useEffect(() => {
    let cancelled = false;
    fetchScenarioDefaults(regionId)
      .then((res: ScenarioDefaultsResponse | null) => {
        if (cancelled || res === null) return;
        setSpeciesOptions(res.species_options);
        setBaseline(res.baseline);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "无法加载情景默认值");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [regionId]);

  // Debounced scenario simulation — fires on any control change and on
  // initial mount once speciesOptions are loaded.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (speciesOptions.length === 0) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);

    let cancelled = false;
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      setError(null);
      postScenario({
        region_id: regionId,
        species,
        additional_density_per_ha: density,
        years,
      })
        .then((res: ScenarioResponse | null) => {
          if (cancelled) return;
          if (res === null) {
            setError("情景接口返回失败");
            setResult(null);
          } else {
            setResult(res);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "情景请求失败");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [regionId, species, density, years, speciesOptions.length]);

  const finalRiskLevel = result?.yearly[result.yearly.length - 1]?.risk_level ?? null;
  const finalRiskLabel =
    finalRiskLevel != null ? RISK_LEVEL_LABELS[finalRiskLevel] ?? "—" : "—";
  const finalRiskColor =
    finalRiskLevel != null ? RISK_LEVEL_COLORS[finalRiskLevel] ?? "#a1a1aa" : "#a1a1aa";

  const baselineRows = useMemo(() => {
    if (!baseline) return [];
    return [
      { label: "起始 FVC", value: (baseline.current_fvc * 100).toFixed(1) + "%" },
      {
        label: "起始土壤水分",
        value: baseline.current_soil_moisture.toFixed(3) + " m³/m³",
      },
      { label: "年降水", value: baseline.annual_precip_mm.toFixed(0) + " mm" },
      { label: "年均风速", value: baseline.avg_wind_speed_ms.toFixed(1) + " m/s" },
    ];
  }, [baseline]);

  return (
    <section className={"relative " + (className ?? "")} style={style}>
      <header className="mb-3 flex items-center gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
            造林情景 · Scenario Lab
          </div>
          <h2 className="mt-1 text-[18px] font-semibold tracking-tight text-[var(--ink)]">
            树种 × 密度 × 年限 → 多年生态演化
          </h2>
        </div>
        <div className="ml-auto">
          <DemoDataBadge />
        </div>
      </header>

      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "minmax(220px, 280px) 1fr" }}
      >
        {/* Left: controls + baseline + recommendation */}
        <div className="flex flex-col gap-4">
          <div className="card-surface px-4 py-4">
            <ScenarioControls
              species={species}
              density={density}
              years={years}
              speciesOptions={speciesOptions}
              onSpeciesChange={setSpecies}
              onDensityChange={setDensity}
              onYearsChange={setYears}
              disabled={speciesOptions.length === 0}
            />
          </div>

          {baselineRows.length > 0 && (
            <div className="card-surface card-surface--warm px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
                起始状态 (区域基线)
              </div>
              <dl className="mt-2 space-y-1 text-[11.5px]">
                {baselineRows.map((row) => (
                  <div
                    key={row.label}
                    className="flex items-baseline justify-between"
                  >
                    <dt className="text-[var(--ink-muted)]">{row.label}</dt>
                    <dd className="num font-medium text-[var(--ink)]">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {result && (
            <div className="card-surface px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
                  {result.years} 年后
                </div>
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                  style={{ backgroundColor: finalRiskColor }}
                >
                  {finalRiskLabel}
                </span>
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-[var(--ink-muted)]">
                {result.recommendation}
              </p>
            </div>
          )}
        </div>

        {/* Right: projection chart */}
        <div className="card-surface relative p-2" style={{ minHeight: 320 }}>
          {loading && (
            <div className="absolute right-3 top-3 z-10 text-[11px] text-[var(--ink-soft)]">
              计算中…
            </div>
          )}
          {error && (
            <div className="absolute right-3 top-3 z-10 text-[11px] text-red-600">
              {error}
            </div>
          )}
          {result ? (
            <ScenarioChart yearly={result.yearly} />
          ) : (
            <div className="flex h-full items-center justify-center text-[12px] text-[var(--ink-soft)]">
              选择参数后开始模拟
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
