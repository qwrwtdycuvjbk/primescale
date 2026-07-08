export type UserRole = "employer" | "candidate" | "admin";
export type RoleType = "contract" | "c2h" | "full-time";
export type ExperienceLevel = "junior" | "mid" | "senior" | "lead";
export type SubmissionType = "pasted_jd" | "manual_form";
export type JobStatus = "draft" | "active" | "paused" | "closed" | "archived";
export type CompanyMemberRole = "admin" | "recruiter" | "hiring_manager";
export type MatchStatus =
  | "suggested"
  | "candidate_interested"
  | "employer_shortlisted"
  | "mutual_fit"
  | "rejected";

export type HandoffStatus = "pending" | "contacted" | "intro_made" | "closed";

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
  logo_url?: string;
  description?: string;
  hq_city?: string;
  industry?: string;
  remote_culture_statement?: string;
  domain_verified?: boolean;
  badge_remote_first?: boolean;
  badge_visa_sponsor?: boolean;
  badge_gcc?: boolean;
  profile_complete?: boolean;
  created_at: string;
  updated_at: string;
}

export type AvailabilityStatus = "actively_looking" | "open" | "not_looking";
export type PreferredWorkType = "remote" | "hybrid" | "onsite";
export type PrivacyVisibility = "public" | "employers_only" | "invite_only";
export type CandidateSource = "platform" | "people_prime";

export interface CandidateProfile {
  id: string;
  user_id: string;
  headline?: string;
  phone?: string;
  current_title?: string;
  years_experience?: number;
  skills: string[];
  role_categories: string[];
  experience_level?: ExperienceLevel;
  salary_min?: number;
  salary_max?: number;
  work_authorization?: string;
  us_state?: string;
  remote_preference: string;
  preferred_work_type?: PreferredWorkType;
  resume_url?: string;
  github_url?: string;
  portfolio_url?: string;
  linkedin_url?: string;
  bio?: string;
  availability_status?: AvailabilityStatus;
  privacy_visibility?: PrivacyVisibility;
  profile_completeness?: number;
  open_to_matching: boolean;
  profile_complete: boolean;
  source?: CandidateSource;
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
  expires_at?: string;
  jd_quality_score?: number;
  jd_quality_feedback?: string;
  featured?: boolean;
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
  visible_to_employer?: boolean;
  recruiter_notified_at?: string;
  created_at: string;
  updated_at: string;
  jobs?: Job;
  candidate_profiles?: CandidateProfile & {
    profiles?: Pick<Profile, "full_name" | "email" | "phone">;
  };
}

export interface HandoffRequest {
  id: string;
  match_id: string;
  status: HandoffStatus;
  notes?: string;
  notified_at?: string;
  created_at: string;
  updated_at: string;
  matches?: Match & {
    jobs?: Job & {
      companies?: Pick<Company, "name" | "website">;
      profiles?: Pick<Profile, "full_name" | "email" | "phone">;
    };
    candidate_profiles?: CandidateProfile & {
      profiles?: Pick<Profile, "full_name" | "email" | "phone">;
    };
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
  phone?: string;
  currentTitle?: string;
  yearsExperience?: number;
  skills: string;
  roleCategories: string[];
  experienceLevel: ExperienceLevel;
  salaryMin?: number;
  salaryMax?: number;
  workAuthorization: string;
  usState: string;
  preferredWorkType: PreferredWorkType;
  availabilityStatus: AvailabilityStatus;
  privacyVisibility: PrivacyVisibility;
  bio?: string;
  githubUrl?: string;
  portfolioUrl?: string;
  linkedinUrl?: string;
  resumeUrl?: string;
}

export interface CompanyInput {
  name: string;
  website?: string;
  size?: string;
  description?: string;
  hqCity?: string;
  industry?: string;
  remoteCultureStatement?: string;
  logoUrl?: string;
}

export interface JobInput {
  title: string;
  description: string;
  roleType: RoleType;
  experienceLevel: ExperienceLevel;
  techStack: string;
  salaryRange: string;
  workType: string;
  visaRequirements: string;
  pastedJd?: string;
  status?: JobStatus;
  publish?: boolean;
}
