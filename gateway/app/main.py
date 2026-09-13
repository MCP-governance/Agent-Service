import os
import time
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="MCP Security Gateway",
    version="0.2.0",
)

FILE_MCP_URL = os.getenv(
    "FILE_MCP_URL",
    "http://mock-mcp:9000",
)

OPA_DECISION_URL = os.getenv(
    "OPA_DECISION_URL",
    "http://opa:8181/v1/data/mcp/authz/allow",
)


class ToolCallRequest(BaseModel):
    request_id: str
    session_id: str
    user_id: str
    agent_id: str
    server_id: str
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    request_id: str
    tool_call_id: str
    decision: Literal["allow", "deny"]
    policy_id: str
    reason: str
    execution_status: Literal[
        "success",
        "blocked",
        "failed",
    ]
    tool_result: dict[str, Any] | None = None
    latency_ms: float


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "gateway",
    }


async def evaluate_opa_policy(
    request: ToolCallRequest,
) -> tuple[str, str]:
    policy_input = {
        "request_id": request.request_id,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "agent_id": request.agent_id,
        "server_id": request.server_id,
        "tool_call_id": request.tool_call_id,
        "tool_name": request.tool_name,
        "arguments": request.arguments,
    }

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                OPA_DECISION_URL,
                json={"input": policy_input},
            )
            response.raise_for_status()
            opa_response = response.json()

    except httpx.RequestError as error:
        return (
            "deny",
            f"OPA 연결 실패로 기본 차단: {error}",
        )

    except httpx.HTTPStatusError as error:
        return (
            "deny",
            "OPA 오류 응답으로 기본 차단: "
            f"{error.response.status_code}",
        )

    except ValueError:
        return (
            "deny",
            "OPA 응답을 해석할 수 없어 기본 차단",
        )

    result = opa_response.get("result")

    if result is True:
        return (
            "allow",
            "OPA가 공개 문서 읽기를 허용함",
        )

    if result is False:
        return (
            "deny",
            "OPA 정책에서 허용하지 않은 요청",
        )

    return (
        "deny",
        "OPA 정책 결과가 없어 기본 차단",
    )


async def execute_read_file(
    request: ToolCallRequest,
) -> dict[str, Any]:
    mcp_request = {
        "request_id": request.request_id,
        "tool_call_id": request.tool_call_id,
        "path": request.arguments["path"],
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            f"{FILE_MCP_URL}/tools/read-file",
            json=mcp_request,
        )
        response.raise_for_status()
        return response.json()


@app.post(
    "/tool-call",
    response_model=DecisionResponse,
)
async def evaluate_tool_call(
    request: ToolCallRequest,
) -> DecisionResponse:
    started_at = time.perf_counter()

    decision, reason = await evaluate_opa_policy(
        request,
    )

    tool_result = None

    if decision == "deny":
        execution_status = "blocked"

    else:
        try:
            tool_result = await execute_read_file(
                request,
            )
            execution_status = "success"

        except httpx.RequestError as error:
            execution_status = "failed"
            reason = (
                "정책은 허용했지만 Mock MCP 연결에 실패함: "
                f"{error}"
            )

        except httpx.HTTPStatusError as error:
            execution_status = "failed"
            reason = (
                "정책은 허용했지만 Mock MCP가 오류를 반환함: "
                f"{error.response.status_code}"
            )

    latency_ms = round(
        (time.perf_counter() - started_at) * 1000,
        3,
    )

    print(
        {
            "event": "gateway_result",
            "request_id": request.request_id,
            "tool_call_id": request.tool_call_id,
            "user_id": request.user_id,
            "agent_id": request.agent_id,
            "server_id": request.server_id,
            "tool_name": request.tool_name,
            "decision": decision,
            "reason": reason,
            "execution_status": execution_status,
            "latency_ms": latency_ms,
        },
        flush=True,
    )

    return DecisionResponse(
        request_id=request.request_id,
        tool_call_id=request.tool_call_id,
        decision=decision,
        policy_id="opa-mcp-file-read-v1",
        reason=reason,
        execution_status=execution_status,
        tool_result=tool_result,
        latency_ms=latency_ms,
    )
