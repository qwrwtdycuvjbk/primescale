export async function scoreJobDescription(job: {
  title: string;
  description: string;
  tech_stack: string[];
  salary_range: string;
  visa_requirements?: string;
}): Promise<{ score: number; feedback: string } | null> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return {
      score: 70,
      feedback:
        "Add a clear salary range, at least three skills, and US work eligibility details.",
    };
  }

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
            content: `Score a US remote tech job post 0-100 for clarity, inclusivity, and completeness. Flag biased language, vague requirements, or missing salary/US eligibility info. Return JSON: { "score": number, "feedback": "2-3 sentences with specific suggestions" }`,
          },
          { role: "user", content: JSON.stringify(job) },
        ],
      }),
    });

    if (!response.ok) return null;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    if (!content) return null;
    const parsed = JSON.parse(content);
    return {
      score: Math.min(100, Math.max(0, Number(parsed.score) || 0)),
      feedback: String(parsed.feedback || ""),
    };
  } catch {
    return null;
  }
}
