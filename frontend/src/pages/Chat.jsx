import { useRef, useState, useEffect } from "react";
import { api, apiErrorMessage } from "../api.js";

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text: "Ask me about today's scan — in English or Urdu. e.g. \"Is today good for buying?\" or \"MCB ke baare mein kya sochte ho?\"",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages, busy]);

  const send = async (e) => {
    e?.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const data = await api.query(q);
      setMessages((m) => [...m, { role: "ai", text: data.answer }]);
    } catch (err) {
      // Graceful failure — e.g. the Anthropic billing error. Never crash.
      setMessages((m) => [
        ...m,
        { role: "err", text: `Assistant unavailable: ${apiErrorMessage(err)}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef}>
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.text}
          </div>
        ))}
        {busy && <div className="bubble ai muted">…thinking</div>}
      </div>
      <form className="chat-input" onSubmit={send}>
        <input
          className="input"
          placeholder="Type your question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button className="btn primary" type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
