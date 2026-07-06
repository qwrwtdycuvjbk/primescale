import { cn } from "@/lib/utils";
import {
  fieldInputClass,
  fieldInputDarkClass,
  fieldLabelClass,
} from "@/components/site/form-styles";

export {
  fieldInputClass,
  fieldInputDarkClass,
  fieldLabelClass,
} from "@/components/site/form-styles";

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
