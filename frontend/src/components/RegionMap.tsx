"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  RISK_LEVEL_COLORS,
  type RegionsGeoJSON,
  type GridGeoJSON,
} from "@/lib/api";

interface NdviSummary {
  [regionId: number]: number;
}
interface RiskSummary {
  [regionId: number]: number;
}

export type MapLayerMode = "ndvi" | "risk" | "hotspot";

interface RegionMapProps {
  regions: RegionsGeoJSON | null;
  ndviSummary: NdviSummary;
  riskSummary?: RiskSummary;
  layerMode?: MapLayerMode;
  selectedRegionId: number | null;
  onSelectRegion: (id: number) => void;
  // When provided, overrides ndviSummary for the NDVI layer so the map reflects
  // a specific year instead of the all-time mean.
  ndviYearly?: Record<number, number>;
  // Pixel-grid NDVI overlay for the currently-selected region + year.
  hotspotGrid?: GridGeoJSON | null;
}

// Continuous sand → green ramp tuned to the actual annual-mean NDVI span
// observed in the sandy-land subregions (~0.28 at worst, ~0.40 at best). The
// 0.25–0.42 window stretches each year's small change into visible contrast
// when scrubbing the time slider.
function ndviToColor(ndvi: number): string {
  const lo = 0.25;
  const hi = 0.42;
  const t = Math.max(0, Math.min(1, (ndvi - lo) / (hi - lo)));
  const sand = [212, 165, 116]; // #d4a574
  const green = [46, 125, 50];  // #2e7d32
  const r = Math.round(sand[0] + (green[0] - sand[0]) * t);
  const g = Math.round(sand[1] + (green[1] - sand[1]) * t);
  const b = Math.round(sand[2] + (green[2] - sand[2]) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

function riskToColor(level: number): string {
  return RISK_LEVEL_COLORS[level] ?? "#a1a1aa";
}

function extendBoundsWithGeometry(
  bounds: maplibregl.LngLatBounds,
  geometry: { type: string; coordinates: unknown } | null
) {
  if (!geometry) return;
  const raw = geometry.coordinates as number[][][] | number[][][][];
  const rings: number[][][] =
    geometry.type === "MultiPolygon"
      ? (raw as number[][][][]).flat()
      : (raw as number[][][]);
  for (const c of rings.flat()) bounds.extend([c[0], c[1]]);
}

export default function RegionMap({
  regions,
  ndviSummary,
  riskSummary,
  layerMode = "ndvi",
  selectedRegionId,
  onSelectRegion,
  ndviYearly,
  hotspotGrid,
}: RegionMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupsRef = useRef<maplibregl.Popup[]>([]);
  const fittedRef = useRef(false);
  const onSelectRef = useRef(onSelectRegion);

  useEffect(() => {
    onSelectRef.current = onSelectRegion;
  }, [onSelectRegion]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "osm-tiles",
            type: "raster",
            source: "osm",
            minzoom: 0,
            maxzoom: 18,
          },
        ],
      },
      center: [115, 43],
      zoom: 5,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    // maplibre doesn't track container resize on its own — without this, the
    // fitBounds math uses a stale width after the dashboard switches between
    // overview (span 12) and single-region (span 6) layouts.
    const ro = new ResizeObserver(() => {
      map.resize();
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add/update region layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !regions || regions.features.length === 0) return;

    const addLayers = () => {
      const sandyLands = {
        type: "FeatureCollection" as const,
        features: regions.features
          .filter((f) => f.properties.level === "subregion")
          .map((f) => {
            const ndviVal =
              ndviYearly?.[f.properties.id] ?? ndviSummary[f.properties.id] ?? 0;
            const fill =
              layerMode === "risk"
                ? riskToColor(riskSummary?.[f.properties.id] ?? 0)
                : ndviToColor(ndviVal);
            return {
              ...f,
              properties: { ...f.properties, fillColor: fill },
            };
          }),
      };

      // Sandy land regions with NDVI coloring
      if (map.getSource("sandy-lands")) {
        (map.getSource("sandy-lands") as maplibregl.GeoJSONSource).setData(
          sandyLands as unknown as GeoJSON.FeatureCollection
        );
      } else {
        map.addSource("sandy-lands", {
          type: "geojson",
          data: sandyLands as unknown as GeoJSON.FeatureCollection,
        });

        map.addLayer({
          id: "sandy-fill",
          type: "fill",
          source: "sandy-lands",
          paint: {
            "fill-color": ["get", "fillColor"],
            "fill-opacity": 0.45,
          },
        });

        map.addLayer({
          id: "sandy-border",
          type: "line",
          source: "sandy-lands",
          paint: {
            "line-color": "#5d4037",
            "line-width": 1,
          },
        });

        // Click handler
        map.on("click", "sandy-fill", (e) => {
          const feature = e.features?.[0];
          if (feature?.properties?.id) {
            onSelectRef.current(feature.properties.id);
          }
        });

        map.on("mouseenter", "sandy-fill", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "sandy-fill", () => {
          map.getCanvas().style.cursor = "";
        });
      }

      // Clear stale popups before adding fresh labels
      for (const p of popupsRef.current) p.remove();
      popupsRef.current = [];

      // Labels for subregions
      for (const f of sandyLands.features) {
        if (!f.geometry) continue;
        // Support both Polygon and MultiPolygon — flatten all ring coordinates
        const raw = f.geometry.coordinates as unknown as number[][][] | number[][][][];
        const rings: number[][][] =
          (f.geometry as unknown as { type: string }).type === "MultiPolygon"
            ? (raw as number[][][][]).flat()
            : (raw as number[][][]);
        const pts = rings.flat();
        if (pts.length === 0) continue;
        const lngs = pts.map((c) => c[0]);
        const lats = pts.map((c) => c[1]);
        const center: [number, number] = [
          (Math.min(...lngs) + Math.max(...lngs)) / 2,
          (Math.min(...lats) + Math.max(...lats)) / 2,
        ];
        const popup = new maplibregl.Popup({
          closeOnClick: false,
          closeButton: false,
          className: "region-label",
        })
          .setLngLat(center)
          .setHTML(
            `<div style="font-weight:600;font-size:13px;color:#1a1a1a">${f.properties.name}</div>`
          )
          .addTo(map);
        popupsRef.current.push(popup);
      }
    };

    // rAF poll instead of `map.on("load", ...)`: the "load" event only fires
    // once on initial style load, so a handler attached after that point is
    // dead. `isStyleLoaded()` can also transiently return false right after a
    // sibling effect calls setData/addLayer, so we keep retrying until it's
    // true. Cancellation prevents effect re-runs from stacking polls.
    let cancelled = false;
    const tryAdd = () => {
      if (cancelled) return;
      if (map.isStyleLoaded()) {
        addLayers();
      } else {
        requestAnimationFrame(tryAdd);
      }
    };
    tryAdd();
    return () => {
      cancelled = true;
    };
  }, [regions, ndviSummary, riskSummary, layerMode, ndviYearly]);

  // Pixel-grid hotspot overlay + region-layer visibility. In hotspot mode the
  // grid is the authoritative boundary, so hide the broader sandy-land fill
  // and outline instead of stacking two competing shapes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const apply = () => {
      const hotspotActive = layerMode === "hotspot" && hotspotGrid != null;
      const gridFc = hotspotActive
        ? {
            type: "FeatureCollection" as const,
            features: hotspotGrid!.features.map((f) => ({
              ...f,
              properties: {
                ...f.properties,
                fillColor: ndviToColor(f.properties.ndvi),
              },
            })),
          }
        : { type: "FeatureCollection" as const, features: [] };

      if (map.getSource("hotspot-grid")) {
        (map.getSource("hotspot-grid") as maplibregl.GeoJSONSource).setData(
          gridFc as unknown as GeoJSON.FeatureCollection
        );
      } else {
        map.addSource("hotspot-grid", {
          type: "geojson",
          data: gridFc as unknown as GeoJSON.FeatureCollection,
        });
        map.addLayer({
          id: "hotspot-fill",
          type: "fill",
          source: "hotspot-grid",
          paint: {
            "fill-color": ["get", "fillColor"],
            "fill-opacity": 0.85,
          },
        });
        map.addLayer({
          id: "hotspot-border",
          type: "line",
          source: "hotspot-grid",
          paint: {
            "line-color": "rgba(0,0,0,0.08)",
            "line-width": 0.5,
          },
        });
      }

      // Belt-and-suspenders: hide the layers outright when not in hotspot
      // mode. setData with empty features should be enough, but toggling
      // visibility guarantees the pixel grid can't visually linger on top
      // of the polygon fill after a mode switch.
      if (map.getLayer("hotspot-fill")) {
        map.setLayoutProperty(
          "hotspot-fill",
          "visibility",
          hotspotActive ? "visible" : "none"
        );
        map.setLayoutProperty(
          "hotspot-border",
          "visibility",
          hotspotActive ? "visible" : "none"
        );
      }

      if (map.getLayer("sandy-fill")) {
        map.setLayoutProperty(
          "sandy-fill",
          "visibility",
          hotspotActive ? "none" : "visible"
        );
      }
      if (map.getLayer("sandy-border")) {
        map.setLayoutProperty(
          "sandy-border",
          "visibility",
          hotspotActive ? "none" : "visible"
        );
      }

      // Single source of truth for sandy-fill opacity when the region layer is
      // visible; hotspot mode hides it entirely so the grid edge defines extent.
      if (map.getLayer("sandy-fill")) {
        map.setPaintProperty(
          "sandy-fill",
          "fill-opacity",
          [
            "case",
            ["==", ["get", "id"], selectedRegionId ?? -1],
            0.55,
            0.35,
          ]
        );
      }
    };

    // Same "load fires only once" trap as the sandy-fill effect above — and
    // this one is the actual cause of the "switch out of hotspot does nothing"
    // bug, because after the sandy-fill setData just above, `isStyleLoaded()`
    // transiently returns false here and the `map.on("load", apply)` callback
    // was never firing again, leaving hotspot visibility stuck on "visible".
    let cancelled = false;
    const tryApply = () => {
      if (cancelled) return;
      if (map.isStyleLoaded()) {
        apply();
      } else {
        requestAnimationFrame(tryApply);
      }
    };
    tryApply();
    return () => {
      cancelled = true;
    };
  }, [hotspotGrid, layerMode, selectedRegionId]);

  // Border width still responds independently to selection so the selected
  // outline stays crisp regardless of layer mode.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("sandy-border")) return;
    map.setPaintProperty("sandy-border", "line-width", [
      "case",
      ["==", ["get", "id"], selectedRegionId ?? -1],
      2,
      1,
    ]);
  }, [selectedRegionId]);

  // Fit the map to the focus target: a specific sandy land when one is
  // selected, all subregions when the user is in the "两大沙地" overview.
  // Deferred with rAF so the grid layout (span 6 vs. span 12) has settled and
  // the container width reflects the new viewport before fitBounds runs.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !regions) return;

    const hotspotActive =
      layerMode === "hotspot" && hotspotGrid != null && hotspotGrid.features.length > 0;
    if (hotspotActive) {
      const bounds = new maplibregl.LngLatBounds();
      for (const f of hotspotGrid.features) {
        extendBoundsWithGeometry(bounds, f.geometry);
      }
      if (!bounds.isEmpty()) {
        const animated = fittedRef.current;
        fittedRef.current = true;
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            map.resize();
            map.fitBounds(bounds, {
              padding: 56,
              duration: animated ? 700 : 0,
            });
          })
        );
        return;
      }
    }

    const subs = regions.features.filter(
      (f) => f.properties.level === "subregion"
    );
    if (subs.length === 0) return;
    const target =
      selectedRegionId != null
        ? subs.filter((f) => f.properties.id === selectedRegionId)
        : subs;
    if (target.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    for (const f of target) {
      extendBoundsWithGeometry(bounds, f.geometry);
    }
    if (bounds.isEmpty()) return;

    const animated = fittedRef.current;
    fittedRef.current = true;

    const doFit = () => {
      map.resize();
      map.fitBounds(bounds, {
        // Larger padding on single-region view gives breathing room around the
        // sandy-land polygon so it doesn't crowd the edges of the map pane.
        padding: selectedRegionId != null ? 80 : 40,
        duration: animated ? 700 : 0,
      });
    };
    // Two rAFs so layout + style are both settled before we compute the new
    // viewport. Running unconditionally (instead of gating on isStyleLoaded) is
    // deliberate: after the first fit, re-fits triggered by a tab switch
    // sometimes see `isStyleLoaded()` transiently false, and `map.once("load",
    // ...)` never fires again after the initial load — so the re-fit would be
    // dropped silently.
    requestAnimationFrame(() => requestAnimationFrame(doFit));
  }, [regions, selectedRegionId, layerMode, hotspotGrid]);

  return (
    <div ref={containerRef} className="h-full w-full rounded-lg overflow-hidden" />
  );
}
