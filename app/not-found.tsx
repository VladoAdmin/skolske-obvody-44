import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4">
      <h2 className="text-lg font-semibold">Stránka nenájdená</h2>
      <p className="text-sm text-muted-foreground">
        Obvod alebo stránka, ktorú hľadáte, neexistuje.
      </p>
      <Link
        href="/"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Späť na domov
      </Link>
    </div>
  )
}
