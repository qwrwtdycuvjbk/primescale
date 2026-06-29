import Image from "next/image";
import { cn } from "@/lib/utils";

type PrimeScaleLogoProps = {
  /** `light` = white logo for dark backgrounds; `dark` = black logo for light backgrounds */
  variant?: "light" | "dark";
  className?: string;
  priority?: boolean;
};

export function PrimeScaleLogo({
  variant = "light",
  className,
  priority,
}: PrimeScaleLogoProps) {
  return (
    <Image
      src="/primescale-logo.png"
      alt="PrimeScale"
      width={180}
      height={52}
      priority={priority}
      className={cn(
        "h-10 w-auto sm:h-11",
        variant === "dark" && "brightness-0",
        className,
      )}
    />
  );
}
