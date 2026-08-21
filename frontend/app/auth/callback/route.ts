import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const return_to = req.nextUrl.searchParams.get("return_to") || "/";
  const error = req.nextUrl.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(
      new URL(`/?auth_error=${error}`, req.url)
    );
  }

  // Tokens are now set as HttpOnly cookies by the backend /auth/callback.
  // This route just handles the redirect to the target page.
  return NextResponse.redirect(new URL(return_to, req.url));
}
