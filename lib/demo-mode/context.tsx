'use client'

// VLA-34: global real-only / demo-mode toggle. Client-only state — filters
// already-fetched is_demo=true rows out of the UI, never triggers a refetch.
//
// Persistence: sessionStorage (survives client-side navigation automatically,
// since this provider lives in the root layout and never unmounts) PLUS a
// cosmetic `?demo=0` URL param written via the native History API — NOT
// next/navigation's router. router.push/replace would ask the Next.js server
// for a fresh RSC payload of the current route on every flip (real network
// round-trip); history.replaceState only rewrites the address bar so the
// mode still survives a hard reload / shared link without ever hitting the
// server for the toggle itself.
//
// Default is demo mode ON — the existing behaviour before this toggle
// existed — so anyone who never touches the switch sees zero regression.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'so_demo_mode_v1'
const URL_PARAM = 'demo'

interface DemoModeContextValue {
  demoMode: boolean
  setDemoMode: (value: boolean) => void
}

const DemoModeContext = createContext<DemoModeContextValue | null>(null)

export function DemoModeProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoModeState] = useState(true)

  // Hydrate from the URL param, then sessionStorage, once on mount.
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      const fromUrl = params.get(URL_PARAM)
      if (fromUrl === '0') {
        setDemoModeState(false)
        return
      }
      if (fromUrl === '1') {
        setDemoModeState(true)
        return
      }
      if (sessionStorage.getItem(STORAGE_KEY) === '0') {
        setDemoModeState(false)
      }
    } catch {
      // window/sessionStorage unavailable (SSR guard, private-mode edge cases)
    }
    // Run exactly once — subsequent changes go through setDemoMode below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setDemoMode = useCallback((value: boolean) => {
    setDemoModeState(value)
    try {
      sessionStorage.setItem(STORAGE_KEY, value ? '1' : '0')
      const url = new URL(window.location.href)
      if (value) {
        url.searchParams.delete(URL_PARAM)
      } else {
        url.searchParams.set(URL_PARAM, '0')
      }
      window.history.replaceState(window.history.state, '', url.toString())
    } catch {
      // ignore — state already flipped, persistence is best-effort
    }
  }, [])

  return (
    <DemoModeContext.Provider value={{ demoMode, setDemoMode }}>
      {children}
    </DemoModeContext.Provider>
  )
}

export function useDemoMode(): DemoModeContextValue {
  const ctx = useContext(DemoModeContext)
  if (!ctx) throw new Error('useDemoMode must be used within DemoModeProvider')
  return ctx
}
