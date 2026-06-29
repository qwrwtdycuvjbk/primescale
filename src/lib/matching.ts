export function parseSkills(input: string | string[]): string[] {
  const raw = Array.isArray(input) ? input.join(",") : input;
  return [
    ...new Set(
      raw
        .split(/[,;\n|]/)
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
}

function skillMatches(candidateSkill: string, jobSkill: string): boolean {
  return (
    candidateSkill === jobSkill ||
    candidateSkill.includes(jobSkill) ||
    jobSkill.includes(candidateSkill)
  );
}

export function computeSkillOverlapScore(
  candidateSkills: string[],
  jobSkills: string[],
): number {
  if (jobSkills.length === 0) return 40;
  if (candidateSkills.length === 0) return 0;

  const matched = jobSkills.filter((jobSkill) =>
    candidateSkills.some((cs) => skillMatches(cs, jobSkill)),
  );

  return Math.round((matched.length / jobSkills.length) * 100);
}

export function experienceScore(
  candidateLevel?: string,
  jobLevel?: string,
): number {
  if (!candidateLevel || !jobLevel) return 50;
  const order = ["junior", "mid", "senior", "lead"];
  const cIdx = order.indexOf(candidateLevel);
  const jIdx = order.indexOf(jobLevel);
  if (cIdx === -1 || jIdx === -1) return 50;
  const diff = cIdx - jIdx;
  if (diff >= 0) return 100;
  if (diff === -1) return 70;
  return 40;
}

export function combinedMatchScore(
  skillScore: number,
  expScore: number,
): number {
  return Math.round(skillScore * 0.7 + expScore * 0.3);
}

export async function llmMatchReason(
  candidate: {
    headline?: string;
    skills: string[];
    experience_level?: string;
  },
  job: {
    title: string;
    description: string;
    tech_stack: string[];
    experience_level: string;
  },
  score: number,
): Promise<string | null> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return null;

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        temperature: 0.3,
        max_tokens: 120,
        messages: [
          {
            role: "system",
            content:
              "You write one concise sentence explaining why a US tech candidate matches a job. Be specific and factual. No hype.",
          },
          {
            role: "user",
            content: JSON.stringify({
              score,
              candidate,
              job: {
                title: job.title,
                stack: job.tech_stack,
                level: job.experience_level,
              },
            }),
          },
        ],
      }),
    });

    if (!response.ok) return null;
    const data = await response.json();
    return data.choices?.[0]?.message?.content?.trim() ?? null;
  } catch {
    return null;
  }
}

export async function parseJobDescriptionWithLlm(
  pastedJd: string,
): Promise<Partial<{
  title: string;
  tech_stack: string[];
  experience_level: string;
  role_type: string;
  salary_range: string;
  description: string;
}> | null> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return null;

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        temperature: 0.2,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content: `Extract US remote tech job fields from a job description. Return JSON with keys: title, tech_stack (array of strings), experience_level (junior|mid|senior|lead), role_type (contract|c2h|full-time), salary_range (string or null), description (clean summary).`,
          },
          { role: "user", content: pastedJd.slice(0, 8000) },
        ],
      }),
    });

    if (!response.ok) return null;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    if (!content) return null;
    return JSON.parse(content);
  } catch {
    return null;
  }
}
