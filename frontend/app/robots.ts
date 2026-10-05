import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:5173";

  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/login", "/register", "/privacy", "/terms"],
      disallow: [
        "/dashboard",
        "/projects",
        "/evaluations",
        "/runs",
        "/redteam",
        "/experiments",
        "/analytics",
        "/agents",
        "/settings",
        "/organizations",
        "/api-keys",
        "/audit",
        "/notifications",
        "/metrics",
        "/datasets",
        "/schedules",
        "/reports",
        "/profiles",
        "/api-keys",
        "/api/",
      ],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
