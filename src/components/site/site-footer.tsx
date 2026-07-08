import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import Link from "next/link";
import { ArrowUpRight, Mail, Phone } from "lucide-react";

const productLinks = [
  { label: "How it works", href: "#how-it-works" },
  { label: "The difference", href: "#why-us" },
  { label: "For employers", href: "#for-employers" },
  { label: "For candidates", href: "#for-candidates" },
];

const companyLinks = [
  {
    label: "People Prime Worldwide",
    href: "https://people-prime.com/index",
    external: true,
  },
  { label: "Contact", href: "#contact" },
];

const contact = [
  {
    icon: Mail,
    label: "remote@people-prime.com",
    href: "mailto:remote@people-prime.com",
  },
  {
    icon: Phone,
    label: "+1 (747) 212-1886",
    href: "tel:+17472121886",
  },
];

const socialLinks = [
  {
    label: "LinkedIn",
    href: "https://www.linkedin.com/company/peopleprimeww/posts/?feedView=all",
  },
  {
    label: "X",
    href: "https://x.com/peopleprimeww",
  },
  {
    label: "YouTube",
    href: "https://www.youtube.com/@PeoplePrime_ITinfraJobs",
  },
  {
    label: "Instagram",
    href: "https://www.instagram.com/peopleprime_worldwide/",
  },
];

export function SiteFooter() {
  return (
    <footer id="contact" className="noise relative overflow-hidden bg-ink text-ink-foreground">
      <div className="relative mx-auto w-full max-w-screen-2xl px-8 pt-20 sm:px-10 lg:px-12">
        <div className="flex flex-col gap-8 border-b border-white/10 pb-16 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-ink-muted">
              Ready when you are
            </p>
            <h2 className="display-headline mt-5 max-w-2xl text-balance text-4xl sm:text-6xl">
              Match US tech talent{" "}
              <span className="italic text-primary">faster.</span>
            </h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href="/auth/employer/signup"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
            >
              Post a role
              <ArrowUpRight className="h-4 w-4" />
            </Link>
            <Link
              href="/auth/candidate/signup"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-6 py-3.5 text-sm font-semibold transition-colors hover:bg-white/5"
            >
              Get matched
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="grid gap-12 py-16 lg:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <PrimeScaleLogo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-muted">
              AI-powered US remote tech hiring, backed by People Prime Worldwide.
              Better Careers, Better Lives.
            </p>

            <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
              <p className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
                Powered by
              </p>
              <p className="mt-2 text-sm font-semibold text-ink-foreground">
                People Prime Worldwide
              </p>
              <a
                href="https://people-prime.com/index"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex text-sm text-primary transition-colors hover:text-primary/80"
              >
                people-prime.com
              </a>
            </div>

            <ul className="mt-6 flex flex-col gap-3 text-sm text-ink-muted">
              {contact.map((c) => (
                <li key={c.label}>
                  <a
                    href={c.href}
                    className="flex items-center gap-3 transition-colors hover:text-ink-foreground"
                  >
                    <c.icon className="h-4 w-4 text-primary" />
                    {c.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-mono text-xs uppercase tracking-[0.2em] text-ink-muted">
              Platform
            </h4>
            <ul className="mt-5 flex flex-col gap-3">
              {productLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-ink-foreground/90 transition-colors hover:text-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-mono text-xs uppercase tracking-[0.2em] text-ink-muted">
              Company
            </h4>
            <ul className="mt-5 flex flex-col gap-3">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    target={link.external ? "_blank" : undefined}
                    rel={link.external ? "noopener noreferrer" : undefined}
                    className="text-sm text-ink-foreground/90 transition-colors hover:text-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>

            <h4 className="mt-8 font-mono text-xs uppercase tracking-[0.2em] text-ink-muted">
              Follow us
            </h4>
            <ul className="mt-5 flex flex-col gap-3">
              {socialLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-ink-foreground/90 transition-colors hover:text-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div
          className="display-headline select-none border-t border-white/10 pt-8 text-[22vw] leading-[0.8] text-white/[0.06] lg:text-[16rem]"
          aria-hidden
        >
          PrimeScale
        </div>

        <div className="flex flex-col items-center justify-between gap-4 py-8 text-sm text-ink-muted sm:flex-row">
          <p>
            © {new Date().getFullYear()} People Prime Worldwide. All rights
            reserved.
          </p>
          <p>US remote tech roles only.</p>
        </div>
      </div>
    </footer>
  );
}
