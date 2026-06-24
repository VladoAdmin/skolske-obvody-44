import { NextRequest, NextResponse } from "next/server";

/**
 * Rate-limit middleware stub — Sprint 0 scaffold.
 *
 * Currently a pass-through. Sprint 6 (security hardening) wires in a real
 * in-memory / Redis-backed rate limiter keyed on IP + route group.
 *
 * Rate-limited route groups (to be enforced in Sprint 6):
 *   /api/auth/*        — login endpoints
 *   /api/admin/import  — dataset ingest
 *   /api/              — general API cap
 */
export function middleware(request: NextRequest) {
  // TODO Sprint 6: implement sliding-window rate limiter
  // For now, just pass through all requests.
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
