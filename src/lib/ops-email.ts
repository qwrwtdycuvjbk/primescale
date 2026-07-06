const OPS_EMAIL =
  process.env.PEOPLE_PRIME_HANDOFF_EMAIL ?? "remote@people-prime.com";
const RESEND_FROM =
  process.env.RESEND_FROM_EMAIL ?? "PrimeScale <onboarding@resend.dev>";

export function getAppUrl() {
  return process.env.NEXT_PUBLIC_APP_URL ?? "https://primescale.app";
}

function sandboxAllowedRecipient(errorBody: string): string | null {
  const match = errorBody.match(
    /only send testing emails to your own email address \(([^)]+)\)/i,
  );
  return match?.[1] ?? null;
}

async function deliverOpsEmail(
  apiKey: string,
  to: string,
  subject: string,
  html: string,
): Promise<{ ok: true } | { ok: false; body: string }> {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: RESEND_FROM,
      to: [to],
      subject,
      html,
    }),
  });

  if (response.ok) return { ok: true };
  return { ok: false, body: await response.text() };
}

export async function sendOpsEmail(subject: string, html: string) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn("RESEND_API_KEY not set; skipping ops email:", subject);
    return false;
  }

  const devOverride = process.env.RESEND_DEV_TO?.trim();
  const recipient =
    process.env.NODE_ENV === "development" && devOverride
      ? devOverride
      : OPS_EMAIL;

  let result = await deliverOpsEmail(apiKey, recipient, subject, html);

  if (
    !result.ok &&
    process.env.NODE_ENV === "development" &&
    recipient !== devOverride
  ) {
    const fallback = sandboxAllowedRecipient(result.body) ?? devOverride;
    if (fallback && fallback !== recipient) {
      console.warn(
        `Ops email to ${recipient} blocked by Resend sandbox; retrying to ${fallback}`,
      );
      result = await deliverOpsEmail(
        apiKey,
        fallback,
        `[DEV] ${subject}`,
        `<p><em>Dev redirect: intended recipient was ${recipient}.</em></p>${html}`,
      );
    }
  }

  if (!result.ok) {
    console.error("Ops email failed", subject, result.body);
    return false;
  }

  return true;
}
