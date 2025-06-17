from fastapi import APIRouter, Depends, HTTPException

from app.schemas.apply import ApplyRequest
from app.services.hh_client import HHClient, get_hh_client
from app.services.llm.dependencies import llm_provider_dep
from app.services.prompt_builder import build_application_prompt

router = APIRouter()


@router.post("/apply")
async def apply_for_job(
    req: ApplyRequest,
    vacancy_id: str,
    hh: HHClient = Depends(get_hh_client),
    llm=Depends(llm_provider_dep),
):
    # 1) получаем полные данные вакансии
    resp = await hh.client.get(f"/vacancies/{vacancy_id}")
    resp.raise_for_status()
    vacancy = resp.json()

    # 2) строим единый промпт и запрашиваем LLM
    prompt = build_application_prompt(req, vacancy)
    application_package = await llm.generate(prompt)

    # 3) отправляем на hh.ru
    try:
        result = await hh.apply(
            vacancy_id=vacancy_id, cover_letter=application_package
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HH API error: {e}")

    return {"vacancy_id": vacancy_id, "hh_response": result}
