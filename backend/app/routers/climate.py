"""HA sensor discovery for the room settings modal's dropdowns —
CLIMATE_CADENCE_PLAN.md."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.clients.ha import HomeAssistantClient
from app.deps import get_ha_client
from app.schemas import HaSensorsOut, SensorInfoOut

router = APIRouter(tags=["climate"])


@router.get("/api/ha/sensors", response_model=HaSensorsOut)
def list_ha_sensors(ha_client: HomeAssistantClient = Depends(get_ha_client)) -> HaSensorsOut:
    try:
        sensors = ha_client.list_climate_sensors()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Home Assistant is unreachable") from exc

    out = [
        SensorInfoOut(
            entity_id=sensor.entity_id,
            friendly_name=sensor.friendly_name,
            device_class=sensor.device_class,
            unit=sensor.unit,
            state=sensor.state,
        )
        for sensor in sensors
    ]
    return HaSensorsOut(
        temperature=[s for s in out if s.device_class == "temperature"],
        humidity=[s for s in out if s.device_class == "humidity"],
    )
