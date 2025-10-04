from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.hh_client import HHClient, get_hh_client

router = APIRouter(prefix="/mvp", tags=["mvp"])


@router.get("/search")
async def search_python_vacancies(
    page: int = Query(default=0, ge=0),
    per_page: int = Query(default=20, ge=1, le=100),
    hh_client: HHClient = Depends(get_hh_client),
):
    """Search for 'Python разработчик' vacancies on hh.ru.

    This MVP endpoint performs a simple search without any extra filtering.
    """
    try:
        return await hh_client.search_vacancies(
            text="Python разработчик",
            page=page,
            per_page=per_page,
            schedule="remote",  # только удалёнка
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e!s}")


@router.post("/apply")
async def apply_to_python_vacancies(
    limit: int = Query(default=100, ge=1, le=100, description="Max vacancies to apply to"),
    page: int = Query(default=0, ge=0),
    per_page: int = Query(default=20, ge=1, le=100),
    hh_client: HHClient = Depends(get_hh_client),
):
    """Search 'Python разработчик' (remote only) and apply to the first N.

    Rules for MVP:
    - Use the first available resume from the user's account.
    - Do NOT send cover letters. If HH requires a cover letter, skip that vacancy (record error and continue).
    - Remote-only vacancies via schedule=remote.
    - Gracefully handle when fewer than N vacancies are available.
    """
    try:
        # Get first available resume
        resumes = await hh_client.get_my_resumes()
        items = resumes.get("items", []) if isinstance(resumes, dict) else resumes
        if not items:
            raise HTTPException(status_code=400, detail="Нет доступных резюме в вашем аккаунте hh.ru")
        resume_id = items[0]["id"]

        # Search vacancies (remote only)
        search = await hh_client.search_vacancies(
            text="Python разработчик",
            page=page,
            per_page=per_page,
            schedule="remote",
        )
        vacancies = search.get("items", [])
        if not vacancies:
            return {"applied": 0, "results": [], "message": "Вакансии не найдены"}

        results: list[dict] = []
        applied_count = 0

        for v in vacancies[:limit]:
            vacancy_id = v.get("id")
            if not vacancy_id:
                continue
            try:
                resp = await hh_client.apply(
                    vacancy_id=vacancy_id,
                    resume_id=resume_id,
                    cover_letter=None,
                    answers=None,
                )
                results.append({
                    "vacancy_id": vacancy_id,
                    "status": "ok",
                    "response": resp,
                })
                applied_count += 1
            except Exception as apply_err:
                # Skip and continue on any application error (e.g., cover letter required)
                results.append({
                    "vacancy_id": vacancy_id,
                    "status": "skipped",
                    "error": str(apply_err),
                })

        return {"applied": applied_count, "results": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply failed: {e!s}")
