import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { Link } from "react-router-dom";
import { brl, resolveMediaUrl as resolveUrl } from "@/lib/api";
import { Star, ShieldCheck } from "lucide-react";

// Custom red pin
function makeIcon(label = "", verified = false) {
  return L.divIcon({
    html: `<div class="prime-marker ${verified ? "verified" : ""}">${verified ? "" : label}</div>`,
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

export default function MapView({ items, center = [-22.9711, -43.1822], zoom = 12 }) {
  return (
    <div data-testid="map-view" className="rounded-2xl overflow-hidden border border-zinc-900 h-[520px] shadow-2xl shadow-red-950/20">
      <MapContainer center={center} zoom={zoom} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {items.map((m) => (
          <Marker
            key={m.id}
            position={[m.lat, m.lng]}
            icon={makeIcon("", m.verified)}
            data-testid={`map-marker-${m.id}`}
          >
            <Popup minWidth={220}>
              <div className="space-y-2">
                <Link to={`/massagista/${m.id}`} className="flex items-center gap-3">
                  <img src={resolveUrl(m.main_image)} alt={m.name} className="h-12 w-12 rounded-lg object-cover" />
                  <div className="min-w-0">
                    <div className="font-display font-semibold text-zinc-50 text-sm leading-tight flex items-center gap-1">
                      {m.name}
                      {m.verified && <ShieldCheck className="h-3.5 w-3.5 text-red-500" />}
                    </div>
                    <div className="text-[11px] text-zinc-400">{m.bairro}</div>
                  </div>
                </Link>
                <div className="flex items-center justify-between text-xs text-zinc-300">
                  <div className="flex items-center gap-1">
                    <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                    {m.rating?.toFixed(1)} <span className="text-zinc-500">({m.reviews})</span>
                  </div>
                  <div className="text-red-500 font-semibold">{brl(m.price_60)}</div>
                </div>
                <Link
                  to={`/massagista/${m.id}`}
                  className="block text-center w-full rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-medium py-1.5"
                >
                  Ver perfil
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
