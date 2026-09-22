import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Bot,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Send,
  Trash2,
  User,
  X,
  LogOut,
} from "lucide-react";
import {
  signInWithPopup,
  signOut,
  onAuthStateChanged,
} from "firebase/auth";
import { auth, googleProvider } from "./firebase";
import { api } from "./api";

const STORAGE_KEY = "ai-tour-planner-session";

const newId = () =>
  crypto?.randomUUID?.() ||
  `${Date.now()}-${Math.random().toString(16).slice(2)}`;

function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(
    sessionStorage.getItem(STORAGE_KEY)
  );
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) || null,
    [sessions, activeId]
  );

  /* Firebase authentication */
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setAuthLoading(false);
    });

    return unsubscribe;
  }, []);

  /* Load sessions after login */
  useEffect(() => {
    if (user) {
      refreshSessions();
    } else {
      setSessions([]);
      setMessages([]);
      setActiveId(null);
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, [user]);

  async function refreshSessions(preferredId = null) {
    try {
      const data = await api.sessions();
      const list = data.sessions || [];

      setSessions(list);

      const storedId = sessionStorage.getItem(STORAGE_KEY);

      const candidateId =
        preferredId || activeId || storedId;

      const selected =
        list.find((s) => s.id === candidateId)?.id || null;

      setActiveId(selected);

      if (selected) {
        sessionStorage.setItem(STORAGE_KEY, selected);
        await loadMessages(selected);
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
        setMessages([]);
      }
    } catch (e) {
      setError(e.message);
    }
  }

  async function loadMessages(id) {
    if (!id) {
      setMessages([]);
      return;
    }

    try {
      const data = await api.messages(id);

      setMessages(data.messages || []);
      setError("");
    } catch (e) {
      setError(e.message);
      setMessages([]);
      sessionStorage.removeItem(STORAGE_KEY);
      setActiveId(null);
    }
  }

  function selectSession(id) {
    setActiveId(id);
    setSidebarOpen(false);
    setError("");

    sessionStorage.setItem(STORAGE_KEY, id);

    loadMessages(id);
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  function createChat() {
    const id = newId();

    setActiveId(id);
    setMessages([]);
    setInput("");
    setError("");
    setSidebarOpen(false);

    sessionStorage.setItem(STORAGE_KEY, id);
  }

  async function handleGoogleLogin() {
    try {
      setError("");

      await signInWithPopup(
        auth,
        googleProvider
      );
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleLogout() {
    try {
      await signOut(auth);

      setSessions([]);
      setMessages([]);
      setActiveId(null);
      setInput("");

      sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      setError(e.message);
    }
  }

  async function sendMessage() {
    const text = input.trim();

    if (!text || loading || !user) return;

    let sessionId = activeId;

    if (!sessionId) {
      sessionId = newId();

      setActiveId(sessionId);

      sessionStorage.setItem(
        STORAGE_KEY,
        sessionId
      );
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      },
    ]);

    setInput("");
    setLoading(true);
    setError("");

    try {
      const data = await api.chat(
        sessionId,
        text
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          created_at: new Date().toISOString(),
        },
      ]);

      await refreshSessions(
        data.session_id
      );
    } catch (e) {
      setError(e.message);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "I couldn't complete that request. Please try again.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  async function deleteSession(sessionId) {
    if (!sessionId || loading) return;

    try {
      await api.deleteSession(sessionId);

      const remaining = sessions.filter(
        (s) => s.id !== sessionId
      );

      setSessions(remaining);

      if (sessionId === activeId) {
        if (remaining.length > 0) {
          const nextId = remaining[0].id;

          setActiveId(nextId);

          sessionStorage.setItem(
            STORAGE_KEY,
            nextId
          );

          await loadMessages(nextId);
        } else {
          setActiveId(null);
          setMessages([]);

          sessionStorage.removeItem(
            STORAGE_KEY
          );
        }
      }
    } catch (e) {
      setError(e.message);
    }
  }

  const keyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  /* Centered loading screen */
  if (authLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <div className="welcome-icon">
            <Bot size={28} />
          </div>

          <h1>Loading VoyageAI...</h1>
        </div>
      </div>
    );
  }

  /* Login screen */
  if (!user) {
    return (
      <div className="app-shell">
        <main className="chat-shell">
          <section className="messages">
            <div className="welcome">
              <div className="welcome-icon">
                <Bot size={28} />
              </div>

              <h1>Welcome to VoyageAI</h1>

              <p>
                Your intelligent travel planner for
                destinations, trains, hotels, food,
                routes, weather and complete
                itineraries.
              </p>

              {error && (
                <div className="error-banner">
                  {error}
                </div>
              )}

              <button
                type="button"
                className="google-login-btn"
                onClick={handleGoogleLogin}
              >
                <svg
                  className="google-icon"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    fill="#4285F4"
                    d="M21.35 12.27c0-.71-.06-1.39-.18-2.05H12v3.88h5.24a4.48 4.48 0 0 1-1.95 2.94v2.45h3.16c1.85-1.7 2.9-4.2 2.9-7.22Z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 21.8c2.64 0 4.86-.87 6.48-2.36l-3.16-2.45c-.88.59-2 .94-3.32.94-2.55 0-4.71-1.72-5.49-4.03H3.25v2.53A9.79 9.79 0 0 0 12 21.8Z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M6.51 13.9a5.9 5.9 0 0 1 0-3.78V7.59H3.25a9.8 9.8 0 0 0 0 8.84l3.26-2.53Z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 6.09c1.44 0 2.73.5 3.75 1.48l2.81-2.81C16.86 3.21 14.64 2.3 12 2.3a9.79 9.79 0 0 0-8.75 5.29l3.26 2.53C7.29 7.81 9.45 6.09 12 6.09Z"
                  />
                </svg>

                <span>Continue with Google</span>
              </button>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside
        className={`sidebar ${
          sidebarOpen ? "open" : ""
        }`}
      >
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-mark">
              <Bot size={18} />
            </div>

            <div>
              <div className="brand-name">
                VoyageAI
              </div>

              <div className="brand-sub">
                Your Intelligent Travel Planner
              </div>
            </div>
          </div>

          <button
            className="icon-btn mobile-close"
            onClick={() =>
              setSidebarOpen(false)
            }
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-chat-btn"
          onClick={createChat}
        >
          <Plus size={18} />
          New chat
        </button>

        <div className="history-label">
          Chats
        </div>

        <div className="session-list">
          {sessions.length === 0 ? (
            <div className="empty-side">
              No previous chats
            </div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`session-item ${
                  s.id === activeId
                    ? "active"
                    : ""
                }`}
              >
                <button
                  className="session-main"
                  onClick={() =>
                    selectSession(s.id)
                  }
                >
                  <MessageSquare size={16} />

                  <span>
                    {s.name || "New Chat"}
                  </span>
                </button>

                <button
                  className="session-delete"
                  title="Delete chat"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        <div style={{ marginTop: "auto" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "10px 6px",
              marginBottom: "6px",
            }}
          >
            {user.photoURL ? (
              <img
                src={user.photoURL}
                alt="Profile"
                style={{
                  width: "30px",
                  height: "30px",
                  borderRadius: "50%",
                }}
              />
            ) : (
              <User size={18} />
            )}

            <div
              style={{
                minWidth: 0,
                flex: 1,
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {user.displayName || "User"}
              </div>

              <div
                style={{
                  fontSize: "11px",
                  color: "#888",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {user.email}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="signout-btn"
            onClick={handleLogout}
          >
            <LogOut size={16} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <div
          className="backdrop"
          onClick={() =>
            setSidebarOpen(false)
          }
        />
      )}

      <main className="chat-shell">
        <header className="topbar">
          <button
            className="icon-btn mobile-menu"
            onClick={() =>
              setSidebarOpen(true)
            }
          >
            <Menu size={20} />
          </button>

          <div className="top-title">
            {activeSession?.name ||
              "VoyageAI"}
          </div>

          <button className="icon-btn">
            <MoreHorizontal size={20} />
          </button>
        </header>

        <section className="messages">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">
                <Bot size={28} />
              </div>

              <h1>Plan your next trip</h1>

              <p>
                Ask about destinations, trains,
                hotels, food, routes, weather
                and complete itineraries.
              </p>

              <div className="suggestions">
                <button
                  onClick={() =>
                    setInput(
                      "Plan a 4-day trip from Bengaluru to Jaipur by train with budget hotels and local food."
                    )
                  }
                >
                  Bengaluru → Jaipur
                </button>

                <button
                  onClick={() =>
                    setInput(
                      "Plan a 5-day Madurai trip focused on temples and local food."
                    )
                  }
                >
                  Madurai food & temples
                </button>

                <button
                  onClick={() =>
                    setInput(
                      "Plan a budget 3-day Kanchipuram trip with nearby temples."
                    )
                  }
                >
                  Kanchipuram temples
                </button>
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                className={`message-row ${m.role}`}
                key={`${m.created_at || ""}-${i}`}
              >
                <div
                  className={`avatar ${m.role}`}
                >
                  {m.role === "user" ? (
                    <User size={16} />
                  ) : (
                    <Bot size={16} />
                  )}
                </div>

                <div
                  className={`message-content ${
                    m.error ? "error" : ""
                  }`}
                >
                  {m.role === "assistant" ? (
                    <ReactMarkdown>
                      {m.content}
                    </ReactMarkdown>
                  ) : (
                    <div className="plain-text">
                      {m.content}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="message-row assistant">
              <div className="avatar assistant">
                <Bot size={16} />
              </div>

              <div className="typing">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </section>

        <div className="composer-wrap">
          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          <div className="composer">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) =>
                setInput(e.target.value)
              }
              onKeyDown={keyDown}
              placeholder="Message VoyageAI..."
              rows={1}
              disabled={loading}
            />

            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={
                !input.trim() || loading
              }
            >
              <Send size={17} />
            </button>
          </div>

          <div className="composer-note">
            VoyageAI can use real travel tools
            to build your plan.
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;