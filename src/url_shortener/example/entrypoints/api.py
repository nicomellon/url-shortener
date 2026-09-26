from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from url_shortener.example import views
from url_shortener.example.domain import commands
from url_shortener.example.service_layer import handlers
from url_shortener.shared.api import Bus, DbSession

router = APIRouter(prefix="/things", tags=["things"])


class CreateThingRequest(BaseModel):
    ref: str
    name: str


@router.post("", status_code=201)
def create_thing(body: CreateThingRequest, bus: Bus):
    try:
        bus.handle(commands.CreateThing(ref=body.ref, name=body.name))
    except handlers.ThingAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{ref}")
def get_thing(ref: str, session: DbSession):
    thing = views.get_thing(session, ref)
    if thing is None:
        raise HTTPException(status_code=404, detail="Thing not found")
    return thing
