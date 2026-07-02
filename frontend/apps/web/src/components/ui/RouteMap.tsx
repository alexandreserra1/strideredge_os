import { useEffect } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, useMap } from 'react-leaflet'
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

export default function RouteMap({ points }: { points: RoutePoint[] }) {
  const { theme } = useTheme()
  const tiles = theme === 'dark'
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'

  if (!points.length) return null
  const start = points[0]
  const end = points[points.length - 1]

  return (
    <MapContainer
      center={[start.lat, start.lon]}
      zoom={14}
      scrollWheelZoom={false}
      zoomControl={false}
      attributionControl={false}
      style={{ height: '100%', width: '100%', background: 'var(--surface-bg)' }}
    >
      <TileLayer key={tiles} url={tiles} />
      {points.slice(0, -1).map((p, i) => (
        <Polyline
          key={i}
          positions={[[p.lat, p.lon], [points[i + 1].lat, points[i + 1].lon]]}
          pathOptions={{ color: cadColor(p.cadence), weight: 3, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}
        />
      ))}
      <CircleMarker center={[start.lat, start.lon]} radius={5}
        pathOptions={{ color: '#0B0D12', weight: 2, fillColor: '#34D399', fillOpacity: 1 }} />
      <CircleMarker center={[end.lat, end.lon]} radius={5}
        pathOptions={{ color: '#0B0D12', weight: 2, fillColor: '#F87171', fillOpacity: 1 }} />
      <FitBounds points={points} />
    </MapContainer>
  )
}
