# OPA 간단 정책 적용 방법

현재 Agent Service는 자연어 키워드를 판단하거나 Tool Call로 변환하지 않는다.
인증된 세션의 구조화된 Tool Call을 MCP Gateway로 그대로 전달한다.

- `/data/public/notice.txt` 읽기는 OPA가 허용한다.
- `/data/sensitive/secret.txt` 읽기는 OPA가 차단한다.
- 그 밖의 요청은 현재 OPA 정책에서 허용하지 않는다.

OPA는 자연어 문장을 직접 판단하지 않는다. 테스트 호출자 또는 향후 AI Agent가 만든
구조화된 Tool Call을 판단한다. Agent Service는 이 요청의 신원과 세션만 검증한다.

```text
구조화된 Tool Call 요청
→ Agent Service가 신원과 세션 검증
→ Agent Service가 Tool Call 전달
→ MCP Gateway가 OPA에 JSON 입력 전달
→ OPA가 true 또는 false 반환
→ MCP Gateway가 실행 또는 차단
```

## Ubuntu 적용

프로젝트 폴더에서 컨테이너를 다시 생성한다.

```bash
cd ~/bob-mcp-testbed
sudo docker compose pull opa
sudo docker compose up -d --build
sudo docker compose ps
```

OPA 정책 단위 테스트를 실행한다.

```bash
sudo docker compose run --rm opa test /policy /tests -v
```

세 개의 테스트가 PASS로 표시되어야 한다.

## 로그 확인

```bash
sudo docker compose logs --tail=100 opa gateway agent-service
```

공개 문서 요청의 Gateway 로그에는 다음 정보가 나타나야 한다.

```text
decision: allow
policy_id: opa-mcp-file-read-v1
```

민감 문서 요청의 Gateway 로그에는 다음 정보가 나타나야 한다.

```text
decision: deny
policy_id: opa-mcp-file-read-v1
```

OPA가 중지되거나 올바른 결과를 반환하지 않으면 Gateway는 기본 차단한다.

## curl로 전체 흐름 확인

먼저 테스트 계정으로 로그인하여 세션 ID를 발급받는다.

```bash
curl -s -X POST http://127.0.0.1:8000/auth/mock-login \
  -H 'Content-Type: application/json' \
  -d '{"email":"miso@bob.local","password":"test-password"}'
```

응답의 `session_id` 값을 아래 `발급받은-세션-ID` 자리에 입력한다.
테스트 Token은 현재 `test-user-token`으로 고정되어 있다.

```bash
curl -s -X POST http://127.0.0.1:8000/agent/tool-call \
  -H 'Authorization: Bearer test-user-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id":"발급받은-세션-ID",
    "server_id":"file-mcp",
    "tool_name":"read_file",
    "arguments":{"path":"/data/public/notice.txt"}
  }'
```

정상 흐름은 다음과 같다.

```text
curl
→ Agent Service의 Token 및 세션 검증
→ MCP Gateway
→ OPA 정책 판단
→ Mock MCP의 read_file 실행
→ 파일 내용 반환
```

존재하지 않는 세션 ID를 사용하면 Agent Service가 HTTP 401로 차단한다.
`/data/sensitive/secret.txt`를 요청하면 Agent Service는 요청을 전달하지만,
MCP Gateway와 OPA가 Tool 실행 전에 차단한다.
