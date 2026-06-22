import Image from "next/image";
import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-50 bg-slate-950">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center">
          <Image
            src="/primescale-logo.png"
            alt="PrimeScale"
            width={377}
            height={218}
            priority
            className="h-14 w-auto"
          />
        </Link>
        <nav className="hidden items-center gap-8 text-sm text-slate-300 md:flex">
          <a href="#how-it-works" className="transition hover:text-white">
            How it works
          </a>
          <a href="#why-us" className="transition hover:text-white">
            Why us
          </a>
          <a href="#contact" className="transition hover:text-white">
            Contact
          </a>
        </nav>
        <a
          href="#post-role"
          className="rounded-full bg-teal-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-teal-400"
        >
          Post a role
        </a>
      </div>
    </header>
  );
}
