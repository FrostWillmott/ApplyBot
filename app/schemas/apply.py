from pydantic import BaseModel


class CoverLetterRequest(BaseModel):
    job_title: str
    company: str
    skills: str
    experience: str


class ApplyRequest(BaseModel):
    position: str
    resume: str
