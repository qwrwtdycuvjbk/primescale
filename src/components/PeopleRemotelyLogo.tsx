import { cn } from "@/lib/utils";

type PeopleRemotelyLogoProps = {
  /** `light` = white logo for dark backgrounds; `dark` = dark logo for light backgrounds */
  variant?: "light" | "dark";
  className?: string;
};

function LogoSparkle({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={className}
    >
      <path
        d="M6 1v2M6 9v2M1 6h2M9 6h2M2.8 2.8l1.4 1.4M7.8 7.8l1.4 1.4M2.8 9.2l1.4-1.4M7.8 4.2l1.4-1.4"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
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
        "inline-flex flex-col justify-center gap-0 font-sans text-[1.15rem] font-bold leading-none tracking-[-0.03em] sm:text-[1.25rem]",
        variant === "light" ? "text-ink-foreground" : "text-foreground",
        className,
      )}
      role="img"
      aria-label="People Remotely"
    >
      <span className="whitespace-nowrap">People</span>
      <span className="-mt-[0.14em] inline-flex items-end whitespace-nowrap">
        Remotely
        <LogoSparkle
          className={cn(
            "relative -bottom-px ml-0.5 h-[0.34em] w-[0.34em] shrink-0",
            variant === "light" ? "text-white/45" : "text-muted-foreground",
          )}
        />
      </span>
    </span>
  );
}
