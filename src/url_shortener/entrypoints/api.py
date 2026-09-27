from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

from url_shortener import views
from url_shortener.domain import model
from url_shortener.entrypoints.dependencies import DbSession
from url_shortener.service_layer import services

router = APIRouter(tags=["urls"])

# Collisions are rare with 62**7 codes, so a few retries are plenty
MAX_ATTEMPTS = 3


class CreateShortURLRequest(BaseModel):
    url: HttpUrl


class ShortURLResponse(BaseModel):
    short_code: str
    short_url: str
    url: str


@router.post("/urls", status_code=201)
def create_short_url(
    body: CreateShortURLRequest, session: DbSession, request: Request
) -> ShortURLResponse:
    url = str(body.url)
    for _ in range(MAX_ATTEMPTS):
        short_code = model.new_short_code()
        try:
            services.create_short_url(session, short_code, url)
            break
        except services.ShortCodeTaken:
            continue
    else:
        raise HTTPException(status_code=503, detail="Could not allocate a short code")
    return ShortURLResponse(
        short_code=short_code,
        short_url=str(request.url_for("redirect", short_code=short_code)),
        url=url,
    )


# 302 rather than 301, so browsers don't cache the redirect forever
@router.get("/{short_code}", status_code=302, response_class=RedirectResponse)
def redirect(short_code: str, session: DbSession) -> RedirectResponse:
    url = views.get_url(session, short_code)
    if url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(url, status_code=302)
