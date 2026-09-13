package mcp.authz_test

import data.mcp.authz.allow

test_public_document_is_allowed if {
    allow with input as {
        "user_id": "user-test-001",
        "agent_id": "document-agent-test",
        "server_id": "file-mcp",
        "tool_name": "read_file",
        "arguments": {
            "path": "/data/public/notice.txt",
        },
    }
}

test_sensitive_document_is_denied if {
    not allow with input as {
        "user_id": "user-test-001",
        "agent_id": "document-agent-test",
        "server_id": "file-mcp",
        "tool_name": "read_file",
        "arguments": {
            "path": "/data/sensitive/secret.txt",
        },
    }
}

test_unknown_request_is_denied if {
    not allow with input as {
        "user_id": "user-test-001",
        "agent_id": "document-agent-test",
        "server_id": "file-mcp",
        "tool_name": "read_file",
        "arguments": {
            "path": "/data/unsupported/request.txt",
        },
    }
}
