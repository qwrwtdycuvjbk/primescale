import { cn } from "@/lib/utils";

type PeopleRemotelyLogoProps = {
  /** `light` = white logo for dark backgrounds; `dark` = dark logo for light backgrounds */
  variant?: "light" | "dark";
  className?: string;
};

/** Lime four-point sparkle + dot — matches the People Remotely brand mark */
function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 22"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={className}
    >
      <path
        d="M10 1C10 5.2 6.8 8.4 2.6 8.4C6.8 8.4 10 11.6 10 15.8C10 11.6 13.2 8.4 17.4 8.4C13.2 8.4 10 5.2 10 1Z"
        fill="#d5ec64"
      />
      <circle cx="15.2" cy="18.6" r="2.2" fill="#d5ec64" />
    </svg>
  );
}

export function PeopleRemotelyLogo({
  variant = "light",
  className,
}: PeopleRemotelyLogoProps) {
  return (
    <span
      className={cn(
        "inline-flex flex-col justify-center gap-0 font-sans text-[1.35rem] font-bold leading-[0.92] tracking-[-0.04em] sm:text-[1.5rem]",
        variant === "light" ? "text-ink-foreground" : "text-foreground",
        className,
      )}
      role="img"
      aria-label="People Remotely"
    >
      <span className="inline-flex items-start gap-0.5 whitespace-nowrap">
        People
        <LogoMark className="mt-[0.08em] -ml-0.5 h-[0.95em] w-auto shrink-0" />
      </span>
      <span className="-mt-[0.02em] whitespace-nowrap">Remotely</span>
    </span>
  );
}
