"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { PeopleRemotelyLogo } from "@/components/PeopleRemotelyLogo";
import { appContainerClass } from "@/components/site/layout";

const navLinks = [
  { label: "How Applications Work", href: "/#how-applications-work" },
  { label: "Dashboard Workflow", href: "/#dashboard-workflow" },
  { label: "Jobs by Technology", href: "/#departments" },
  { label: "Remote Jobs within US", href: "/#external-jobs" },
  { label: "Remote / Hybrid", href: "/#remote-hybrid-jobs" },
];

interface SiteHeaderProps {
  solid?: boolean;
}

export function SiteHeader({ solid }: SiteHeaderProps = {}) {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<{
    id?: string;
    email?: string;
    role?: string;
    full_name?: string;
  } | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function checkAuth() {
      try {
        const res = await fetch("/api/auth/session", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (isMounted) {
          if (data.authenticated && data.user) {
            setUser(data.user);
          } else {
            setUser(null);
          }
        }
      } catch {
        if (isMounted) setUser(null);
      }
    }
    checkAuth();
    return () => {
      isMounted = false;
    };
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleSignOut = async () => {
    setIsLoggingOut(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });
    } catch {
      // Best effort
    } finally {
      setUser(null);
      setIsLoggingOut(false);
      window.location.href = "/";
    }
  };

  const isSolid = solid !== undefined ? solid : !isHome || scrolled;

  const dashboardPath =
    user?.role === "employer"
      ? "/employer"
      : user?.role === "admin"
        ? "/admin"
        : "/candidate";

  return (
    <header className="animate-header-in fixed inset-x-0 top-0 z-50">
      <div
        className={`flex items-center justify-between gap-6 transition-all duration-300 ${appContainerClass} ${
          isSolid
            ? "my-2 rounded-2xl border border-white/10 bg-ink/90 py-2.5 shadow-lg shadow-black/20 backdrop-blur-md lg:my-2"
            : "border border-transparent py-4"
        }`}
      >
        <Link href="/" className="flex items-center gap-3">
          <PeopleRemotelyLogo className="h-12 w-auto sm:h-14" />
        </Link>

        <nav className="hidden items-center gap-4 xl:gap-6 lg:flex">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-xs xl:text-sm font-medium text-ink-muted transition-colors hover:text-ink-foreground whitespace-nowrap"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 lg:flex">
          {user ? (
            <>
              <Link
                href={dashboardPath}
                className="text-sm font-medium text-ink-muted transition-colors hover:text-ink-foreground whitespace-nowrap"
              >
                Dashboard
              </Link>
              <button
                type="button"
                onClick={handleSignOut}
                disabled={isLoggingOut}
                className="rounded-full border border-white/20 bg-white/5 px-4 py-2 text-sm font-medium text-ink-foreground transition-all hover:bg-white/10 hover:border-white/30 disabled:opacity-50 whitespace-nowrap"
              >
                {isLoggingOut ? "Signing out..." : "Sign out"}
              </button>
            </>
          ) : (
            <>
              <Link
                href="/auth/login"
                className="text-sm font-medium text-ink-foreground transition-opacity hover:opacity-70 whitespace-nowrap"
              >
                Log in
              </Link>
              <Link
                href="/auth/employer/signup"
                className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold leading-none text-primary-foreground transition-transform hover:-translate-y-0.5 whitespace-nowrap"
              >
                Post a role for free
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-ink-foreground lg:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {open && (
        <div className="animate-menu-in mx-2 mt-1 rounded-2xl border border-white/10 bg-ink/95 p-4 backdrop-blur-md lg:hidden">
          <nav className="flex flex-col gap-1">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-ink-muted hover:bg-white/5 hover:text-ink-foreground"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-white/10 pt-3">
              {user ? (
                <>
                  <Link
                    href={dashboardPath}
                    onClick={() => setOpen(false)}
                    className="rounded-lg px-3 py-2 text-sm font-medium text-ink-foreground hover:bg-white/5"
                  >
                    Dashboard
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      handleSignOut();
                    }}
                    disabled={isLoggingOut}
                    className="w-full text-left rounded-lg px-3 py-2 text-sm font-medium text-ink-muted hover:bg-white/5 hover:text-ink-foreground"
                  >
                    {isLoggingOut ? "Signing out..." : "Sign out"}
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/auth/login"
                    onClick={() => setOpen(false)}
                    className="rounded-lg px-3 py-2 text-sm font-medium text-ink-foreground hover:bg-white/5"
                  >
                    Log in
                  </Link>
                  <Link
                    href="/auth/employer/signup"
                    onClick={() => setOpen(false)}
                    className="rounded-full bg-primary px-5 py-2.5 text-center text-sm font-semibold leading-none text-primary-foreground"
                  >
                    Post a role for free
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
