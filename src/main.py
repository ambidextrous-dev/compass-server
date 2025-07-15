import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytz
from dateutil import parser as date_parser
from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from shapely.geometry import LineString

from config import get_settings

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("compass-server")

# Load settings once
settings = get_settings()
storage_dir = Path(settings.storage_dir)
storage_dir.mkdir(exist_ok=True)

app = FastAPI(
    title="Compass Server",
    description="A Python reimplementation of Compass service",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.post("/api/input")
async def receive_input(
    payload: dict = Body(...),
    authorization: str = Header(...),
):
    logger.info("Received /api/input call")
    logger.debug("Raw payload: %s", payload)

    # Extract Bearer token
    token = None
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    logger.info("Auth token: %s", token)

    if token != settings.write_token:
        logger.warning("Invalid write token")
        raise HTTPException(status_code=401, detail="Invalid write token")

    locations = payload.get("locations")
    if locations is None:
        logger.error("No 'locations' in payload")
        raise HTTPException(status_code=400, detail="Missing 'locations' in payload")

    features = []
    for idx, loc in enumerate(locations):
        logger.debug("Processing location #%d: %s", idx, loc)
        if "coords" in loc:
            # old-style Overland shape
            coords = loc["coords"]
            ts = loc.get("timestamp")
            if (not coords or "latitude" not in coords
                    or "longitude" not in coords or ts is None):
                logger.error("Location #%d missing fields coords or timestamp", idx)
                raise HTTPException(
                    status_code=400,
                    detail=f"Location at index {idx} missing required fields",
                )
            feat = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [coords["longitude"], coords["latitude"]],
                },
                "properties": {
                    "timestamp": ts,
                    **{k: v for k, v in loc.items()
                       if k not in ("coords", "timestamp")},
                },
            }

        elif "geometry" in loc and "properties" in loc:
            # already a GeoJSON Feature
            feat = loc

        else:
            logger.error("Location #%d not recognized as Feature or legacy shape", idx)
            raise HTTPException(
                status_code=400,
                detail=f"Location at index {idx} is not a recognized shape",
            )

        features.append(feat)

    # Save to file
    file_name = f"{uuid4().hex}.json"
    file_path = storage_dir / file_name
    logger.info("Saving %d features to %s", len(features), file_path)
    file_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )

    logger.info("Successfully saved file %s", file_name)
    return {"result": "ok"}


@app.get("/api/query")
async def query_data(
    token: str = Query(...),
    date: str = Query(..., description="YYYY-MM-DD"),
    tz: str = Query("UTC", description="Timezone for start/end of day"),
    format: str = Query("full", regex="^(full|linestring)$"),
):
    # 1. Validate token
    if token != settings.read_token:
        raise HTTPException(status_code=401, detail="Invalid read token")

    # 2. Compute day bounds in UTC
    try:
        zone = pytz.timezone(tz)
    except pytz.UnknownTimeZoneError:
        raise HTTPException(status_code=400, detail="Unknown timezone")
    # parse the date, localize to midnight
    local_start = zone.localize(datetime.fromisoformat(date))
    local_end = local_start.replace(hour=23, minute=59, second=59)
    # convert to UTC
    start_utc = local_start.astimezone(pytz.utc)
    end_utc = local_end.astimezone(pytz.utc)

    # 3. Load & filter all JSON files
    points = []
    for path in storage_dir.glob("*.json"):
        payload = json.load(open(path, encoding="utf-8"))
        # assume payload["features"] is a list of GeoJSON Features
        for feature in payload.get("features", []):
            ts = date_parser.isoparse(feature["properties"].get("timestamp"))
            if start_utc <= ts <= end_utc:
                points.append(feature)

    # 4. Return results
    if format == "full":
        return {"type": "FeatureCollection", "features": points}

    # 5. Combine into a LineString if requested
    coords = [feat["geometry"]["coordinates"] for feat in points]
    line = LineString(coords)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": list(line.coords)},
        "properties": {"date": date, "count": len(coords)},
    }


@app.get("/api/last")
async def get_last(token: str = Query(...)):
    # 1. Validate token
    if token != settings.read_token:
        raise HTTPException(status_code=401, detail="Invalid read token")

    # 2. Find the newest timestamp across all files
    latest_feature = None
    latest_ts = None
    for path in storage_dir.glob("*.json"):
        payload = json.load(open(path, encoding="utf-8"))
        for feat in payload.get("features", []):
            ts = date_parser.isoparse(feat["properties"].get("timestamp"))
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
                latest_feature = feat

    if not latest_feature:
        raise HTTPException(status_code=404, detail="No data found")

    return latest_feature

@app.get("/api/find-from-localtime")
async def find_from_local(
    token: str = Query(...),
    datetime_str: str = Query(..., description="YYYY-MM-DDTHH:MM:SS"),
    tz: str = Query("UTC", description="Timezone for the provided datetime"),
):
    # 1. Validate token
    if token != settings.read_token:
        raise HTTPException(status_code=401, detail="Invalid read token")

    # 2. Parse & convert the cutoff time
    try:
        zone = pytz.timezone(tz)
    except pytz.UnknownTimeZoneError:
        raise HTTPException(status_code=400, detail="Unknown timezone")
    local_dt = datetime.fromisoformat(datetime_str)
    local_cutoff = zone.localize(local_dt)
    cutoff_utc = local_cutoff.astimezone(pytz.utc)

    # 3. Load & filter all JSON files
    results = []
    for path in storage_dir.glob("*.json"):
        payload = json.load(open(path, encoding="utf-8"))
        for feat in payload.get("features", []):
            ts = date_parser.isoparse(feat["properties"].get("timestamp"))
            if ts >= cutoff_utc:
                results.append(feat)

    return {"type": "FeatureCollection", "features": results}
