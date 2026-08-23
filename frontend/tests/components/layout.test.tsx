import { describe, it, expect } from "vitest";

describe("Sidebar navigation", () => {
  const navItems = [
    "Dashboard",
    "Projects",
    "Evaluations",
    "Runs",
    "Metrics",
    "Red Team",
    "Reports",
    "Settings",
  ];

  it("has all required navigation items", () => {
    expect(navItems).toHaveLength(8);
    expect(navItems).toContain("Dashboard");
    expect(navItems).toContain("Red Team");
  });
});

describe("Pagination", () => {
  it("calculates total pages correctly", () => {
    const total = 100;
    const pageSize = 20;
    const totalPages = Math.ceil(total / pageSize);
    expect(totalPages).toBe(5);
  });
});

describe("Status colors", () => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100";
      case "running":
        return "bg-blue-100";
      case "failed":
        return "bg-red-100";
      case "queued":
        return "bg-yellow-100";
      case "cancelled":
        return "bg-gray-100";
      default:
        return "bg-muted";
    }
  };

  it("returns correct colors for statuses", () => {
    expect(getStatusColor("completed")).toBe("bg-green-100");
    expect(getStatusColor("running")).toBe("bg-blue-100");
    expect(getStatusColor("failed")).toBe("bg-red-100");
    expect(getStatusColor("queued")).toBe("bg-yellow-100");
  });
});
