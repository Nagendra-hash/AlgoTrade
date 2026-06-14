"use client";
// Interactive World Map — react-simple-maps with regional sentiment heat overlays.
// Path: frontend/src/app/geo-monitor/WorldMap.tsx
import { useState, useCallback, memo, useRef, useEffect } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  Marker,
} from "react-simple-maps";
import { cn } from "@/lib/utils";

// ── Constants ─────────────────────────────────────────────────
const TOPO_JSON_URL =
  "https://unpkg.com/world-atlas@2.0.2/countries-110m.json";

// Colors for the legend scale
const SENTIMENT_COLORS = [
  "#dc2626", // -100: bearish (red)
  "#ef4444",
  "#f87171",
  "#fca5a5",
  "#9ca3af", // 0: neutral (gray)
  "#86efac",
  "#4ade80",
  "#22c55e",
  "#16a34a", // +100: bullish (green)
];

function sentimentToColor(score: number): string {
  // score is -1 to 1, map to index 0..8
  const idx = Math.round(((score + 1) / 2) * 8);
  return SENTIMENT_COLORS[Math.min(Math.max(idx, 0), 8)];
}

// Map our custom geopolitical regions to ISO 3166-1 numeric codes
// (world-atlas v2 TopoJSON uses numeric IDs, not alpha-3)
const REGION_COUNTRY_MAP: Record<string, string[]> = {
  "Indo-Pacific": [
    "156", "158", "392", "356", "036", "360", "458", "702", "764", "704",
    "608", "410", "408", "524", "050", "144", "104", "116", "418", "554",
    "598", "496", "096", "626", "242", "840",
  ],
  "Middle East": [
    "364", "376", "682", "784", "368", "760", "887", "634", "414", "512",
    "048", "400", "422", "275", "004", "792",
  ],
  "Eastern Europe": [
    "804", "643", "112", "616", "203", "703", "348", "642", "100", "498",
    "233", "428", "440", "268", "051", "031",
  ],
  Africa: [
    "710", "566", "818", "404", "231", "288", "834", "180", "024", "729",
    "012", "504", "788", "434", "686", "384", "120", "800", "716", "508",
    "894", "706", "450", "072", "516", "466", "562", "148", "854", "204",
    "646", "108", "728", "454", "768", "694", "430", "324", "478", "232",
    "266", "178", "140", "226", "262", "174", "748", "426", "480", "690",
    "678", "132", "270", "624",
  ],
  "Latin America": [
    "076", "032", "484", "170", "152", "604", "862", "218", "068", "600",
    "858", "320", "340", "222", "558", "188", "591", "192", "214", "630",
    "332", "388", "780", "044", "084", "328", "740", "028", "052", "662",
    "670", "308", "212", "659",
  ],
  Arctic: [
    "124", "304", "352", "578", "752", "246",
  ],
  Europe: [
    "250", "276", "826", "380", "724", "620", "528", "056", "756", "040",
    "208", "372", "300", "191", "070", "705", "807", "008", "499", "688",
    "442", "470", "196", "492", "438", "020", "674", "336",
  ],
};

// Build reverse map: country code → region name
const COUNTRY_TO_REGION: Record<string, string> = {};
for (const [region, countries] of Object.entries(REGION_COUNTRY_MAP)) {
  for (const code of countries) {
    COUNTRY_TO_REGION[code] = region;
  }
}

// Marker positions for key geopolitical hotspots
const HOTSPOT_MARKERS = [
  { name: "Taiwan Strait",      coords: [120.5, 24.5] as [number, number], region: "Indo-Pacific" },
  { name: "South China Sea",    coords: [114.0, 10.0] as [number, number], region: "Indo-Pacific" },
  { name: "Ukraine Conflict",   coords: [31.0, 48.5] as [number, number],  region: "Eastern Europe" },
  { name: "Persian Gulf",       coords: [52.0, 26.5] as [number, number],  region: "Middle East" },
  { name: "Red Sea",            coords: [42.0, 20.0] as [number, number],  region: "Middle East" },
  { name: "Horn of Africa",     coords: [47.0, 5.0] as [number, number],   region: "Africa" },
  { name: "Sahel Region",       coords: [2.0, 15.0] as [number, number],   region: "Africa" },
  { name: "Amazon Basin",       coords: [-60.0, -5.0] as [number, number], region: "Latin America" },
  { name: "Arctic Passage",     coords: [0.0, 80.0] as [number, number],   region: "Arctic" },
  { name: "Korean Peninsula",   coords: [128.0, 38.5] as [number, number], region: "Indo-Pacific" },
];

