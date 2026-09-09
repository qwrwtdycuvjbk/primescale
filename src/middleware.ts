import { NextResponse, type NextRequest } from "next/server";

const protectedPrefixes = ["/employer", "/candidate", "/admin"];
const authExchangePaths = ["/auth/callback", "/auth/confirm"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (authExchangePaths.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  const isProtected = protectedPrefixes.some((prefix) =>
    pathname.startsWith(prefix),
  );

  // 1. Django JWT session check via HttpOnly cookies
  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  const hasDjangoSession = Boolean(accessToken || refreshToken);

  if (hasDjangoSession) {
    // Authenticated via Django cookie session; proceed to route
    return NextResponse.next();
  }

  // 2. If route is protected and no Django session exists, redirect to login
  if (isProtected) {
    const loginUrl = request.nextUrl.clone();
    if (pathname.startsWith("/admin")) {
      loginUrl.pathname = "/auth/employer/login";
    } else {
      loginUrl.pathname = pathname.startsWith("/employer")
        ? "/auth/employer/login"
        : "/auth/candidate/login";
    }
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/auth/:path*", "/admin/:path*", "/candidate/:path*", "/employer/:path*"],
};
