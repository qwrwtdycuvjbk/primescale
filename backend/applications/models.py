"""
Applications Models.
Phase 17 — Job Applications Migration.

The application model leverages the underlying Match model from `matching`,
representing the candidate application lifecycle:
- suggested
- candidate_interested (Applied)
- employer_shortlisted
- mutual_fit
- rejected

Using Match as the underlying data store guarantees that:
1. UUIDs and existing relationship graphs are 100% preserved.
2. Duplicate applications to the same job are prohibited by the unique_candidate_job_match constraint.
3. Applications integrate seamlessly with the recruiter review and handoff queue.
"""

from matching.models import Match

# Re-export Match as Application for explicit domain modeling
Application = Match
