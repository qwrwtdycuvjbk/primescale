"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { appContainerClass } from "@/components/site/layout";

const navLinks = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Why us", href: "#why-us" },
  { label: "Employers", href: "#for-employers" },
  { label: "Candidates", href: "#for-candidates" },
];

export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="animate-header-in fixed inset-x-0 top-0 z-50">
      <div
        className={`flex items-center justify-between gap-6 transition-all duration-300 ${appContainerClass} ${
          scrolled
            ? "my-2 rounded-2xl border border-white/10 bg-ink/80 py-3 shadow-lg shadow-black/20 backdrop-blur-md lg:my-3"
            : "border border-transparent py-5"
        }`}
      >
        <Link href="/" className="flex items-center gap-3">
          <PrimeScaleLogo className="h-11 w-auto sm:h-12" />
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[12px] font-medium text-ink-muted transition-colors hover:text-ink-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/auth/login"
            className="text-[12px] font-medium text-ink-foreground transition-opacity hover:opacity-70"
          >
            Log in
          </Link>
          <Link
            href="/auth/employer/signup"
            className="rounded-full bg-primary px-5 py-2.5 text-[12px] font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Post a role
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-ink-foreground md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {open && (
        <div className="animate-menu-in mx-2 mt-1 rounded-2xl border border-white/10 bg-ink/95 p-4 backdrop-blur-md md:hidden">
          <nav className="flex flex-col gap-1">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-white/5 hover:text-ink-foreground"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-white/10 pt-3">
              <Link
                href="/auth/login"
                className="rounded-lg px-3 py-2 text-[12px] font-medium text-ink-foreground hover:bg-white/5"
              >
                Log in
              </Link>
              <Link
                href="/auth/employer/signup"
                className="rounded-full bg-primary px-5 py-2.5 text-center text-[12px] font-semibold text-primary-foreground"
              >
                Post a role
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
