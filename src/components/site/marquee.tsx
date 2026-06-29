import { Asterisk } from "lucide-react";

type MarqueeProps = {
  items: string[];
  className?: string;
  duration?: number;
  reverse?: boolean;
};

export function Marquee({
  items,
  className = "",
  duration = 32,
  reverse = false,
}: MarqueeProps) {
  const loop = [...items, ...items];

  return (
    <div className={`pause-on-hover relative flex overflow-hidden ${className}`}>
      <div
        className="animate-marquee flex shrink-0 items-center whitespace-nowrap"
        style={
          {
            "--marquee-duration": `${duration}s`,
            animationDirection: reverse ? "reverse" : "normal",
          } as React.CSSProperties
        }
      >
        {loop.map((item, i) => (
          <span key={`${item}-${i}`} className="flex items-center">
            <span className="px-6 text-2xl font-medium tracking-tight sm:text-3xl">
              {item}
            </span>
            <Asterisk className="h-5 w-5 shrink-0 text-primary-foreground" />
          </span>
        ))}
      </div>
    </div>
  );
}
