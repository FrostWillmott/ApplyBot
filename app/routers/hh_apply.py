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
    found = await hh.list_vacancies(
        text=req.position, page=0, per_page=pages * 20
    )
    items: list[dict[str, Any]] = found.get("items", [])

    results = []
    for vac in items:
        prompt = build_application_prompt(req, vac)
        letter = await llm.generate(prompt)
        try:
            await hh.apply(vacancy_id=vac["id"], cover_letter=letter)
            results.append({"vacancy_id": vac["id"], "status": "ok"})
        except Exception as e:
            results.append(
                {"vacancy_id": vac["id"], "status": "error", "detail": str(e)}
            )

    return {"applications": results}
