import Link from "next/link";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";

export function Header() {
  return (
    <header className="sticky top-0 z-50 bg-slate-950">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center">
          <PrimeScaleLogo priority className="h-16 w-auto sm:h-[4.5rem]" />
        </Link>
        <nav className="hidden items-center gap-8 text-sm text-slate-300 md:flex">
          <a href="#how-it-works" className="transition hover:text-white">
            How it works
          </a>
          <a href="#for-employers" className="transition hover:text-white">
            Employers
          </a>
          <a href="#for-candidates" className="transition hover:text-white">
            Candidates
          </a>
          <a href="#contact" className="transition hover:text-white">
            Contact
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <Link
            href="/auth/login"
            className="hidden text-sm text-slate-300 transition hover:text-white sm:inline"
          >
            Log in
          </Link>
          <Link
            href="/auth/employer/signup"
            className="rounded-full bg-teal-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-teal-400"
          >
            Post a role
          </Link>
        </div>
      </div>
    </header>
  );
}
