"""Prompt building utilities for LLM interactions."""

from typing import Any

from app.schemas.apply import ApplyRequest


def build_application_prompt(req: ApplyRequest, vacancy: dict[str, Any]) -> str:
    """Build a prompt for generating cover letter and screening answers."""
    title = vacancy.get("name", "Unknown Position")
    company = vacancy.get("employer", {}).get("name", "Unknown Employer")

    snippet_req = vacancy.get("snippet", {}).get("requirement", "")
    snippet_resp = vacancy.get("snippet", {}).get("responsibility", "")

    full_desc = vacancy.get("description", "")
    questions = vacancy.get("questions", [])
    key_skills = ", ".join(ks.get("name") for ks in vacancy.get("key_skills", []))

    prompt = (
        f"You are a professional career coach. "
        f'Write a concise, persuasive cover letter for the position "{title}" '
        f'at "{company}".\n\n'
        f"Short requirements:\n{snippet_req}\n\n"
        f"Key responsibilities:\n{snippet_resp}\n\n"
        f"Full job description:\n{full_desc}\n\n"
        f"Applicant resume summary:\n{req.resume}\n\n"
        f"Skills: {req.skills} (from request)\n"
        f"Key skills listed in vacancy: {key_skills}\n"
        f"Experience: {req.experience}\n\n"
    )

    if questions:
        prompt += 'Then, under the heading "Screening Answers", answer each question:\n'
        for i, q in enumerate(questions, 1):
            prompt += f"{i}. {q}\n"

    return prompt
