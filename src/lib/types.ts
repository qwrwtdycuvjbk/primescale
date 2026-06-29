export type UserRole = "employer" | "candidate" | "admin";
export type RoleType = "contract" | "c2h" | "full-time";
export type ExperienceLevel = "junior" | "mid" | "senior" | "lead";
export type SubmissionType = "pasted_jd" | "manual_form";
export type JobStatus = "draft" | "active" | "closed";
export type MatchStatus =
  | "suggested"
  | "candidate_interested"
  | "employer_shortlisted"
  | "rejected";

export interface Profile {
  id: string;
  role: UserRole;
  full_name: string;
  email: string;
  phone?: string;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  owner_id: string;
  name: string;
  website?: string;
  size?: string;
  country: string;
  created_at: string;
  updated_at: string;
}

export interface CandidateProfile {
  id: string;
  user_id: string;
  headline?: string;
  skills: string[];
  role_categories: string[];
  experience_level?: ExperienceLevel;
  salary_min?: number;
  salary_max?: number;
  work_authorization?: string;
  us_state?: string;
  remote_preference: string;
  resume_url?: string;
  bio?: string;
  open_to_matching: boolean;
  profile_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  company_id: string;
  posted_by: string;
  title: string;
  description: string;
  role_type: RoleType;
  experience_level: ExperienceLevel;
  tech_stack: string[];
  salary_range?: string;
  work_type: string;
  visa_requirements?: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  companies?: Pick<Company, "name" | "website">;
}

export interface Match {
  id: string;
  candidate_profile_id: string;
  job_id: string;
  match_score: number;
  match_reason?: string;
  status: MatchStatus;
  created_at: string;
  updated_at: string;
  jobs?: Job;
  candidate_profiles?: CandidateProfile & {
    profiles?: Pick<Profile, "full_name" | "email">;
  };
}

export interface RoleSubmission {
  id: string;
  createdAt: string;
  companyName: string;
  contactName: string;
  email: string;
  phone: string;
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
  phone: string;
  jobTitle: string;
  roleType: RoleType;
  experienceLevel: ExperienceLevel;
  techStack: string;
  salaryRange?: string;
  description: string;
  notes?: string;
  submissionType?: SubmissionType;
}

export interface CandidateProfileInput {
  headline: string;
  skills: string;
  roleCategories: string[];
  experienceLevel: ExperienceLevel;
  salaryMin?: number;
  salaryMax?: number;
  workAuthorization: string;
  usState: string;
  bio?: string;
}

export interface CompanyInput {
  name: string;
  website?: string;
  size?: string;
}

export interface JobInput {
  title: string;
  description: string;
  roleType: RoleType;
  experienceLevel: ExperienceLevel;
  techStack: string;
  salaryRange?: string;
  visaRequirements?: string;
  pastedJd?: string;
}
