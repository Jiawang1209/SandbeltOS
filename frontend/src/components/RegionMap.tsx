"use client";

import { useEffect, useRef, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { RegionsGeoJSON } from "@/lib/api";

interface NdviSummary {
  [regionId: number]: number; // average NDVI
}

interface RegionMapProps {
  regions: RegionsGeoJSON | null;
  ndviSummary: NdviSummary;
  selectedRegionId: number | null;
  onSelectRegion: (id: number) => void;
}

function ndviToColor(ndvi: number): string {
  // 0.0-0.1: sandy brown, 0.1-0.2: yellow-green, 0.2-0.3: light green, 0.3+: green
  if (ndvi < 0.08) return "#d4a574";
  if (ndvi < 0.15) return "#c4b550";
  if (ndvi < 0.22) return "#7cb342";
  return "#2e7d32";
}

export default function RegionMap({
  regions,
  ndviSummary,
  selectedRegionId,
  onSelectRegion,
}: RegionMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onSelectRef = useRef(onSelectRegion);
  onSelectRef.current = onSelectRegion;

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
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add/update region layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !regions || regions.features.length === 0) return;

    const addLayers = () => {
      // Separate the shelterbelt boundary from sandy land subregions
      const shelterbelt = {
        type: "FeatureCollection" as const,
        features: regions.features.filter(
          (f) => f.properties.level === "region"
        ),
      };
      const sandyLands = {
        type: "FeatureCollection" as const,
        features: regions.features
          .filter((f) => f.properties.level === "subregion")
          .map((f) => ({
            ...f,
            properties: {
              ...f.properties,
              fillColor: ndviToColor(ndviSummary[f.properties.id] ?? 0),
            },
          })),
      };

      // Three-North Shelterbelt boundary
      if (!map.getSource("shelterbelt")) {
        map.addSource("shelterbelt", {
          type: "geojson",
          data: shelterbelt as unknown as GeoJSON.FeatureCollection,
        });
        map.addLayer({
          id: "shelterbelt-fill",
          type: "fill",
          source: "shelterbelt",
          paint: {
            "fill-color": "#a3d9a5",
            "fill-opacity": 0.06,
          },
        });
        map.addLayer({
          id: "shelterbelt-border",
          type: "line",
          source: "shelterbelt",
          paint: {
            "line-color": "#388e3c",
            "line-width": 2,
            "line-dasharray": [4, 3],
          },
        });
      }

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
            "line-width": 2,
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

      // Labels for subregions
      for (const f of sandyLands.features) {
        if (!f.geometry) continue;
        const coords = f.geometry.coordinates[0];
        const lngs = coords.map((c) => c[0]);
        const lats = coords.map((c) => c[1]);
        const center: [number, number] = [
          (Math.min(...lngs) + Math.max(...lngs)) / 2,
          (Math.min(...lats) + Math.max(...lats)) / 2,
        ];
        const ndvi = ndviSummary[f.properties.id] ?? 0;

        new maplibregl.Popup({
          closeOnClick: false,
          closeButton: false,
          className: "region-label",
        })
          .setLngLat(center)
          .setHTML(
            `<div style="font-weight:600;font-size:12px;color:#1a1a1a">${f.properties.name}</div>
             <div style="font-size:11px;color:#555">NDVI: ${ndvi.toFixed(3)}</div>
             <div style="font-size:10px;color:#888">${f.properties.area_km2?.toLocaleString()} km²</div>`
          )
          .addTo(map);
      }
    };

    if (map.isStyleLoaded()) {
      addLayers();
    } else {
      map.on("load", addLayers);
    }
  }, [regions, ndviSummary]);

  // Highlight selected region
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("sandy-border")) return;

    map.setPaintProperty("sandy-border", "line-width", [
      "case",
      ["==", ["get", "id"], selectedRegionId ?? -1],
      4,
      2,
    ]);
    map.setPaintProperty("sandy-fill", "fill-opacity", [
      "case",
      ["==", ["get", "id"], selectedRegionId ?? -1],
      0.6,
      0.35,
    ]);
  }, [selectedRegionId]);

  return (
    <div ref={containerRef} className="h-full w-full rounded-lg overflow-hidden" />
  );
}
