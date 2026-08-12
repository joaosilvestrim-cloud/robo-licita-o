"use client";
import { useEffect, useState, useCallback } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
  Marker,
} from "react-simple-maps";

const GEO_URL =
  "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson";

const CENTROIDS: Record<string, [number, number]> = {
  AC: [-70.5,  -9.0], AL: [-36.6,  -9.5], AM: [-64.6,  -4.0],
  AP: [-51.9,   1.4], BA: [-41.7, -12.9], CE: [-39.5,  -5.5],
  DF: [-47.9, -15.8], ES: [-40.3, -19.6], GO: [-49.3, -16.0],
  MA: [-44.3,  -4.9], MG: [-44.7, -18.5], MS: [-54.8, -20.5],
  MT: [-56.1, -12.6], PA: [-52.2,  -3.4], PB: [-36.8,  -7.1],
  PE: [-37.5,  -8.4], PI: [-42.8,  -7.7], PR: [-51.6, -24.7],
  RJ: [-42.7, -22.2], RN: [-36.5,  -5.8], RO: [-62.8, -11.0],
  RR: [-61.4,   2.0], RS: [-53.0, -30.0], SC: [-50.5, -27.3],
  SE: [-37.4, -10.6], SP: [-48.5, -22.2], TO: [-48.3, -10.2],
};

// Gradiente azul → laranja → vermelho
const HEAT_STOPS: [number, [number, number, number]][] = [
  [0.00, [219, 234, 254]],
  [0.25, [ 96, 165, 250]],
  [0.55, [251, 146,  60]],
  [1.00, [220,  38,  38]],
];
function lerp(a: number, b: number, t: number) { return Math.round(a + (b - a) * t); }
function heatColor(count: number, max: number): string {
  if (max === 0 || count === 0) return "#dbeafe";
  const t = Math.min(count / max, 1);
  let i = 0;
  while (i < HEAT_STOPS.length - 2 && t > HEAT_STOPS[i + 1][0]) i++;
  const [t0, c0] = HEAT_STOPS[i];
  const [t1, c1] = HEAT_STOPS[i + 1];
  const u = (t - t0) / (t1 - t0);
  return `rgb(${lerp(c0[0],c1[0],u)},${lerp(c0[1],c1[1],u)},${lerp(c0[2],c1[2],u)})`;
}

type StatStat  = { state: string; count: number; total_value: number };
type CityPoint = { city_code: string; city: string; lat: number; lng: number; count: number; total_value: number };

interface Props {
  token: string;
  selectedState: string | null;
  selectedCity: string | null;
  onStateSelect: (s: string | null) => void;
  onCitySelect:  (city: string | null) => void;
}

const BRAZIL_POS = { coordinates: [-54, -15] as [number, number], zoom: 1 };

