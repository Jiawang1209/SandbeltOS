"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchLandsatTileUrl, type RegionsGeoJSON } from "@/lib/api";

interface SwipeCompareMapProps {
  regions: RegionsGeoJSON | null;
  selectedRegionId: number | null;
  beforeYear: number;
  afterYear: number;
}

// Two overlapping MapLibre instances. The "after" map is clipped so only the
// pixels to the right of the user-controlled divider are visible, revealing the
// "before" map underneath. Camera state is synced via `move` events so pan/zoom
// on either side stays in lockstep.
export default function SwipeCompareMap({
  regions,
  selectedRegionId,
  beforeYear,
  afterYear,
}: SwipeCompareMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLDivElement>(null);
  const afterRef = useRef<HTMLDivElement>(null);
  const beforeMapRef = useRef<maplibregl.Map | null>(null);
  const afterMapRef = useRef<maplibregl.Map | null>(null);
  // Ratio 0..1 — left fraction occupied by the "before" pane.
  const [divider, setDivider] = useState(0.5);
  const [beforeUrl, setBeforeUrl] = useState<string | null>(null);
  const [afterUrl, setAfterUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch both tile URLs. Keyed on year so changing the slider refreshes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchLandsatTileUrl(beforeYear),
      fetchLandsatTileUrl(afterYear),
    ])
      .then(([b, a]) => {
        if (cancelled) return;
        setBeforeUrl(b.tile_url);
        setAfterUrl(a.tile_url);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "tile fetch failed");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [beforeYear, afterYear]);

  // Build a style containing one Landsat raster source + the polygon outline
  // layer for the selected sandy land. Called for each map instance.
  const buildStyle = useCallback(
    (tileUrl: string): maplibregl.StyleSpecification => ({
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "&copy; OpenStreetMap contributors",
        },
        landsat: {
          type: "raster",
          tiles: [tileUrl],
          tileSize: 256,
          attribution: "USGS Landsat / Google Earth Engine",
        },
      },
      layers: [
        { id: "osm", type: "raster", source: "osm" },
        { id: "landsat", type: "raster", source: "landsat" },
      ],
    }),
    []
  );

  // Initialize both maps once tile URLs are ready.
  useEffect(() => {
    if (!beforeRef.current || !afterRef.current) return;
    if (!beforeUrl || !afterUrl) return;
    if (beforeMapRef.current || afterMapRef.current) return;

    const before = new maplibregl.Map({
      container: beforeRef.current,
      style: buildStyle(beforeUrl),
      center: [118, 44],
      zoom: 6,
      attributionControl: false,
    });
    const after = new maplibregl.Map({
      container: afterRef.current,
      style: buildStyle(afterUrl),
      center: [118, 44],
      zoom: 6,
      attributionControl: false,
    });
    after.addControl(new maplibregl.NavigationControl(), "top-right");

    beforeMapRef.current = before;
    afterMapRef.current = after;

    // Camera sync. A simple `syncing` guard prevents feedback loops.
    let syncing = false;
    const syncFrom = (src: maplibregl.Map, dst: maplibregl.Map) => () => {
      if (syncing) return;
      syncing = true;
      dst.jumpTo({
        center: src.getCenter(),
        zoom: src.getZoom(),
        bearing: src.getBearing(),
        pitch: src.getPitch(),
      });
      syncing = false;
    };
    const aToB = syncFrom(after, before);
    const bToA = syncFrom(before, after);
    after.on("move", aToB);
    before.on("move", bToA);

    const ro = new ResizeObserver(() => {
      before.resize();
      after.resize();
    });
    if (containerRef.current) ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      before.off("move", bToA);
      after.off("move", aToB);
      before.remove();
      after.remove();
      beforeMapRef.current = null;
      afterMapRef.current = null;
    };
  }, [beforeUrl, afterUrl, buildStyle]);

  // Swap the Landsat tile source on the already-initialized maps when the
  // year changes (instead of re-creating the whole map).
  useEffect(() => {
    const m = beforeMapRef.current;
    if (!m || !beforeUrl) return;
    const apply = () => {
      if (m.getLayer("landsat")) m.removeLayer("landsat");
      if (m.getSource("landsat")) m.removeSource("landsat");
      m.addSource("landsat", {
        type: "raster",
        tiles: [beforeUrl],
        tileSize: 256,
      });
      m.addLayer({ id: "landsat", type: "raster", source: "landsat" });
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [beforeUrl]);

  useEffect(() => {
    const m = afterMapRef.current;
    if (!m || !afterUrl) return;
    const apply = () => {
      if (m.getLayer("landsat")) m.removeLayer("landsat");
      if (m.getSource("landsat")) m.removeSource("landsat");
      m.addSource("landsat", {
        type: "raster",
        tiles: [afterUrl],
        tileSize: 256,
      });
      m.addLayer({ id: "landsat", type: "raster", source: "landsat" });
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [afterUrl]);

  // Draw selected-region polygon outline on both maps for visual anchor.
  useEffect(() => {
    if (!regions) return;
    const target = regions.features.find(
      (f) =>
        f.properties.level === "subregion" &&
        (selectedRegionId == null || f.properties.id === selectedRegionId)
    );
    const fc = target
      ? {
          type: "FeatureCollection" as const,
          features: [target],
        }
      : { type: "FeatureCollection" as const, features: [] };

    for (const m of [beforeMapRef.current, afterMapRef.current]) {
      if (!m) continue;
      const apply = () => {
        if (m.getSource("focus")) {
          (m.getSource("focus") as maplibregl.GeoJSONSource).setData(
            fc as unknown as GeoJSON.FeatureCollection
          );
        } else {
          m.addSource("focus", {
            type: "geojson",
            data: fc as unknown as GeoJSON.FeatureCollection,
          });
          m.addLayer({
            id: "focus-outline",
            type: "line",
            source: "focus",
            paint: {
              "line-color": "#fde68a",
              "line-width": 2,
            },
          });
        }
      };
      if (m.isStyleLoaded()) apply();
      else m.once("load", apply);
    }
  }, [regions, selectedRegionId]);

  // Fit to the selected region's bounds once maps are ready.
  useEffect(() => {
    if (!regions) return;
    const before = beforeMapRef.current;
    const after = afterMapRef.current;
    if (!before || !after) return;

    const subs = regions.features.filter(
      (f) => f.properties.level === "subregion"
    );
    const target =
      selectedRegionId != null
        ? subs.filter((f) => f.properties.id === selectedRegionId)
        : subs;
    if (target.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    for (const f of target) {
      if (!f.geometry) continue;
      const raw = f.geometry.coordinates as unknown as
        | number[][][]
        | number[][][][];
      const rings: number[][][] =
        (f.geometry as unknown as { type: string }).type === "MultiPolygon"
          ? (raw as number[][][][]).flat()
          : (raw as number[][][]);
      for (const c of rings.flat()) bounds.extend([c[0], c[1]]);
    }
    if (bounds.isEmpty()) return;

    const fit = () => {
      before.resize();
      after.resize();
      before.fitBounds(bounds, { padding: 40, duration: 0 });
    };
    requestAnimationFrame(() => requestAnimationFrame(fit));
  }, [regions, selectedRegionId, beforeUrl, afterUrl]);

  // Pointer-driven divider drag.
  const dragging = useRef(false);
  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onPointerUp = (e: React.PointerEvent) => {
    dragging.current = false;
    (e.target as Element).releasePointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    setDivider(Math.max(0.02, Math.min(0.98, x)));
  };

  const dividerPct = `${(divider * 100).toFixed(2)}%`;

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden rounded-lg"
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* After map (top of stack, clipped to right of divider) */}
      <div
        ref={afterRef}
        className="absolute inset-0"
        style={{ clipPath: `inset(0 0 0 ${dividerPct})` }}
      />
      {/* Before map (base) */}
      <div ref={beforeRef} className="absolute inset-0" style={{ zIndex: -1 }} />

      {/* Divider bar + handle */}
      <div
        className="pointer-events-none absolute inset-y-0 w-[2px] bg-white/90 shadow-[0_0_0_1px_rgba(0,0,0,0.25)]"
        style={{ left: dividerPct, transform: "translateX(-1px)" }}
      />
      <div
        role="slider"
        aria-label="Swipe compare divider"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(divider * 100)}
        tabIndex={0}
        className="absolute top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border border-zinc-200 bg-white shadow-md"
        style={{ left: dividerPct }}
        onPointerDown={onPointerDown}
      >
        <span className="text-[10px] font-bold tracking-tighter text-zinc-700">
          ◀▶
        </span>
      </div>

      {/* Year badges */}
      <div
        className="pointer-events-none absolute left-3 top-3 rounded-md border border-zinc-200 bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-zinc-800 shadow-sm backdrop-blur"
        style={{ opacity: divider > 0.12 ? 1 : 0 }}
      >
        {beforeYear}
      </div>
      <div
        className="pointer-events-none absolute right-3 top-3 rounded-md border border-zinc-200 bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-zinc-800 shadow-sm backdrop-blur"
        style={{ opacity: divider < 0.88 ? 1 : 0 }}
      >
        {afterYear}
      </div>

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-sm text-zinc-700">
          加载 Landsat 底图…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 px-4 text-center text-sm text-red-600">
          Landsat 加载失败：{error}
        </div>
      )}
    </div>
  );
}
