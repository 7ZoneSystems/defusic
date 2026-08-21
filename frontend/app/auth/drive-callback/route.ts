import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code");
  const error = req.nextUrl.searchParams.get("error");

  if (error || !code) {
    return NextResponse.redirect(
      new URL(`/library?drive_error=${error || "no_code"}`, req.url)
    );
  }

  // Redirect to library with the code; the frontend will exchange it server-side
  const callbackUrl = new URL("/library", req.url);
  callbackUrl.searchParams.set("drive_code", code);
  return NextResponse.redirect(callbackUrl);
}
