"use client";

import { useEffect, useRef, useState } from "react";

interface TimeSliderProps {
  years: number[];
  value: number;
  onChange: (year: number) => void;
  summary?: string;
}

export default function TimeSlider({
  years,
  value,
  onChange,
  summary,
}: TimeSliderProps) {
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!playing) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }
    timerRef.current = setInterval(() => {
      const last = years[years.length - 1];
      if (value >= last) return;
      onChange(years[Math.min(years.indexOf(value) + 1, years.length - 1)]);
    }, 900);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [playing, value, years, onChange]);

  useEffect(() => {
    if (playing && value === years[years.length - 1]) {
      const stop = setTimeout(() => setPlaying(false), 900);
      return () => clearTimeout(stop);
    }
  }, [playing, value, years]);

  if (years.length === 0) return null;

  const min = years[0];
  const max = years[years.length - 1];

  return (
    <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full border border-[var(--line)] bg-white/95 px-4 py-2 text-[11px] shadow-sm backdrop-blur">
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        className="grid h-7 w-7 place-items-center rounded-full bg-[var(--ink)] text-white transition hover:opacity-90"
        aria-label={playing ? "暂停" : "播放"}
      >
        {playing ? (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <rect x="2.5" y="1.5" width="2.5" height="9" rx="0.5" />
            <rect x="7" y="1.5" width="2.5" height="9" rx="0.5" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <path d="M3 1.5 L10 6 L3 10.5 Z" />
          </svg>
        )}
      </button>

      <div className="flex items-center gap-2">
        <span className="num text-[10px] text-[var(--ink-soft)]">{min}</span>
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="time-slider-range h-1 w-56 cursor-pointer appearance-none rounded-full bg-[var(--line)] accent-[var(--accent-moss)]"
        />
        <span className="num text-[10px] text-[var(--ink-soft)]">{max}</span>
      </div>

      <div className="flex items-baseline gap-2 border-l border-[var(--line)] pl-3">
        <span className="num text-[16px] font-semibold text-[var(--ink)]">
          {value}
        </span>
        {summary && (
          <span className="text-[10px] text-[var(--ink-muted)]">{summary}</span>
        )}
      </div>
    </div>
  );
}
