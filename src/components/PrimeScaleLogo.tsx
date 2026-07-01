import Image from "next/image";
import { cn } from "@/lib/utils";

type PrimeScaleLogoProps = {
  /** `light` = white logo for dark backgrounds; `dark` = navy logo for light backgrounds */
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
      src={variant === "light" ? "/primescale-logo.png" : "/primescale-logo-dark.png"}
      alt="PrimeScale"
      width={377}
      height={218}
      priority={priority}
      className={cn("h-11 w-auto sm:h-12", className)}
    />
  );
}
