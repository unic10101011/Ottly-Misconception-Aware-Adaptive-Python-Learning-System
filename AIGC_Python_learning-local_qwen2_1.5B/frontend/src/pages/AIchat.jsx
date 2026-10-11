import React, { useState, useEffect, useRef } from 'react';
import chathaita from './images/chathaita.png';
import yonghu from './images/yonghu.png';
import chatbeijing from './images/chatbeijing.png'; // 背景图

const AIchat = () => {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([
    { content: "你好呀，我是小海獭，请问有什么可以帮助你的呢？", isUser: false },
  ]);
  const [history, setHistory] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [typing, setTyping] = useState(false);
  const [question, setQuestion] = useState("");
  const [activeTab, setActiveTab] = useState("chat");
  const [selectedSessionFilter, setSelectedSessionFilter] = useState("");
  const chatBodyRef = useRef(null);
  const pageSize = 10;

  // ====================== 后端接口 完全原封不动 ======================
  useEffect(() => {
    loadSessions();
    loadHistory();
  }, []);

  const loadSessions = async () => {
    try {
      const response = await fetch("/api/v1/ai/sessions", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("获取会话列表失败");
      const data = await response.json();
      if (data.code === 200) setSessions(data.data.sessions);
    } catch (error) {
      console.error("加载会话失败:", error);
    }
  };

  const loadHistory = async (page = currentPage, sessionId = selectedSessionFilter) => {
    try {
      const url = `/api/v1/ai/history?page=${page}&page_size=${pageSize}${
        sessionId ? `&session_id=${sessionId}` : ""
      }`;
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("获取历史记录失败");
      const data = await response.json();
      if (data.code === 200) {
        setHistory(data.data);
        setTotalPages(Math.ceil(data.total / pageSize));
      }
    } catch (error) {
      console.error("加载历史记录失败:", error);
    }
  };

  const loadSessionHistory = async (sessionId) => {
    try {
      const response = await fetch(
        `/api/v1/ai/history?session_id=${sessionId}&page=1&page_size=100`,
        {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        }
      );
      if (!response.ok) throw new Error("获取会话历史失败");
      const data = await response.json();
      if (data.code === 200) {
        const records = data.data;
        const newMessages = [];
        records.reverse().forEach((record) => {
          newMessages.push({ content: record.question, isUser: true });
          newMessages.push({ content: record.answer, isUser: false });
        });
        if (records.length === 0) {
          newMessages.push({
            content: "你好呀，我是小海獭，请问有什么可以帮助你的呢？",
            isUser: false,
          });
        }
        setMessages(newMessages);
      }
    } catch (error) {
      console.error("加载会话历史失败:", error);
    }
  };

  const selectSession = (sessionId) => {
    setCurrentSessionId(sessionId);
    loadSessionHistory(sessionId);
  };

  const createNewSession = () => {
    setCurrentSessionId(null);
    setMessages([{ content: "你好呀，我是小海獭，请问有什么可以帮助你的呢？", isUser: false }]);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    const newMessages = [...messages, { content: question, isUser: true }, { content: "", isUser: false }];
    setMessages(newMessages);
    setQuestion("");
    setTyping(true);

    try {
      const response = await fetch("/api/v1/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        body: JSON.stringify({ question, stream: true, session_id: currentSessionId }),
      });

      if (!response.ok) throw new Error("API请求失败");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = "";
      let sessionIdFromResponse = currentSessionId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.substring(6);
            if (data) {
              try {
                const json = JSON.parse(data);
                if (json.content) {
                  if (json.content === "[END]") break;
                  fullAnswer += json.content;
                  setTyping(false);
                  setMessages((prev) => [...prev.slice(0, -1), { content: fullAnswer, isUser: false }]);
                }
                if (json.session_id) sessionIdFromResponse = json.session_id;
              } catch (e) {
                console.error("解析JSON失败:", e);
              }
            }
          }
        }
      }

      if (!currentSessionId && sessionIdFromResponse) {
        setCurrentSessionId(sessionIdFromResponse);
        loadSessions();
      }
    } catch (error) {
      console.error("错误:", error);
      setTyping(false);
      setMessages((prev) => [...prev.slice(0, -1), { content: "抱歉，AI服务暂时不可用，请稍后再试。", isUser: false }]);
    }
  };

  const deleteHistoryRecord = async (recordId) => {
    if (!window.confirm("确定要删除这条记录吗？")) return;
    try {
      const response = await fetch(`/api/v1/ai/history/${recordId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("删除记录失败");
      const data = await response.json();
      if (data.code === 200) {
        loadHistory();
        loadSessions();
      }
    } catch (error) {
      console.error("删除历史记录失败:", error);
    }
  };

  const formatDateTime = (dateTimeString) => {
    const date = new Date(dateTimeString);
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  useEffect(() => {
    if (chatBodyRef.current) chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
  }, [messages, typing]);

  // ====================== 渲染界面 ======================
  return (
    // 根容器改为全宽全高，无左侧边栏
    <div style={{ width: "100%", height: "100%", margin: 0, overflow: "hidden", padding: 0 }}>
      {/* 右侧区域（现在是整个屏幕） */}
      <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", overflow: "hidden" }}>
        <ul className="nav nav-tabs" style={{ margin: 0, padding: 0, borderBottom: 0 }}>
          <li className="nav-item">
            <a
              className={`nav-link ${activeTab === "chat" ? "active" : ""}`}
              href="#"
              onClick={(e) => { e.preventDefault(); setActiveTab("chat"); }}
              style={{ padding: "8px 16px" }}
            >
              对话
            </a>
          </li>
          <li className="nav-item">
            <a
              className={`nav-link ${activeTab === "history" ? "active" : ""}`}
              href="#"
              onClick={(e) => { e.preventDefault(); setActiveTab("history"); }}
              style={{ padding: "8px 16px" }}
            >
              历史记录
            </a>
          </li>
        </ul>

        {/* 对话页面：背景铺满无留白 */}
        {activeTab === "chat" && (
          <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
            <div
              ref={chatBodyRef}
              style={{
                flex: 1,
                backgroundImage: `url(${chatbeijing})`,
                backgroundSize: "cover",
                backgroundRepeat: "no-repeat",
                backgroundPosition: "center 90%",
                padding: "16px",
                overflowY: "auto",
              }}
            >
              {messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    justifyContent: msg.isUser ? "flex-end" : "flex-start",
                    marginBottom: "12px",
                    alignItems: "flex-start",
                    gap: "8px",
                  }}
                >
                  {!msg.isUser && (
                    <img
                      src={chathaita}
                      alt="小海獭"
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "50%",
                        objectFit: "cover",
                        objectPosition: "center",
                      }}
                    />
                  )}
                  <div
                    style={{
                      maxWidth: "70%",
                      padding: "12px 16px",
                      borderRadius: msg.isUser ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
                      backgroundColor: msg.isUser ? "#409EFF" : "#fff",
                      color: msg.isUser ? "#fff" : "#333",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                      fontSize: "15px",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {msg.content}
                  </div>
                  {msg.isUser && (
                    <img
                      src={yonghu}
                      alt="用户"
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "50%",
                        objectFit: "cover",
                        objectPosition: "center",
                      }}
                    />
                  )}
                </div>
              ))}
              {typing && (
                <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "12px" }}>
                  <img
                    src={chathaita}
                    alt="小海獭"
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "50%",
                      objectFit: "cover",
                      objectPosition: "center",
                    }}
                  />
                  <div style={{ background: "#fff", padding: "12px 18px", borderRadius: "4px 16px 16px 16px" }}>
                    <span style={{ display: "inline-block", width: "8px", height: "8px", background: "#ccc", borderRadius: "50%", margin: "0 2px", animation: "typing 1.4s infinite ease-in-out" }}></span>
                    <span style={{ display: "inline-block", width: "8px", height: "8px", background: "#ccc", borderRadius: "50%", margin: "0 2px", animation: "typing 1.4s infinite ease-in-out 0.16s" }}></span>
                    <span style={{ display: "inline-block", width: "8px", height: "8px", background: "#ccc", borderRadius: "50%", margin: "0 2px", animation: "typing 1.4s infinite ease-in-out 0.32s" }}></span>
                  </div>
                </div>
              )}
            </div>

            {/* 底部输入框 */}
            <div
              style={{
                padding: "12px 16px",
                background: "#fff",
                borderTop: "1px solid #eee",
                display: "flex",
                gap: "10px",
                alignItems: "center",
              }}
            >
              <form onSubmit={sendMessage} style={{ flex: 1, display: "flex", gap: "10px" }}>
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="请输入消息..."
                  style={{ flex: 1, borderRadius: "24px", padding: "10px 16px", border: "1px solid #ddd", outline: "none" }}
                />
                <button
                  type="submit"
                  style={{ borderRadius: "24px", padding: "0 20px", background: "#409EFF", color: "#fff", border: "none" }}
                >
                  发送
                </button>
              </form>
            </div>
          </div>
        )}

        {/* 历史记录：背景铺满无留白 */}
        {activeTab === "history" && (
          <div
            className="p-4 d-flex flex-column"
            style={{
              flex: 1,
              backgroundImage: `url(${chatbeijing})`,
              backgroundSize: "cover",
              backgroundRepeat: "no-repeat",
              backgroundPosition: "center bottom",
              overflowY: "auto",
            }}
          >
            <div className="mb-3 d-flex justify-content-between align-items-center">
              <h5 className="mb-0">历史记录</h5>
              <select className="form-select form-select-sm w-auto" value={selectedSessionFilter} onChange={e => { setSelectedSessionFilter(e.target.value); setCurrentPage(1); loadHistory(1, e.target.value); }}>
                <option value="">所有会话</option>
                {sessions.map(s => <option key={s.session_id} value={s.session_id}>会话 {s.session_id.substring(0, 8)}...</option>)}
              </select>
            </div>
            <div className="flex-grow-1 overflow-auto">
              {history.map((record) => (
                <div key={record.record_id} className="p-3 bg-white bg-opacity-90 rounded border shadow-sm mb-3">
                  <div className="fw-medium mb-2">{record.question}</div>
                  <div className="text-muted mb-2">{record.answer}</div>
                  <div className="d-flex justify-content-between align-items-center small text-muted pt-2 border-top">
                    <span>{formatDateTime(record.response_time)}</span>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteHistoryRecord(record.record_id)}>删除</button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 d-flex justify-content-center gap-2">
              <button className="btn btn-outline-secondary btn-sm" disabled={currentPage === 1} onClick={() => { setCurrentPage(p => p - 1); loadHistory(currentPage - 1); }}>上一页</button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                <button key={p} className={`btn btn-sm ${p === currentPage ? "btn-primary" : "btn-outline-secondary"}`} onClick={() => { setCurrentPage(p); loadHistory(p); }}>{p}</button>
              ))}
              <button className="btn btn-outline-secondary btn-sm" disabled={currentPage === totalPages} onClick={() => { setCurrentPage(p => p + 1); loadHistory(currentPage + 1); }}>下一页</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AIchat;
