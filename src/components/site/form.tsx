import { cn } from "@/lib/utils";

export const fieldLabelClass =
  "mb-2 block font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground";

export const fieldInputClass =
  "w-full rounded-xl border border-border bg-background px-4 py-3 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";

export const fieldInputDarkClass =
  "w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-ink-foreground placeholder:text-ink-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";

export function FieldLabel({
  htmlFor,
  children,
  dark,
}: {
  htmlFor?: string;
  children: React.ReactNode;
  dark?: boolean;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn(fieldLabelClass, dark && "text-ink-muted")}
    >
      {children}
    </label>
  );
}

export function PrimaryButton({
  className,
  children,
  type = "button",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {message}
    </p>
  );
}
