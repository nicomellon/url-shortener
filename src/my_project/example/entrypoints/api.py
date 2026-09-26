from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from my_project.example import views
from my_project.example.domain import commands
from my_project.example.service_layer import handlers
from my_project.shared.api import Bus, DbSession

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
