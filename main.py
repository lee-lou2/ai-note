import os
import httpx
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
BASIC_AUTH_USERNAME = os.getenv("BASIC_AUTH_USERNAME", "admin")
BASIC_AUTH_PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "change-me")

app = FastAPI(title="Realtime Speech to Text")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()


def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username, BASIC_AUTH_USERNAME
    )
    correct_password = secrets.compare_digest(
        credentials.password, BASIC_AUTH_PASSWORD
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


class ScribeTokenResponse(BaseModel):
    token: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", dependencies=[Depends(verify_basic_auth)])
async def index():
    return FileResponse("static/index.html")


@app.get(
    "/scribe-token",
    response_model=ScribeTokenResponse,
    dependencies=[Depends(verify_basic_auth)]
)
async def get_scribe_token() -> dict:
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is not set")

    url = "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"xi-api-key": ELEVENLABS_API_KEY},
            )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Error contacting ElevenLabs: {e}"
        ) from e

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"ElevenLabs error: {resp.text}",
        )

    data = resp.json()
    token = data.get("token")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="Token missing in ElevenLabs response"
        )

    return {"token": token}


app.mount("/static", StaticFiles(directory="static"), name="static")
