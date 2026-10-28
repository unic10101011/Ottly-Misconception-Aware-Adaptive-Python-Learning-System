import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatContent from '../components/ChatContent.jsx';
import chathaita from './images/chathaita.png';
import yonghu from './images/yonghu.png';
import chatbeijing from './images/chatbeijing.png'; // 背景图

const welcomeMessage = { content: "你好呀，我是小海獭，请问有什么可以帮助你的呢？", isUser: false };

const AIchat = () => {
  const navigate = useNavigate();
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([welcomeMessage]);
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState('');
  const [sessionsError, setSessionsError] = useState('');
  const [sessionHistoryError, setSessionHistoryError] = useState('');
  const [sessionHistoryLoading, setSessionHistoryLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const [question, setQuestion] = useState("");
  const [activeTab, setActiveTab] = useState("chat");
  const [selectedSessionFilter, setSelectedSessionFilter] = useState("");
  const chatBodyRef = useRef(null);
  const questionInputRef = useRef(null);
  const sendingRef = useRef(false);
  const mountedRef = useRef(false);
  const sessionRequestRef = useRef(0);
  const runtimeRef = useRef(null);
  const [contextFull, setContextFull] = useState(false);
  const [sessionNotice, setSessionNotice] = useState('');
  const pageSize = 10;

  useEffect(() => {
    mountedRef.current = true;
    loadSessionHistory();
    loadSessions();
    loadHistory();
    const restoreOnFocus = () => loadSessionHistory(undefined, true);
    window.addEventListener('focus', restoreOnFocus);
    return () => {
      mountedRef.current = false;
      sessionRequestRef.current++;
      window.removeEventListener('focus', restoreOnFocus);
    };
  }, []);

  useEffect(() => {
    if (!sending || sendingRef.current) return;
    const timer = setInterval(() => loadSessionHistory(undefined, true), 1500);
    return () => clearInterval(timer);
  }, [sending]);

  const loadSessions = async () => {
    setSessionsError('');
    try {
      const response = await fetch("/api/v1/ai/sessions", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("获取会话列表失败");
      const data = await response.json();
      if (data.code === 200) setSessions(data.data.sessions);
    } catch (error) {
      console.error("加载会话失败:", error);
      setSessionsError('会话列表暂时无法加载，请稍后重试。');
    }
  };

  const loadHistory = async (page = currentPage, sessionId = selectedSessionFilter) => {
    setHistoryError('');
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
        setTotalPages(Math.max(1, Math.ceil(data.total / pageSize)));
      }
    } catch (error) {
      console.error("加载历史记录失败:", error);
      setHistoryError('历史记录暂时无法加载，请稍后重试。');
    }
  };

  const loadSessionHistory = async (sessionId = undefined, quiet = false) => {
    if (sendingRef.current) return;
    const requestVersion = ++sessionRequestRef.current;
    if (!quiet) setSessionHistoryLoading(true);
    setSessionHistoryError('');
    try {
      const response = await fetch('/api/v1/ai/session', {
        method: sessionId === undefined ? 'GET' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        ...(sessionId === undefined ? {} : { body: JSON.stringify({ session_id: sessionId }) }),
      });
      const result = await response.json();
      if (!response.ok || result.code !== 200) throw new Error(result.detail?.message || result.detail || '获取当前会话失败');
      if (!mountedRef.current || requestVersion !== sessionRequestRef.current) return;
      const data = result.data;
      if (runtimeRef.current && runtimeRef.current !== data.runtime_id) {
        setSessionNotice('项目已重启，已为你开启新对话。旧记录仍可在历史记录中查看。');
      }
      runtimeRef.current = data.runtime_id;
      setCurrentSessionId(data.session_id);
      setMessages([welcomeMessage, ...data.messages]);
      setContextFull(data.context_full);
      setSending(data.pending);
      setTyping(data.pending && !data.messages.at(-1)?.content);
    } catch (error) {
      if (mountedRef.current && requestVersion === sessionRequestRef.current) {
        setSessionHistoryError(`会话暂时无法加载：${error.message}。请重试后继续。`);
      }
    } finally {
      if (mountedRef.current && requestVersion === sessionRequestRef.current) setSessionHistoryLoading(false);
    }
  };

  const selectSession = (sessionId) => {
    setSessionNotice('');
    loadSessionHistory(sessionId);
  };

  const createNewSession = () => {
    setSessionNotice('');
    loadSessionHistory(null);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (sendingRef.current || sending || sessionHistoryLoading || sessionHistoryError || contextFull || !question.trim()) return;
    sendingRef.current = true;
    sessionRequestRef.current++;
    setSending(true);
    setSessionNotice('');

    const newMessages = [...messages, { content: question, isUser: true }, { content: "", isUser: false }];
    setMessages(newMessages);
    setQuestion("");
    setTyping(true);

    let restoreAfterSend = false;
    let streamFailed = false;
    try {
      const response = await fetch("/api/v1/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        body: JSON.stringify({ question, stream: true, session_id: currentSessionId, runtime_id: runtimeRef.current }),
      });

      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        const detail = result.detail;
        if (['CHAT_CONTEXT_FULL', 'CHAT_RUNTIME_CHANGED', 'CHAT_BUSY'].includes(detail?.code)) {
          if (mountedRef.current) {
            setMessages(messages);
            setQuestion(question);
            setSessionNotice(detail.message);
            if (detail.code === 'CHAT_CONTEXT_FULL') setContextFull(true);
          }
          restoreAfterSend = detail.code !== 'CHAT_CONTEXT_FULL';
          return;
        }
        throw new Error(typeof detail === 'string' ? detail : 'AI 服务请求失败');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = "";
      let sessionIdFromResponse = currentSessionId;
      let pending = "";
      let ended = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = (pending + chunk).split("\n");
        pending = lines.pop();
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.substring(6);
            if (data) {
              try {
                const json = JSON.parse(data);
                if (json.content) {
                  if (json.content === "[END]") { ended = true; continue; }
                  if (json.error) {
                    streamFailed = true;
                    if (mountedRef.current) { setSessionNotice(json.content); setQuestion(question); }
                  }
                  fullAnswer += json.content;
                  if (mountedRef.current) {
                    setTyping(false);
                    setMessages((prev) => [...prev.slice(0, -1), { content: fullAnswer, isUser: false }]);
                  }
                }
                if (json.session_id) sessionIdFromResponse = json.session_id;
              } catch (e) {
                console.error("解析JSON失败:", e);
              }
            }
          }
        }
      }

      if (!ended) throw new Error('回复连接中断，请稍后重试');
      if (mountedRef.current) {
        if (sessionIdFromResponse) setCurrentSessionId(sessionIdFromResponse);
        loadSessions();
      }
      restoreAfterSend = !streamFailed;
    } catch (error) {
      console.error("错误:", error);
      if (mountedRef.current) {
        setQuestion(question);
        setSessionNotice(error.message || 'AI 服务暂时不可用，请稍后重试。');
        setMessages((prev) => [...prev.slice(0, -1), { content: '本次回复未完成，请重试。', isUser: false }]);
      }
    } finally {
      sendingRef.current = false;
      if (mountedRef.current) {
        setTyping(false);
        setSending(false);
        if (restoreAfterSend) await loadSessionHistory();
      }
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

  return (
    <div className="ai-chat-page">
      <div className="ai-chat-layout">
        <div className="chat-toolbar">
          <div className="chat-tabs" role="tablist" aria-label="AI 对话页面">
            <button type="button" role="tab" aria-selected={activeTab === 'chat'} className={activeTab === 'chat' ? 'active' : ''} onClick={() => setActiveTab('chat')}>对话</button>
            <button type="button" role="tab" aria-selected={activeTab === 'history'} className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>历史记录</button>
          </div>
          <button type="button" className="chat-back-button" onClick={() => navigate('/app/levels')}>← 返回学习地图</button>
        </div>

        {activeTab === "chat" && (
          <div className="ai-chat-panel">
            <div className="chat-session-bar">
              <label htmlFor="chat-session-select">当前会话</label>
              <select id="chat-session-select" value={currentSessionId || ''} disabled={sending || sessionHistoryLoading} onChange={event => event.target.value ? selectSession(event.target.value) : createNewSession()}>
                <option value={currentSessionId && !sessions.some(session => session.session_id === currentSessionId) ? currentSessionId : ''}>新对话</option>
                {sessions.map(session => <option key={session.session_id} value={session.session_id}>会话 {session.session_id.slice(0, 8)} · {formatDateTime(session.last_message_time)}</option>)}
              </select>
              <button type="button" disabled={sending || sessionHistoryLoading} onClick={createNewSession}>＋ 新对话</button>
            </div>
            {sessionsError && <p className="chat-load-error" role="alert">{sessionsError} <button type="button" onClick={loadSessions}>重试</button></p>}
            {sessionHistoryError && <p className="chat-load-error" role="alert">{sessionHistoryError} <button type="button" onClick={() => loadSessionHistory()}>重试</button></p>}
            {(contextFull || sessionNotice) && <p className="chat-session-notice" role="status">
              {contextFull ? '本次对话已接近上下文上限，请新开一个对话继续。' : sessionNotice}
              {contextFull && <button type="button" disabled={sending || sessionHistoryLoading} onClick={createNewSession}>新开一个对话</button>}
            </p>}
            <div
              ref={chatBodyRef}
              className="chat-body"
              style={{ backgroundImage: `url(${chatbeijing})` }}
            >
              {sessionHistoryLoading && <p className="chat-history-empty" role="status">正在打开这段会话...</p>}
              {messages.map((msg, i) => (
                <div key={i} className={'chat-message ' + (msg.isUser ? 'is-user' : 'is-otter')}>
                  {!msg.isUser && (
                    <img src={chathaita} alt="小海獭" className="chat-avatar" />
                  )}
                  <div className="chat-message-bubble">
                    {msg.isUser ? msg.content : <ChatContent content={msg.content} />}
                  </div>
                  {msg.isUser && (
                    <img src={yonghu} alt="用户" className="chat-avatar" />
                  )}
                </div>
              ))}
              {messages.length === 1 && !sessionHistoryLoading && <div className="chat-suggestions">
                <span>可以从这些问题开始</span>
                {['print() 是做什么的？', '我的代码报错了，怎么排查？', '可以给我一点解题提示吗？'].map(prompt =>
                  <button type="button" key={prompt} onClick={() => { setQuestion(prompt); questionInputRef.current?.focus() }}>{prompt}</button>)}
              </div>}
              {typing && (
                <div className="chat-message is-otter" role="status" aria-label="小海獭正在回复">
                  <img src={chathaita} alt="" className="chat-avatar" />
                  <div className="chat-typing">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              )}
            </div>

            <div className="chat-composer">
              <form onSubmit={sendMessage}>
                <label className="visually-hidden" htmlFor="chat-question">向小海獭提问</label>
                <input
                  id="chat-question"
                  ref={questionInputRef}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="把你的问题告诉小海獭..."
                  maxLength={1000}
                  disabled={sending || sessionHistoryLoading || !!sessionHistoryError || contextFull}
                />
                <button
                  type="submit"
                  disabled={sending || sessionHistoryLoading || !!sessionHistoryError || contextFull || !question.trim()}
                >
                  {sending ? '回复中...' : '发送'}
                </button>
              </form>
            </div>
          </div>
        )}

        {activeTab === "history" && (
          <div
            className="chat-history-panel"
            style={{ backgroundImage: `url(${chatbeijing})` }}
          >
            <div className="chat-history-heading">
              <h2>历史记录</h2>
              <select aria-label="筛选会话" className="form-select form-select-sm" value={selectedSessionFilter} onChange={e => { setSelectedSessionFilter(e.target.value); setCurrentPage(1); loadHistory(1, e.target.value); }}>
                <option value="">所有会话</option>
                {sessions.map(s => <option key={s.session_id} value={s.session_id}>会话 {s.session_id.substring(0, 8)}...</option>)}
              </select>
            </div>
            <div className="chat-history-list">
              {historyError && <p className="chat-load-error" role="alert">{historyError} <button type="button" onClick={() => loadHistory()}>重试</button></p>}
              {!historyError && history.length === 0 && <p className="chat-history-empty">还没有聊天记录。回到“对话”向小海獭提问吧。</p>}
              {history.map((record) => (
                <div key={record.record_id} className="p-3 bg-white bg-opacity-90 rounded border shadow-sm mb-3">
                  <div className="fw-medium mb-2">{record.question}</div>
                  <div className="text-muted mb-2 chat-history-answer"><ChatContent content={record.answer} /></div>
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
