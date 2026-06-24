/**
 * Accessible skeleton shown while the MapClient chunk loads.
 * Must not use browser-only APIs (this is server-renderable).
 */
export function MapPlaceholder() {
  return (
    <div
      className="w-full h-full flex items-center justify-center bg-muted/30 text-muted-foreground text-sm"
      role="status"
      aria-label="Načítava sa mapa..."
    >
      <span aria-hidden="true" className="mr-2">⏳</span>
      Načítava sa mapa…
    </div>
  );
}
