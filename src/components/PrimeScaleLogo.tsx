import Image from "next/image";
import { cn } from "@/lib/utils";

type PrimeScaleLogoProps = {
  /** `light` = white logo for dark backgrounds; `dark` = dark logo for light backgrounds */
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
      src="/image.png"
      alt="PrimeScale"
      width={400}
      height={260}
      priority={priority}
      className={cn(
        "h-11 w-auto sm:h-12",
        variant === "dark" && "invert",
        className,
      )}
    />
  );
}
