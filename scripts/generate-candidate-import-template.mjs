import { writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import * as XLSX from "xlsx";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outPath = join(
  __dirname,
  "../public/templates/people-prime-candidate-import.xlsx",
);

const headers = [
  "full_name",
  "email",
  "phone",
  "headline",
  "current_title",
  "years_experience",
  "skills",
  "role_categories",
  "experience_level",
  "salary_min",
  "salary_max",
  "work_authorization",
  "location",
  "preferred_work_type",
  "availability",
  "bio",
  "linkedin_url",
  "github_url",
  "portfolio_url",
];

const examples = [
  [
    "Alex Kumar",
    "alex.kumar@example.com",
    "+1 747 555 0101",
    "Senior DevOps engineer",
    "DevOps Lead",
    9,
    "AWS, Kubernetes, Terraform, Docker",
    "DevOps",
    "senior",
    140000,
    175000,
    "international_remote",
    "Remote",
    "remote",
    "actively_looking",
    "Platform engineer with 9 years building cloud infrastructure.",
    "https://linkedin.com/in/alexkumar",
    "https://github.com/alexkumar",
    "",
  ],
  [
    "Priya Sharma",
    "priya.sharma@example.com",
    "+91 98 5555 0102",
    "Full-stack engineer",
    "Staff Engineer",
    7,
    "React, Node.js, TypeScript, PostgreSQL",
    "Full-stack",
    "senior",
    120000,
    150000,
    "international_remote",
    "India",
    "remote",
    "open",
    "Product-focused engineer for global remote teams.",
    "https://linkedin.com/in/priyasharma",
    "",
    "",
  ],
];

const instructions = [
  ["PrimeScale — People Prime candidate import"],
  [""],
  ["1. Fill one row per candidate in the Candidates sheet."],
  ["2. Required columns: full_name, email, headline, skills, role_categories"],
  ["3. skills → separate with commas (e.g. AWS, Kubernetes, Terraform)"],
  ["4. role_categories → pick ONE value from the Valid values sheet per row"],
  ["5. experience_level → junior, mid, senior, or lead"],
  ["6. work_authorization → copy exactly from Valid values sheet"],
  ["7. availability → actively_looking, open, or not_looking"],
  ["8. Delete the two sample rows before uploading."],
  ["9. Save the file as .xlsx and upload on Admin → Import Excel"],
];

const validValues = [
  ["Column", "Allowed values (copy exactly)"],
  ["role_categories", "AI / ML"],
  ["role_categories", "Cloud"],
  ["role_categories", "Data"],
  ["role_categories", "DevOps"],
  ["role_categories", "Cybersecurity"],
  ["role_categories", "Full-stack"],
  ["role_categories", "Backend"],
  ["role_categories", "Frontend"],
  ["role_categories", "Mobile"],
  ["experience_level", "junior"],
  ["experience_level", "mid"],
  ["experience_level", "senior"],
  ["experience_level", "lead"],
  ["work_authorization", "us_citizen"],
  ["work_authorization", "green_card"],
  ["work_authorization", "h1b"],
  ["work_authorization", "ead"],
  ["work_authorization", "international_remote"],
  ["preferred_work_type", "remote"],
  ["preferred_work_type", "hybrid"],
  ["preferred_work_type", "onsite"],
  ["availability", "actively_looking"],
  ["availability", "open"],
  ["availability", "not_looking"],
];

const workbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(
  workbook,
  XLSX.utils.aoa_to_sheet(instructions),
  "Instructions",
);
XLSX.utils.book_append_sheet(
  workbook,
  XLSX.utils.aoa_to_sheet(validValues),
  "Valid values",
);
XLSX.utils.book_append_sheet(
  workbook,
  XLSX.utils.aoa_to_sheet([headers, ...examples]),
  "Candidates",
);

writeFileSync(outPath, XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }));
console.log(`Wrote ${outPath}`);