// ── Types ─────────────────────────────────────────────────────
interface GeoRegion {
  region: string;
  article_count: number;
  avg_sentiment: number;
  metadata: {
    color: string;
    border: string;
    bg: string;
    text: string;
    icon: string;
    description: string;
  };
}

interface TooltipData {
  region: string;
  countryName: string;
  articleCount: number;
  sentiment: number;
  description: string;
}

// ── Component ────────────────────────────────────────────────
interface WorldMapProps {
  regions: GeoRegion[];
  selectedRegion: string | null;
  onSelectRegion: (region: string | null) => void;
}

const WorldMap = memo(function WorldMap({
  regions,
  selectedRegion,
  onSelectRegion,
}: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // Track container width for responsive scaling
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let latestWidth = 0;
    let rafId: number | null = null;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        latestWidth = entry.contentRect.width;
      }
      if (rafId !== null) return; // coalesce to animation frame
      rafId = requestAnimationFrame(() => {
        rafId = null;
        setContainerWidth(latestWidth);
      });
    });
    observer.observe(el);
    setContainerWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  // Dynamic scale: reference is 147 at 960px wide, scales linearly
  const dynamicScale = containerWidth > 0
    ? Math.max(containerWidth * 0.153, 80)
    : 147;

  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [hoveredCountry, setHoveredCountry] = useState<string | null>(null);

  const regionMap = new Map(regions.map((r) => [r.region, r]));

  const getCountryFill = useCallback(
    (countryCode: string, defaultFill: string): string => {
      const region = COUNTRY_TO_REGION[countryCode];
      if (!region) return defaultFill;
      const rData = regionMap.get(region);
      if (!rData || rData.article_count === 0) return "#374151"; // dark gray for inactive
      if (selectedRegion && selectedRegion !== region) return "#374151"; // dim unselected
      return sentimentToColor(rData.avg_sentiment);
    },
    [regionMap, selectedRegion]
  );

  const getCountryOpacity = useCallback(
    (countryCode: string): number => {
      const region = COUNTRY_TO_REGION[countryCode];
      if (!region) return 0.15;
      const rData = regionMap.get(region);
      if (!rData || rData.article_count === 0) return 0.15;
      // Opacity scales with article intensity (0.3 to 1.0)
      const maxArticles = Math.max(...regions.map((r) => r.article_count), 1);
      return 0.3 + (rData.article_count / maxArticles) * 0.7;
    },
    [regions, regionMap]
  );

  const handleCountryClick = useCallback(
    (countryCode: string) => {
      const region = COUNTRY_TO_REGION[countryCode];
      if (region && regionMap.has(region)) {
        onSelectRegion(selectedRegion === region ? null : region);
      }
    },
    [onSelectRegion, regionMap, selectedRegion]
  );

  const getCountryName = useCallback((geo: any) => {
    return geo.properties?.name || geo.properties?.ADMIN || "";
  }, []);

  const getCountryCode = useCallback((geo: any) => {
    // world-atlas v2 TopoJSON: id is the numeric ISO 3166-1 code (e.g. "156")
    return String(geo.id || "");
  }, []);

  // Show tooltip only for known regions
  const handleHover = useCallback(
    (geo: any) => {
      const code = getCountryCode(geo);
      const region = COUNTRY_TO_REGION[code];
      if (!region) return;
      const rData = regionMap.get(region);
      if (!rData) return;
      setTooltip({
        region,
        countryName: getCountryName(geo),
        articleCount: rData.article_count,
        sentiment: rData.avg_sentiment,
        description: rData.metadata.description,
      });
      setHoveredCountry(code);
    },
    [regionMap, getCountryCode, getCountryName]
  );

  const handleHoverEnd = useCallback(() => {
    setTooltip(null);
    setHoveredCountry(null);
  }, []);

  return (
    <div className="relative" ref={containerRef}>
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          scale: dynamicScale,
          center: [10, 15],
        }}
        style={{ width: "100%", height: "auto" }}
      >
        <Geographies geography={TOPO_JSON_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const code = getCountryCode(geo);
              const fill = getCountryFill(code, "#1f2937");
              const opacity = getCountryOpacity(code);
              const isHovered = hoveredCountry === code;
              const region = COUNTRY_TO_REGION[code];
              const rData = region ? regionMap.get(region) : null;

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onClick={() => handleCountryClick(code)}
                  onMouseEnter={() => handleHover(geo)}
                  onMouseLeave={handleHoverEnd}
                  style={{
                    default: {
                      fill,
                      fillOpacity: opacity,
                      stroke: isHovered ? "#22d3ee" : "#374151",
                      strokeWidth: isHovered ? 1.5 : 0.4,
                      outline: "none",
                      transition: "all 0.15s ease",
                      cursor: rData ? "pointer" : "default",
                    },
                    hover: {
                      fill,
                      fillOpacity: Math.min(opacity + 0.25, 1),
                      stroke: "#22d3ee",
                      strokeWidth: 1.5,
                      outline: "none",
                    },
                    pressed: {
                      fill,
                      fillOpacity: Math.min(opacity + 0.35, 1),
                      stroke: "#06b6d4",
                      strokeWidth: 2,
                      outline: "none",
                    },
                  }}
                />
              );
            })
          }
        </Geographies>

        {/* Hotspot markers */}
        {HOTSPOT_MARKERS.map((marker) => {
          const rData = regionMap.get(marker.region);
          if (!rData || rData.article_count === 0) return null;
          const isActive = !selectedRegion || selectedRegion === marker.region;
          if (!isActive) return null;
          const color = sentimentToColor(rData.avg_sentiment);
          return (
            <Marker key={marker.name} coordinates={marker.coords}>
              <circle
                r={4 + rData.article_count * 0.3}
                fill={color}
                fillOpacity={0.5}
                stroke={color}
                strokeWidth={1.5}
                strokeOpacity={0.8}
                className="animate-pulse"
              />
              <circle
                r={3}
                fill={color}
                fillOpacity={0.9}
                stroke="#111827"
                strokeWidth={0.5}
              />
            </Marker>
          );
        })}
      </ComposableMap>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-50 bg-gray-900/95 border border-gray-700 rounded-xl p-3 shadow-xl backdrop-blur-sm"
          style={{
            left: "50%",
            bottom: "100%",
            transform: "translateX(-50%)",
            marginBottom: "8px",
            minWidth: "200px",
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs">{regionMap.get(tooltip.region)?.metadata.icon}</span>
            <span className="text-white text-xs font-bold">{tooltip.region}</span>
            <span className="text-gray-500 text-[10px]">· {tooltip.countryName}</span>
          </div>
          <p className="text-gray-400 text-[10px] mb-1.5">{tooltip.description}</p>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="text-gray-500">
              <span className="text-white font-semibold">{tooltip.articleCount}</span> articles
            </span>
            <span
              className={cn(
                "font-semibold",
                tooltip.sentiment > 0.05
                  ? "text-green-400"
                  : tooltip.sentiment < -0.05
                    ? "text-red-400"
                    : "text-gray-400"
              )}
            >
              {(tooltip.sentiment * 100).toFixed(0)} sentiment
            </span>
          </div>
        </div>
      )}

      {/* Legend bar */}
      <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-800">
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-gray-500">Sentiment</span>
          <span className="text-[9px] text-red-400">Bearish</span>
        </div>
        <div className="flex h-2 rounded-full overflow-hidden flex-1 max-w-[200px]">
          {SENTIMENT_COLORS.map((color, i) => (
            <div key={i} className="flex-1" style={{ backgroundColor: color }} />
          ))}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-green-400">Bullish</span>
        </div>
        <div className="w-px h-4 bg-gray-700" />
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-gray-700" />
          <span className="text-[9px] text-gray-500">No data</span>
        </div>
      </div>

      {/* Hotspot legend */}
      <div className="mt-2 pt-2 border-t border-gray-800/50">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[9px] text-gray-500 font-medium uppercase tracking-wider">Hotspots</span>
          <span className="text-[8px] text-gray-600">({HOTSPOT_MARKERS.length} active)</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-1">
          {HOTSPOT_MARKERS.map((marker) => {
            const rData = regionMap.get(marker.region);
            const dotColor = rData && rData.article_count > 0
              ? sentimentToColor(rData.avg_sentiment)
              : "#4b5563"; // gray-600 for inactive
            const isDimmed = selectedRegion && selectedRegion !== marker.region;
            return (
              <div
                key={marker.name}
                className={cn(
                  "flex items-center gap-1.5 px-1.5 py-1 rounded transition-all",
                  isDimmed ? "opacity-30" : "opacity-80 hover:opacity-100 hover:bg-gray-800/40"
                )}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: dotColor }}
                />
                <span className="text-[9px] text-gray-400 truncate leading-none">{marker.name}</span>
                <span className="text-[7px] text-gray-600 shrink-0">{marker.region}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});

export default WorldMap;
