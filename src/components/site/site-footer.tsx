import { PeopleRemotelyLogo } from "@/components/PeopleRemotelyLogo";
import { Mail, Phone } from "lucide-react";
import { appContainerClass } from "@/components/site/layout";

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
      <div className={`relative pt-14 ${appContainerClass}`}>
        <div className="grid gap-10 py-12 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <PeopleRemotelyLogo />
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-ink-muted">
              Global remote tech hiring with AI review. Backed by People
              Prime Worldwide.
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
          className="display-headline select-none border-t border-white/10 pt-6 text-[18vw] leading-[0.8] text-white/[0.06] lg:text-[12rem]"
          aria-hidden
        >
          People Remotely
        </div>

        <div className="flex flex-col items-center justify-between gap-4 py-8 text-sm text-ink-muted sm:flex-row">
          <p>
            © {new Date().getFullYear()} People Prime Worldwide. All rights
            reserved.
          </p>
          <p>Global remote tech hiring.</p>
        </div>
      </div>
    </footer>
  );
}