export default function BrazilMap({ token, selectedState, selectedCity, onStateSelect, onCitySelect }: Props) {
  const [stateStats,  setStateStats]  = useState<StatStat[]>([]);
  const [cityPoints,  setCityPoints]  = useState<CityPoint[]>([]);
  const [cityLoading, setCityLoading] = useState(false);
  const [position,    setPosition]    = useState(BRAZIL_POS);
  const [tooltip,     setTooltip]     = useState<{ x: number; y: number; text: string } | null>(null);
  const [loading,     setLoading]     = useState(true);

  // Busca stats de estados
  useEffect(() => {
    const api = process.env.NEXT_PUBLIC_API_URL ?? "";
    fetch(`${api}/api/bids/geo`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setStateStats(d.states ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  // Quando estado selecionado → busca dados por cidade
  useEffect(() => {
    if (!selectedState) {
      setCityPoints([]);
      return;
    }
    const api = process.env.NEXT_PUBLIC_API_URL ?? "";
    setCityLoading(true);
    fetch(`${api}/api/bids/geo/cities?state=${selectedState}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => { setCityPoints(d.cities ?? []); setCityLoading(false); })
      .catch(() => setCityLoading(false));
  }, [selectedState, token]);

  // Sincroniza posição do mapa com estado selecionado
  useEffect(() => {
    if (!selectedState) {
      setPosition(BRAZIL_POS);
    } else if (CENTROIDS[selectedState]) {
      setPosition({ coordinates: CENTROIDS[selectedState], zoom: 4.5 });
    }
  }, [selectedState]);

  const stateMap  = Object.fromEntries(stateStats.map(s => [s.state, s]));
  const maxCount  = Math.max(...stateStats.map(s => s.count), 1);
  const maxCityCount = Math.max(...cityPoints.map(c => c.count), 1);
  const maxCityVal   = Math.max(...cityPoints.map(c => c.total_value), 1);

  const handleStateClick = useCallback((code: string) => {
    if (selectedState === code) {
      onStateSelect(null);
      onCitySelect(null);
    } else {
      onStateSelect(code);
      onCitySelect(null);
    }
  }, [selectedState, onStateSelect, onCitySelect]);

  function fmtM(v: number) {
    if (v >= 1e9) return `R$${(v/1e9).toFixed(1)}B`;
    if (v >= 1e6) return `R$${(v/1e6).toFixed(1)}M`;
    if (v >= 1e3) return `R$${(v/1e3).toFixed(0)}K`;
    return `R$${v.toFixed(0)}`;
  }

  return (
    <div className="flex flex-col h-full bg-white border-r border-slate-200">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 shrink-0">
        <h2 className="font-semibold text-slate-800 text-sm">Mapa de Calor</h2>
        <p className="text-[11px] text-slate-400 mt-0.5">
          {selectedState
            ? cityLoading
              ? `Carregando cidades de ${selectedState}…`
              : `${selectedState} — ${cityPoints.length} cidades com licitações · clique novamente para voltar`
            : "Clique em um estado para ver cidades"}
        </p>
      </div>

      {/* Map */}
      <div className="flex-1 relative overflow-hidden">
        {(loading || cityLoading) && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
            <span className="w-6 h-6 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
          </div>
        )}

        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ scale: 750, center: [-54, -15] }}
          style={{ width: "100%", height: "100%" }}
        >
          <ZoomableGroup
            zoom={position.zoom}
            center={position.coordinates}
            onMoveEnd={({ zoom, coordinates }) =>
              setPosition({ zoom, coordinates: coordinates as [number, number] })
            }
          >
            {/* ── Estados ── */}
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map(geo => {
                  const code: string = geo.properties.sigla ?? "";
                  const stat = stateMap[code];
                  const count = stat?.count ?? 0;
                  const isSelected = selectedState === code;

                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      onClick={() => handleStateClick(code)}
                      onMouseEnter={evt => {
                        const svg = (evt.target as SVGElement).closest("svg");
                        if (!svg) return;
                        const rect = svg.getBoundingClientRect();
                        setTooltip({
                          x: evt.clientX - rect.left,
                          y: evt.clientY - rect.top,
                          text: stat
                            ? `${code} — ${count} licitações · ${fmtM(stat.total_value)}`
                            : `${code} — sem licitações`,
                        });
                      }}
                      onMouseLeave={() => setTooltip(null)}
                      style={{
                        default: {
                          fill: isSelected
                            ? "#1e3a8a"
                            : heatColor(count, maxCount),
                          stroke: "#fff",
                          strokeWidth: 0.4,
                          outline: "none",
                          cursor: "pointer",
                          transition: "fill 0.2s",
                          opacity: selectedState && !isSelected ? 0.45 : 1,
                        },
                        hover: {
                          fill: isSelected ? "#1e40af" : "#93c5fd",
                          stroke: "#fff",
                          strokeWidth: 0.6,
                          outline: "none",
                          cursor: "pointer",
                          opacity: 1,
                        },
                        pressed: { fill: "#1e40af", outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>

            {/* ── Círculos de estado (nível Brasil) ── */}
            {!selectedState && stateStats.filter(s => CENTROIDS[s.state]).map(s => {
              const r = (3 + (s.total_value / Math.max(...stateStats.map(x => x.total_value), 1)) * 14) / position.zoom;
              return (
                <Marker key={s.state} coordinates={CENTROIDS[s.state]}>
                  <circle
                    r={r}
                    fill="rgba(255,255,255,0.2)"
                    stroke="rgba(255,255,255,0.6)"
                    strokeWidth={0.5 / position.zoom}
                    style={{ pointerEvents: "none" }}
                  />
                </Marker>
              );
            })}

            {/* ── Círculos de cidade (nível estado) ── */}
            {selectedState && !cityLoading && cityPoints.map(city => {
              const baseR   = 3 + (city.count / maxCityCount) * 16;
              const r       = baseR / position.zoom;
              const fill    = heatColor(city.count, maxCityCount);
              const isSelCity = selectedCity === city.city;

              return (
                <Marker key={city.city_code} coordinates={[city.lng, city.lat]}>
                  <circle
                    r={r}
                    fill={isSelCity ? "#1d4ed8" : fill}
                    stroke={isSelCity ? "#fff" : "rgba(255,255,255,0.8)"}
                    strokeWidth={0.8 / position.zoom}
                    style={{ cursor: "pointer" }}
                    onClick={() => onCitySelect(isSelCity ? null : city.city)}
                    onMouseEnter={evt => {
                      const svg = (evt.target as SVGElement).closest("svg");
                      if (!svg) return;
                      const rect = svg.getBoundingClientRect();
                      setTooltip({
                        x: evt.clientX - rect.left,
                        y: evt.clientY - rect.top,
                        text: `${city.city} — ${city.count} licitações · ${fmtM(city.total_value)}`,
                      });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                </Marker>
              );
            })}
          </ZoomableGroup>
        </ComposableMap>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute z-20 pointer-events-none bg-slate-900 text-white text-xs px-2.5 py-1.5 rounded-lg shadow-lg whitespace-nowrap"
            style={{ left: tooltip.x + 10, top: tooltip.y - 36 }}
          >
            {tooltip.text}
          </div>
        )}
      </div>

      {/* Legenda */}
      <div className="px-4 py-3 border-t border-slate-100 shrink-0 space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>Poucas</span>
          <span className="font-medium text-slate-500">
            {selectedState ? "Licitações por cidade" : "Licitações por estado"}
          </span>
          <span>Muitas</span>
        </div>
        <div className="h-2 rounded-full bg-gradient-to-r from-[#dbeafe] via-[#fb923c] to-[#dc2626]" />

        {/* Top cidades */}
        {selectedState && cityPoints.length > 0 && (
          <div className="mt-2 space-y-1 max-h-28 overflow-y-auto">
            {cityPoints.slice(0, 6).map(c => (
              <button
                key={c.city_code}
                onClick={() => onCitySelect(selectedCity === c.city ? null : c.city)}
                className={`w-full flex items-center justify-between text-[11px] px-2 py-1 rounded-lg transition ${
                  selectedCity === c.city
                    ? "bg-proc-100 text-proc-800 font-semibold"
                    : "hover:bg-slate-50 text-slate-600"
                }`}
              >
                <span className="truncate">{c.city}</span>
                <span className="shrink-0 ml-2 font-medium">{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {(selectedState || selectedCity) && (
          <button
            onClick={() => { onStateSelect(null); onCitySelect(null); }}
            className="w-full text-xs text-proc-600 hover:text-proc-800 font-medium py-1 px-2 bg-proc-50 hover:bg-proc-100 rounded-lg transition"
          >
            Limpar filtros ({[selectedState, selectedCity].filter(Boolean).join(" › ")})
          </button>
        )}
      </div>
    </div>
  );
}
