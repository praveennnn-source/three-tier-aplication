// ---- Configuration ----
// When you deploy the backend (EC2 / behind an ALB), change this to that URL, e.g.
// const API_BASE = "http://your-alb-dns-name/api";
const API_BASE = "http://localhost:5000/api";

// ---- Element refs ----
const viewLogin = document.getElementById("view-login");
const viewRegister = document.getElementById("view-register");
const viewDashboard = document.getElementById("view-dashboard");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const noteForm = document.getElementById("note-form");

const loginMsg = document.getElementById("login-msg");
const registerMsg = document.getElementById("register-msg");
const dashMsg = document.getElementById("dash-msg");

const dashUsername = document.getElementById("dash-username");
const notesList = document.getElementById("notes-list");
const logoutBtn = document.getElementById("logout-btn");

document.getElementById("go-register").addEventListener("click", (e) => {
  e.preventDefault();
  showView("register");
});
document.getElementById("go-login").addEventListener("click", (e) => {
  e.preventDefault();
  showView("login");
});

function showView(name) {
  viewLogin.classList.add("hidden");
  viewRegister.classList.add("hidden");
  viewDashboard.classList.add("hidden");
  loginMsg.textContent = "";
  registerMsg.textContent = "";
  if (name === "login") viewLogin.classList.remove("hidden");
  if (name === "register") viewRegister.classList.remove("hidden");
  if (name === "dashboard") viewDashboard.classList.remove("hidden");
}

function setMsg(el, text, ok) {
  el.textContent = text;
  el.className = "msg " + (ok ? "ok" : "err");
}

function getToken() { return localStorage.getItem("token"); }
function setToken(t) { localStorage.setItem("token", t); }
function clearToken() { localStorage.removeItem("token"); }
function getUsername() { return localStorage.getItem("username"); }
function setUsername(u) { localStorage.setItem("username", u); }

// ---- Register ----
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("reg-username").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value;

  try {
    const res = await fetch(`${API_BASE}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMsg(registerMsg, data.error || "Registration failed", false);
      return;
    }
    setMsg(registerMsg, "Account created. You can sign in now.", true);
    registerForm.reset();
    setTimeout(() => showView("login"), 900);
  } catch (err) {
    setMsg(registerMsg, "Could not reach the server. Is the backend running?", false);
  }
});

// ---- Login ----
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMsg(loginMsg, data.error || "Login failed", false);
      return;
    }
    setToken(data.token);
    setUsername(data.username);
    loginForm.reset();
    enterDashboard();
  } catch (err) {
    setMsg(loginMsg, "Could not reach the server. Is the backend running?", false);
  }
});

// ---- Dashboard ----
async function enterDashboard() {
  dashUsername.textContent = getUsername() || "";
  showView("dashboard");
  await loadNotes();
}

async function authedFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers, {
    Authorization: `Bearer ${getToken()}`,
  });
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    showView("login");
    setMsg(loginMsg, "Session expired. Please sign in again.", false);
    throw new Error("unauthorized");
  }
  return res;
}

async function loadNotes() {
  try {
    const res = await authedFetch("/notes");
    const data = await res.json();
    renderNotes(data.notes || []);
  } catch (err) {
    // already handled by authedFetch on 401
  }
}

function renderNotes(notes) {
  notesList.innerHTML = "";
  if (notes.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No notes yet — add your first one above.";
    notesList.appendChild(li);
    return;
  }
  for (const n of notes) {
    const li = document.createElement("li");
    const time = new Date(n.created_at).toLocaleString();
    li.innerHTML = `${escapeHtml(n.content)}<span class="note-time">${time}</span>`;
    notesList.appendChild(li);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

noteForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("note-input");
  const content = input.value.trim();
  if (!content) return;
  try {
    const res = await authedFetch("/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const data = await res.json();
      setMsg(dashMsg, data.error || "Could not add note", false);
      return;
    }
    input.value = "";
    setMsg(dashMsg, "", true);
    await loadNotes();
  } catch (err) {
    // handled above
  }
});

logoutBtn.addEventListener("click", () => {
  clearToken();
  localStorage.removeItem("username");
  showView("login");
});

// ---- Boot ----
(function init() {
  if (getToken()) {
    enterDashboard();
  } else {
    showView("login");
  }
})();
