interface ProvenanceLinkProps {
  url: string | null | undefined
  label?: string
}

export function ProvenanceLink({ url, label = 'Zdrojový dokument' }: ProvenanceLinkProps) {
  if (!url) {
    return (
      <span className="text-xs text-muted-foreground italic">
        Zdroj nie je verejne publikovateľný
      </span>
    )
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="text-xs text-primary underline hover:text-primary/80"
    >
      {label}
    </a>
  )
}
