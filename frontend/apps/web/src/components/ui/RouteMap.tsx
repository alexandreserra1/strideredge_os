import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, ZoomControl, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { useTheme } from '../layout/ThemeProvider'

export type RoutePoint = { lat: number; lon: number; cadence: number }

// Semáforo de cadência — cores minimalistas (verde/âmbar/vermelho suaves)
function cadColor(c: number) {
  if (c >= 168) return '#34D399'
  if (c >= 160) return '#FBBF24'
  return '#F87171'
}

function FitBounds({ points }: { points: RoutePoint[] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(points.map(p => [p.lat, p.lon]) as [number, number][], { padding: [26, 26] })
    }
  }, [points, map])
  return null
}

const SAT_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

export default function RouteMap({ points }: { points: RoutePoint[] }) {
  const { theme } = useTheme()
  const [sat, setSat] = useState(false)

  const tiles = sat
    ? SAT_URL
    : theme === 'dark'
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'

  if (!points.length) return null
  const start = points[0]
  const end = points[points.length - 1]

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={[start.lat, start.lon]}
        zoom={14}
        scrollWheelZoom={false}
        doubleClickZoom={true}
        zoomControl={false}
        attributionControl={false}
        style={{ height: '100%', width: '100%', background: 'var(--surface-bg)' }}
      >
        <TileLayer key={tiles} url={tiles} />
        <ZoomControl position="bottomright" />
        {points.slice(0, -1).map((p, i) => (
          <Polyline
            key={i}
            positions={[[p.lat, p.lon], [points[i + 1].lat, points[i + 1].lon]]}
            pathOptions={{
              color: cadColor(p.cadence),
              weight: sat ? 4 : 3,         // um pouco mais grossa sobre satélite p/ contraste
              opacity: 0.95, lineCap: 'round', lineJoin: 'round',
            }}
          />
        ))}
        <CircleMarker center={[start.lat, start.lon]} radius={5}
          pathOptions={{ color: '#fff', weight: 2, fillColor: '#34D399', fillOpacity: 1 }} />
        <CircleMarker center={[end.lat, end.lon]} radius={5}
          pathOptions={{ color: '#fff', weight: 2, fillColor: '#F87171', fillOpacity: 1 }} />
        <FitBounds points={points} />
      </MapContainer>

      {/* toggle Mapa / Satélite */}
      <div className="absolute top-3 left-3 z-[1000] flex p-0.5 rounded-lg glass text-[11px] font-medium">
        {[['Mapa', false], ['Satélite', true]].map(([label, on]) => (
          <button
            key={label as string}
            onClick={() => setSat(on as boolean)}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              sat === on ? 'bg-brand text-brand-ink' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
