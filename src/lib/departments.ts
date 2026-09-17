import {
  Code2,
  Database,
  Cloud,
  CheckCircle2,
  Shield,
  Briefcase,
  Palette,
  Kanban,
  LineChart,
  Layers,
  Globe,
  LucideIcon,
} from "lucide-react";

export interface DepartmentInfo {
  code: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const DEPARTMENTS: DepartmentInfo[] = [
  {
    code: "all",
    label: "All Departments",
    icon: Layers,
    description: "Browse all verified remote and hybrid engineering, data, product, design, and operations roles.",
  },
  {
    code: "software-engineering",
    label: "Software Engineering",
    icon: Code2,
    description: "Full-stack, backend, frontend, mobile, and systems engineering opportunities.",
  },
  {
    code: "data-ai",
    label: "Data & AI",
    icon: Database,
    description: "Data science, machine learning, AI engineering, data analytics, and data architecture roles.",
  },
  {
    code: "devops-cloud",
    label: "DevOps & Cloud",
    icon: Cloud,
    description: "Site reliability engineering (SRE), cloud architecture, Kubernetes, and infrastructure positions.",
  },
  {
    code: "qa-testing",
    label: "QA & Testing",
    icon: CheckCircle2,
    description: "Quality assurance, SDET, automated testing, and manual test validation opportunities.",
  },
  {
    code: "cybersecurity",
    label: "Cybersecurity",
    icon: Shield,
    description: "Information security, SecOps, penetration testing, compliance, and cloud security roles.",
  },
  {
    code: "product",
    label: "Product",
    icon: Briefcase,
    description: "Technical product management, product ownership, and product leadership positions.",
  },
  {
    code: "design",
    label: "Design",
    icon: Palette,
    description: "UI/UX design, product design, interaction design, and design systems leadership.",
  },
  {
    code: "project-management",
    label: "Project Management",
    icon: Kanban,
    description: "Scrum masters, agile delivery leads, program managers, and PMO specialists.",
  },
  {
    code: "business-operations",
    label: "Business & Operations",
    icon: LineChart,
    description: "Business analytics, enterprise ERP/CRM consultancy, and business operations.",
  },
  {
    code: "other",
    label: "Other",
    icon: Globe,
    description: "Specialized roles across marketing, customer success, sales, and general technology domains.",
  },
];

export function getDepartmentBySlug(slug: string): DepartmentInfo {
  const normalized = (slug || "").toLowerCase().trim();
  const found = DEPARTMENTS.find(
    (d) => d.code.toLowerCase() === normalized || d.label.toLowerCase() === normalized
  );
  return (
    found || {
      code: normalized || "all",
      label: normalized
        ? normalized
            .split("-")
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
            .join(" ")
        : "All Departments",
      icon: Layers,
      description: "Explore opportunities in this department.",
    }
  );
}
