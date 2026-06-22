export type RoleType = "contract" | "c2h" | "full-time";
export type ExperienceLevel = "junior" | "mid" | "senior" | "lead";
export type SubmissionType = "pasted_jd" | "manual_form";

export interface RoleSubmission {
  id: string;
  createdAt: string;
  companyName: string;
  contactName: string;
  email: string;
  jobTitle: string;
  roleType: RoleType;
  experienceLevel: ExperienceLevel;
  techStack: string;
  salaryRange?: string;
  description: string;
  notes?: string;
  submissionType: SubmissionType;
}

export interface RoleSubmissionInput {
  companyName: string;
  contactName: string;
  email: string;
  jobTitle: string;
  roleType: RoleType;
  experienceLevel: ExperienceLevel;
  techStack: string;
  salaryRange?: string;
  description: string;
  notes?: string;
  submissionType?: SubmissionType;
}
