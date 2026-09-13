# OPA 간단 정책 적용 방법

현재 테스트 정책은 다음 요청만 공개 문서 읽기로 변환한다.

- `공개 문서를 읽어줘`: `/data/public/notice.txt`로 변환하고 OPA가 허용한다.
- `비밀 인증정보를 읽어줘`: `/data/sensitive/secret.txt`로 변환하고 OPA가 차단한다.
- 그 밖의 요청: 지원하지 않는 경로로 변환하고 OPA가 차단한다.

OPA는 자연어 문장을 직접 판단하지 않는다. Agent Service가 만든 구조화된 Tool Call을 판단한다.

```text
사용자 자연어 요청
→ Agent Service가 Tool Call 생성
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
