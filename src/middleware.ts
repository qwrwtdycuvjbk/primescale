import { createServerClient } from "@supabase/ssr";
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

  // 1. Fast Django JWT session check via HttpOnly cookies
  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  const hasDjangoSession = Boolean(accessToken || refreshToken);

  if (hasDjangoSession) {
    // Authenticated via Django cookie session; proceed to route
    return NextResponse.next();
  }

  // 2. Supabase Fallback Check (Compatibility Mode)
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (supabaseUrl && supabaseKey) {
    let supabaseResponse = NextResponse.next({ request });

    const supabase = createServerClient(supabaseUrl, supabaseKey, {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    });

    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (user) {
      return supabaseResponse;
    }
  }

  // 3. If route is protected and neither Django nor Supabase user exists, redirect to login
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
