"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

/**
 * PSK map placeholder — Sprint 0 scaffold.
 *
 * Renders an OSM-based MapLibre map centred on the Prešov region.
 * Sprint 1 will add GeoJSON layers: municipalities, districts (obvody),
 *   schools, MRK zones, bus stops.
 * Sprint 2 will colour districts by compliance verdict (semafor).
 *
 * Keyboard: MapLibre's default keyboard handlers are active (arrows, +/-).
 * Full WCAG keyboard/focus management is wired in Sprint 4.
 */

// PSK approximate centre
const PSK_CENTER: [number, number] = [21.25, 49.0];
const PSK_ZOOM = 8;

export function MapClient() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution:
              '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: "osm-tiles",
            type: "raster",
            source: "osm",
          },
        ],
      },
      center: PSK_CENTER,
      zoom: PSK_ZOOM,
    });

    // Navigation controls (keyboard + mouse)
    mapRef.current.addControl(
      new maplibregl.NavigationControl({ visualizePitch: false }),
      "top-right"
    );

    // Attribution
    mapRef.current.addControl(new maplibregl.AttributionControl(), "bottom-right");

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      role="application"
      aria-label="Interaktívna mapa Prešovského samosprávneho kraja"
      // Keyboard users: use arrow keys to pan, +/- to zoom
      tabIndex={0}
    />
  );
}
