"use client";

import type { ScenarioSpecies, SpeciesOption } from "@/lib/api";

interface ScenarioControlsProps {
  species: ScenarioSpecies;
  density: number;
  years: number;
  speciesOptions: SpeciesOption[];
  onSpeciesChange: (value: ScenarioSpecies) => void;
  onDensityChange: (value: number) => void;
  onYearsChange: (value: number) => void;
  disabled?: boolean;
}

const DENSITY_MIN = 0;
const DENSITY_MAX = 3000;
const DENSITY_STEP = 100;
const YEARS_MIN = 1;
const YEARS_MAX = 15;

export default function ScenarioControls({
  species,
  density,
  years,
  speciesOptions,
  onSpeciesChange,
  onDensityChange,
  onYearsChange,
  disabled = false,
}: ScenarioControlsProps) {
  return (
    <div className="flex flex-col gap-4 text-[12px]">
      <label className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
          树种
        </span>
        <select
          value={species}
          onChange={(e) => onSpeciesChange(e.target.value as ScenarioSpecies)}
          disabled={disabled}
          className="rounded-md border border-[var(--line)] bg-white px-2 py-1.5 text-[12px] font-medium text-[var(--ink)] disabled:opacity-60"
        >
          {speciesOptions.map((opt) => (
            <option key={opt.key} value={opt.key}>
              {opt.label_cn} · 年耗水 ~{opt.water_use_mm.toFixed(0)} mm
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
            增加密度
          </span>
          <span className="num text-[12px] font-medium text-[var(--ink)]">
            {density} 株/公顷
          </span>
        </div>
        <input
          type="range"
          min={DENSITY_MIN}
          max={DENSITY_MAX}
          step={DENSITY_STEP}
          value={density}
          disabled={disabled}
          onChange={(e) => onDensityChange(Number(e.target.value))}
          className="accent-green-700 disabled:opacity-60"
        />
        <div className="num flex justify-between text-[10px] text-[var(--ink-soft)]">
          <span>{DENSITY_MIN}</span>
          <span>1500</span>
          <span>{DENSITY_MAX}</span>
        </div>
      </label>

      <label className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
            投影年限
          </span>
          <span className="num text-[12px] font-medium text-[var(--ink)]">
            {years} 年
          </span>
        </div>
        <input
          type="range"
          min={YEARS_MIN}
          max={YEARS_MAX}
          step={1}
          value={years}
          disabled={disabled}
          onChange={(e) => onYearsChange(Number(e.target.value))}
          className="accent-green-700 disabled:opacity-60"
        />
        <div className="num flex justify-between text-[10px] text-[var(--ink-soft)]">
          <span>{YEARS_MIN}</span>
          <span>8</span>
          <span>{YEARS_MAX}</span>
        </div>
      </label>
    </div>
  );
}
