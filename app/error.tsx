'use client'

interface ErrorProps {
  error: Error
  reset: () => void
}

export default function GlobalError({ reset }: ErrorProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4">
      <h2 className="text-lg font-semibold">Stala sa chyba</h2>
      <p className="text-sm text-muted-foreground text-center max-w-sm">
        Skúste obnoviť stránku alebo nahláste problém správcovi portálu.
      </p>
      <button
        onClick={reset}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Skúsiť znova
      </button>
    </div>
  )
}
