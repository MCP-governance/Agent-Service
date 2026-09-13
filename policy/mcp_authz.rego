package mcp.authz

default allow := false

allow if {
    input.user_id == "user-test-001"
    input.agent_id == "document-agent-test"
    input.server_id == "file-mcp"
    input.tool_name == "read_file"
    input.arguments.path == "/data/public/notice.txt"
}
