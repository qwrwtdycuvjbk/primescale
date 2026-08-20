import type { MetadataRoute } from "next";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ||
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") ||
  "https://peopleremotely.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const paths: Array<{
    path: string;
    changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
    priority: number;
  }> = [
    { path: "/", changeFrequency: "weekly", priority: 1 },
    {
      path: "/matching",
      changeFrequency: "weekly",
      priority: 0.95,
    },
    {
      path: "/auth/employer/signup",
      changeFrequency: "monthly",
      priority: 0.9,
    },
    {
      path: "/auth/candidate/signup",
      changeFrequency: "monthly",
      priority: 0.9,
    },
    {
      path: "/auth/employer/login",
      changeFrequency: "monthly",
      priority: 0.5,
    },
    {
      path: "/auth/candidate/login",
      changeFrequency: "monthly",
      priority: 0.5,
    },
    { path: "/auth/login", changeFrequency: "monthly", priority: 0.4 },
    { path: "/auth/signup", changeFrequency: "monthly", priority: 0.4 },
  ];

  return paths.map(({ path, changeFrequency, priority }) => ({
    url: `${siteUrl}${path === "/" ? "" : path}`,
    lastModified,
    changeFrequency,
    priority,
  }));
}
