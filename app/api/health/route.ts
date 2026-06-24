import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/health
 * Basic liveness probe. Returns 200 + JSON status object.
 * Vercel, Supabase, and routing service checks live here later.
 */
export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "skolske-obvody-44",
    timestamp: new Date().toISOString(),
    sprint: 0,
  });
}
