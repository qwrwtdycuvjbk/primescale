import type { Metadata, Viewport } from "next";
import dynamic from "next/dynamic";
import { Geist, Geist_Mono, Fraunces } from "next/font/google";
import "./globals.css";
import { getGoogleSiteVerification } from "@/lib/google-site-verification";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "600", "700"],
});

const Analytics = dynamic(() =>
  import("@vercel/analytics/react").then((mod) => mod.Analytics),
);

const SpeedInsights = dynamic(() =>
  import("@vercel/speed-insights/next").then((mod) => mod.SpeedInsights),
);

const googleSiteVerification = getGoogleSiteVerification();

export const metadata: Metadata = {
  title: "PrimeScale | US remote tech hiring",
  description:
    "Post US remote tech roles or build a candidate profile. Skill-matched shortlists, recruiter-reviewed. Backed by People Prime Worldwide.",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    shortcut: [{ url: "/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-icon.svg", type: "image/svg+xml" }],
  },
  ...(googleSiteVerification
    ? {
        verification: {
          google: googleSiteVerification,
        },
      }
    : {}),
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#2A2A24",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`light ${geistSans.variable} ${geistMono.variable} ${fraunces.variable} bg-background`}
    >
      <head>
        {googleSiteVerification ? (
          <meta name="google-site-verification" content={googleSiteVerification} />
        ) : null}
      </head>
      <body className="min-h-full font-sans antialiased">
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
