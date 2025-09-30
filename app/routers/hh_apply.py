from typing import Any

from fastapi import APIRouter, Depends

from app.schemas.apply import ApplyRequest
from app.services.hh_client import HHClient, get_hh_client
from app.services.llm.dependencies import hh_client_dep, llm_provider_dep
from app.services.prompt_builder import build_application_prompt

router = APIRouter(prefix="/hh", tags=["hh"])


@router.get("/vacancies")
async def vacancies(
    text: str,
    page: int = 0,
    per_page: int = 20,
    hh: HHClient = Depends(get_hh_client),
):
    """Возвращает список вакансий по текстовому поиску."""
    data = await hh.list_vacancies(text=text, page=page, per_page=per_page)
    return data


@router.post("/auto-apply")
async def auto_apply(
    req: ApplyRequest,
    hh=Depends(hh_client_dep),
    llm=Depends(llm_provider_dep),
    pages: int = 1,
):
    """1) Ищет вакансии по req.position
    2) Для каждой вакансии строит prompt из vacancy и req
    3) Генерирует письмо через LLM
    4) Отправляет отклик в HH и собирает результаты
    """
    # Fetch resume details
    resume_details = await hh.get_resume_details(req.resume_id)

    # Extract relevant information from the resume
    experience = resume_details.get("experience", [])
    skills = resume_details.get("skill_set", [])

    # Format experience
    formatted_experience = ""
    for exp in experience:
        company = exp.get("company", "")
        position = exp.get("position", "")
        start_date = exp.get("start", "")
        end_date = exp.get("end", "") or "Present"
        description = exp.get("description", "")
        formatted_experience += f"{company}, {position}, {start_date} - {end_date}: {description}\n"

    # Format skills
    formatted_skills = ", ".join([skill.get("name", "") for skill in skills]) if skills else req.skills

    # Update request with resume information
    enhanced_req = req.copy()
    enhanced_req.experience = formatted_experience or req.experience
    enhanced_req.skills = formatted_skills or req.skills
    enhanced_req.resume = resume_details.get("description", "") or req.resume
    enhanced_req.position = resume_details.get("title", "") or req.position

    found = await hh.list_vacancies(
        text=enhanced_req.position, page=0, per_page=pages * 20
    )
    items: list[dict[str, Any]] = found.get("items", [])

    results = []
    for vac in items:
        prompt = build_application_prompt(enhanced_req, vac)
        letter = await llm.generate(prompt)
        try:
            await hh.apply(vacancy_id=vac["id"], resume_id=req.resume_id, cover_letter=letter)
            results.append({"vacancy_id": vac["id"], "status": "ok"})
        except Exception as e:
            results.append(
                {"vacancy_id": vac["id"], "status": "error", "detail": str(e)}
            )

    return {"applications": results}
