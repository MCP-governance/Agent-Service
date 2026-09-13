const TOKEN_KEY = "bob_mock_sso_token";
const token = sessionStorage.getItem(TOKEN_KEY);

const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send-button");
const resultPanel = document.querySelector("#result-panel");
let currentUser = null;

function redirectToLogin() {
  sessionStorage.removeItem(TOKEN_KEY);
  window.location.replace("/login");
}

async function loadCurrentUser() {
  if (!token) {
    redirectToLogin();
    return;
  }

  const response = await fetch("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    redirectToLogin();
    return;
  }

  currentUser = await response.json();
  document.querySelector("#user-name").textContent = currentUser.name;
  document.querySelector("#user-department").textContent = currentUser.department;
  document.querySelector("#user-avatar").textContent = currentUser.name.slice(0, 1);
}

function renderResult(body) {
  const decision = body.gateway_result?.decision || "unknown";
  const badge = document.querySelector("#decision-badge");
  const allowed = decision === "allow";

  resultPanel.classList.remove("hidden", "allowed", "blocked");
  resultPanel.classList.add(allowed ? "allowed" : "blocked");
  badge.className = `decision-badge ${allowed ? "allowed" : "blocked"}`;
  badge.textContent = allowed ? "ALLOW" : "DENY";

  document.querySelector("#result-title").textContent = allowed
    ? "요청을 허용했습니다"
    : "요청을 차단했습니다";
  document.querySelector("#result-message").textContent = body.message;
  document.querySelector("#result-user").textContent = currentUser.user_id;
  document.querySelector("#result-request-id").textContent = body.request_id;
  document.querySelector("#result-tool").textContent = body.tool_call?.tool_name || "-";
  document.querySelector("#result-path").textContent =
    body.tool_call?.arguments?.path || "-";
  document.querySelector("#result-json").textContent = JSON.stringify(body, null, 2);
  resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function sendPrompt() {
  const message = promptInput.value.trim();

  if (!message) {
    promptInput.focus();
    return;
  }

  sendButton.disabled = true;
  sendButton.textContent = "정책 확인 중";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    if (response.status === 401) {
      redirectToLogin();
      return;
    }

    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.detail || "요청 처리에 실패했습니다.");
    }

    renderResult(body);
  } catch (error) {
    resultPanel.classList.remove("hidden", "allowed");
    resultPanel.classList.add("blocked");
    document.querySelector("#result-title").textContent = "요청 처리 오류";
    document.querySelector("#result-message").textContent = error.message;
    document.querySelector("#decision-badge").textContent = "ERROR";
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "요청 보내기";
  }
}

document.querySelectorAll(".example-button").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});

document.querySelector("#logout-button").addEventListener("click", redirectToLogin);
sendButton.addEventListener("click", sendPrompt);
promptInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    sendPrompt();
  }
});

loadCurrentUser().catch(redirectToLogin);
