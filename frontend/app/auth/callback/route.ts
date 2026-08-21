import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const access_token = req.nextUrl.searchParams.get("access_token");
  const refresh_token = req.nextUrl.searchParams.get("refresh_token");
  const return_to = req.nextUrl.searchParams.get("return_to") || "/";
  const error = req.nextUrl.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(
      new URL(`/?auth_error=${error}`, req.url)
    );
  }

  // Redirect to target clean URL - never expose tokens in the browser URL
  const res = NextResponse.redirect(new URL(return_to, req.url));

  if (access_token) {
    res.cookies.set("access_token", access_token, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 3600,
    });
  }

  if (refresh_token) {
    res.cookies.set("refresh_token", refresh_token, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 86400,
    });
  }

  return res;
}
