const OPS_EMAIL =
  process.env.PEOPLE_PRIME_HANDOFF_EMAIL ?? "remote@people-prime.com";
const RESEND_FROM =
  process.env.RESEND_FROM_EMAIL ?? "PrimeScale <onboarding@resend.dev>";

export function getAppUrl() {
  return process.env.NEXT_PUBLIC_APP_URL ?? "https://primescale.app";
}

export async function sendOpsEmail(subject: string, html: string) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn("RESEND_API_KEY not set; skipping ops email:", subject);
    return false;
  }

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: RESEND_FROM,
      to: [OPS_EMAIL],
      subject,
      html,
    }),
  });

  if (!response.ok) {
    console.error("Ops email failed", subject, await response.text());
    return false;
  }

  return true;
}
