"""
Robust, deterministic technical skill extraction utility for PeopleRemotely.

Extracts canonical programming languages, frameworks, databases, cloud platforms,
and devops/infrastructure tools from unstructured text or structured lists.
- Enforces strict regex word boundaries (preventing false positives like 'c' in 'candidate').
- Replaces/filters generic categories like 'IT Jobs', 'Information Technology', etc.
- Maps aliases and variations to canonical skill names.
"""

from __future__ import annotations

import re
from typing import Any, Final, Iterable, Sequence

# Canonical skill mapping: maps lowercase alias -> canonical display name
CANONICAL_SKILL_MAP: Final[dict[str, str]] = {
    # Languages
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    ".net": ".NET",
    "dotnet": ".NET",
    "asp.net": "ASP.NET",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "scala": "Scala",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "dart": "Dart",
    "r": "R",
    "perl": "Perl",
    "bash": "Bash",
    "shell": "Shell",
    "sql": "SQL",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "sass": "Sass",
    "scss": "Sass",

    # Web & Application Frameworks
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "react native": "React Native",
    "react-native": "React Native",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "rails": "Ruby on Rails",
    "ruby on rails": "Ruby on Rails",
    "laravel": "Laravel",
    "symfony": "Symfony",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "graphql": "GraphQL",
    "rest": "REST",
    "rest api": "REST",
    "rest apis": "REST",
    "restful": "REST",
    "restful api": "REST",
    "restful apis": "REST",
    "grpc": "gRPC",

    # Databases & Caching
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "dynamodb": "DynamoDB",
    "cassandra": "Cassandra",
    "oracle": "Oracle",
    "mssql": "SQL Server",
    "sql server": "SQL Server",
    "neo4j": "Neo4j",
    "mariadb": "MariaDB",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",

    # Cloud & DevOps & Messaging
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI",
    "git": "Git",
    "linux": "Linux",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "celery": "Celery",
    "airflow": "Airflow",
    "spark": "Apache Spark",
    "hadoop": "Hadoop",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-Learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
}

# Generic / non-skill categories to explicitly filter out
GENERIC_CATEGORY_BLACKLIST: Final[set[str]] = {
    "it jobs",
    "it",
    "information technology",
    "engineering",
    "software engineer",
    "software engineering",
    "software developer",
    "developer",
    "technology",
    "computer software",
    "general",
    "other",
    "unspecified",
    "customer service",
    "operations",
    "product",
    "sales",
    "marketing",
    "business analysis",
    "management",
    "project management",
}


def is_generic_category(label: str | None) -> bool:
    """Returns True if the label matches a broad category rather than a specific skill."""
    if not label or not isinstance(label, str):
        return True
    cleaned = label.strip().lower()
    return cleaned in GENERIC_CATEGORY_BLACKLIST or cleaned.replace("-", " ") in GENERIC_CATEGORY_BLACKLIST


def extract_technical_skills(
    source: str | Sequence[str] | Iterable[str] | None,
) -> list[str]:
    """
    Extracts and normalizes technical skills from either unstructured text (job description/title,
    candidate resume text) or a sequence of skill strings/tags.

    Guarantees:
    - Case-insensitive matching.
    - Word boundary protection for short identifiers and symbols (e.g. C++, C#, .NET, Go, R).
    - Aliases mapped to canonical names (e.g. 'postgres' -> 'PostgreSQL', 'react.js' -> 'React').
    - Generic categories (e.g. 'IT Jobs') excluded.
    - Returns a deduplicated list sorted alphabetically.
    """
    if source is None:
        return []

    found_skills: set[str] = set()

    # If source is a sequence/collection of items (and not a single string)
    if isinstance(source, (list, tuple, set)):
        items_to_process: list[str] = []
        for item in source:
            if not item:
                continue
            item_str = str(item).strip()
            if not item_str:
                continue

            # Check if this item itself is a generic category
            if is_generic_category(item_str):
                continue

            # Check if direct match in canonical map (or hyphen-separated version)
            direct_key = item_str.lower()
            unhyphenated_key = direct_key.replace("-", " ")
            if direct_key in CANONICAL_SKILL_MAP:
                found_skills.add(CANONICAL_SKILL_MAP[direct_key])
            elif unhyphenated_key in CANONICAL_SKILL_MAP:
                found_skills.add(CANONICAL_SKILL_MAP[unhyphenated_key])
            else:
                # Treat item as text to scan
                items_to_process.append(item_str)

        if not items_to_process:
            return sorted(list(found_skills))
        text_to_scan = " ".join(items_to_process)
    elif isinstance(source, str):
        text_to_scan = source
    else:
        text_to_scan = str(source)

    if not text_to_scan.strip():
        return sorted(list(found_skills))

    # Pre-pad text for boundary detection
    padded_text = f" {text_to_scan.lower()} "

    # Check each canonical skill in our dictionary
    for alias, canonical in CANONICAL_SKILL_MAP.items():
        if canonical in found_skills:
            continue

        alias_lower = alias.lower()
        # Build strict boundary regex based on whether alias contains symbols
        if alias_lower in ("c++", "c#", ".net", "asp.net"):
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias_lower) + r"(?![a-zA-Z0-9])"
        elif alias_lower == "rest":
            # Avoid false positives on common English word "rest" (e.g. "rest of", "at rest", "rest and relaxation")
            # When scanning unstructured free text, require uppercase REST or explicit RESTful / REST API context
            if re.search(r"\bREST\b", text_to_scan) or re.search(r"(?<![a-zA-Z0-9_])(?:restful|rest[\s_-]apis?)(?![a-zA-Z0-9_])", padded_text):
                found_skills.add(canonical)
            continue
        elif alias_lower in ("c", "r"):
            # Very short single-character language requires strict standalone whitespace/punctuation boundary
            pattern = r"(?<![a-zA-Z0-9_])" + re.escape(alias_lower) + r"(?![a-zA-Z0-9_])"
        else:
            pattern = r"(?<![a-zA-Z0-9_])" + re.escape(alias_lower) + r"(?![a-zA-Z0-9_])"

        if re.search(pattern, padded_text):
            found_skills.add(canonical)

    return sorted(list(found_skills))
