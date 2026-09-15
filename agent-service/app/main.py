import os
import secrets
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="Agent Service",
    version="0.1.0",
)

GATEWAY_URL = os.getenv(
    "GATEWAY_URL",
    "http://gateway:8080",
)

TEST_USER_TOKEN = os.getenv(
    "TEST_USER_TOKEN",
    "test-user-token",
)

MOCK_SSO_EMAIL = os.getenv(
    "MOCK_SSO_EMAIL",
    "miso@bob.local",
)

MOCK_SSO_PASSWORD = os.getenv(
    "MOCK_SSO_PASSWORD",
    "test-password",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


class AgentToolCallRequest(BaseModel):
    session_id: str
    server_id: str
    tool_name: str
    arguments: dict


class AgentToolCallResponse(BaseModel):
    request_id: str
    session_id: str
    status: str
    message: str
    tool_call: dict
    gateway_result: dict


class MockLoginRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    department: str
    roles: list[str]


class MockLoginResponse(BaseModel):
    access_token: str
    token_type: str
    session_id: str
    user: UserProfile


TEST_USER = UserProfile(
    user_id="user-test-001",
    email=MOCK_SSO_EMAIL,
    name="김미소",
    department="보안기술팀",
    roles=["analyst"],
)

ACTIVE_SESSIONS: dict[str, str] = {}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/login")


@app.get("/login", include_in_schema=False)
async def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/workspace", include_in_schema=False)
async def workspace_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "workspace.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "agent-service",
    }


def authenticate(authorization: str | None) -> UserProfile:
    expected = f"Bearer {TEST_USER_TOKEN}"

    if authorization is None or not secrets.compare_digest(
        authorization,
        expected,
    ):
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 인증 Token",
        )

    return TEST_USER


@app.post(
    "/auth/mock-login",
    response_model=MockLoginResponse,
)
async def mock_login(
    request: MockLoginRequest,
) -> MockLoginResponse:
    email_matches = secrets.compare_digest(
        request.email.strip().lower(),
        MOCK_SSO_EMAIL.lower(),
    )
    password_matches = secrets.compare_digest(
        request.password,
        MOCK_SSO_PASSWORD,
    )

    if not email_matches or not password_matches:
        raise HTTPException(
            status_code=401,
            detail="회사 계정 또는 비밀번호를 확인해주세요.",
        )

    session_id = str(uuid.uuid4())
    ACTIVE_SESSIONS[session_id] = TEST_USER.user_id

    print(
        {
            "event": "mock_sso_login_succeeded",
            "user_id": TEST_USER.user_id,
            "email": TEST_USER.email,
            "session_id": session_id,
        },
        flush=True,
    )

    return MockLoginResponse(
        access_token=TEST_USER_TOKEN,
        token_type="bearer",
        session_id=session_id,
        user=TEST_USER,
    )


@app.get("/auth/me", response_model=UserProfile)
async def current_user(
    authorization: str | None = Header(default=None),
) -> UserProfile:
    return authenticate(authorization)


def validate_session(user: UserProfile, session_id: str) -> None:
    session_user_id = ACTIVE_SESSIONS.get(session_id)

    if session_user_id != user.user_id:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않거나 만료된 세션",
        )


@app.post(
    "/agent/tool-call",
    response_model=AgentToolCallResponse,
)
async def forward_tool_call(
    request: AgentToolCallRequest,
    authorization: str | None = Header(default=None),
) -> AgentToolCallResponse:
    user = authenticate(authorization)
    validate_session(user, request.session_id)
    user_id = user.user_id

    request_id = str(uuid.uuid4())
    tool_call_id = str(uuid.uuid4())

    gateway_request = {
        "request_id": request_id,
        "session_id": request.session_id,
        "user_id": user_id,
        "agent_id": "document-agent-test",
        "server_id": request.server_id,
        "tool_call_id": tool_call_id,
        "tool_name": request.tool_name,
        "arguments": request.arguments,
    }

    print(
        {
            "event": "authenticated_tool_call_received",
            "request_id": request_id,
            "session_id": request.session_id,
            "user_id": user_id,
            "server_id": request.server_id,
            "tool_name": request.tool_name,
        },
        flush=True,
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/tool-call",
                json=gateway_request,
            )
            response.raise_for_status()

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Gateway 연결 실패: {error}",
        ) from error

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Gateway가 오류 상태를 반환함: "
                f"{error.response.status_code}"
            ),
        ) from error

    gateway_result = response.json()
    decision = gateway_result["decision"]

    if decision == "allow":
        status = "allowed"
        response_message = (
            "Gateway가 Tool Call을 허용했습니다. "
            "테스트용 Mock MCP가 요청을 실행했습니다."
        )
    else:
        status = "blocked"
        response_message = (
            "Gateway가 Tool Call을 차단했습니다."
        )

    return AgentToolCallResponse(
        request_id=request_id,
        session_id=request.session_id,
        status=status,
        message=response_message,
        tool_call={
            "tool_call_id": tool_call_id,
            "server_id": request.server_id,
            "tool_name": request.tool_name,
            "arguments": request.arguments,
        },
        gateway_result=gateway_result,
    )
