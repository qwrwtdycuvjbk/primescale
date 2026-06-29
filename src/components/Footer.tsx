import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";

const platformLinks = [
  { label: "Post a role", href: "#post-role" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Why us", href: "#why-us" },
];

const companyLinks = [
  {
    label: "People Prime Worldwide",
    href: "https://people-prime.com/index",
    external: true,
  },
  { label: "Contact us", href: "#contact" },
];

const socialLinks = [
  {
    label: "People Prime website",
    href: "https://people-prime.com/index",
    icon: GlobeIcon,
  },
  {
    label: "LinkedIn",
    href: "https://www.linkedin.com/company/peopleprimeww/posts/?feedView=all",
    icon: LinkedInIcon,
  },
  {
    label: "X",
    href: "https://x.com/peopleprimeww",
    icon: XIcon,
  },
  {
    label: "YouTube",
    href: "https://www.youtube.com/@PeoplePrime_ITinfraJobs",
    icon: YouTubeIcon,
  },
  {
    label: "Instagram",
    href: "https://www.instagram.com/peopleprime_worldwide/",
    icon: InstagramIcon,
  },
];

export function Footer() {
  return (
    <footer id="contact" className="bg-slate-950 px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <PrimeScaleLogo className="h-14 w-auto sm:h-16" />
            <p className="mt-4 text-sm text-slate-400">
              Vetted remote tech talent in 24 hours
            </p>

            <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Powered by
              </p>
              <p className="mt-2 text-sm font-semibold text-white">
                People Prime Worldwide
              </p>
              <p className="mt-1 text-sm font-medium text-teal-400">
                Better Careers, Better Lives
              </p>
              <div className="mt-4 border-t border-white/10 pt-4">
                <a
                  href="https://people-prime.com/index"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-slate-400 transition hover:text-teal-400"
                >
                  <GlobeIcon className="h-4 w-4 text-teal-500" />
                  people-prime.com
                </a>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              Platform
            </p>
            <ul className="mt-4 space-y-3">
              {platformLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-slate-300 transition hover:text-white"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              Company
            </p>
            <ul className="mt-4 space-y-3">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    target={link.external ? "_blank" : undefined}
                    rel={link.external ? "noopener noreferrer" : undefined}
                    className="text-sm text-slate-300 transition hover:text-white"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              Contact
            </p>
            <ul className="mt-4 space-y-3">
              <li>
                <a
                  href="tel:+17472121886"
                  className="flex items-center gap-2 text-sm text-slate-300 transition hover:text-white"
                >
                  <PhoneIcon className="h-4 w-4 shrink-0 text-teal-500" />
                  +1 (747) 212-1886
                </a>
              </li>
              <li>
                <a
                  href="mailto:remote@people-prime.com"
                  className="flex items-center gap-2 text-sm text-slate-300 transition hover:text-white"
                >
                  <MailIcon className="h-4 w-4 shrink-0 text-teal-500" />
                  remote@people-prime.com
                </a>
              </li>
            </ul>

            <p className="mt-8 text-xs font-semibold uppercase tracking-widest text-slate-500">
              Follow us
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              {socialLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={link.label}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-teal-500/40 text-teal-500 transition hover:border-teal-400 hover:bg-teal-500/10 hover:text-teal-400"
                >
                  <link.icon className="h-4 w-4" />
                </a>
              ))}
            </div>
          </div>
        </div>

        <p className="mt-12 border-t border-white/10 pt-8 text-center text-sm text-slate-500">
          © {new Date().getFullYear()} People Prime Worldwide. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  );
}

function PhoneIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className={className}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"
      />
    </svg>
  );
}

function MailIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className={className}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M22 6l-10 7L2 6" />
    </svg>
  );
}

function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden
    >
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 114.126 0 2.063 2.063 0 01-2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden
    >
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden
    >
      <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className={className}
      aria-hidden
    >
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z" />
      <path d="M17.5 6.5h.01" strokeLinecap="round" />
    </svg>
  );
}
