import { useEffect, useState } from "react";
import { api, getApiKey } from "./api.js";
import Home from "./pages/Home.jsx";
import Opportunities from "./pages/Opportunities.jsx";
import StockLookup from "./pages/StockLookup.jsx";
import Chat from "./pages/Chat.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { id: "home", label: "Home" },
  { id: "opportunities", label: "Top Opportunities" },
  { id: "stock", label: "Stock Lookup" },
  { id: "chat", label: "AI Chat" },
  { id: "settings", label: "Settings" },
];

const TITLES = {
  home: ["Daily Market Signal", "Today's verdict from the PSX scanner."],
  opportunities: ["Top Opportunities", "Highest-ranked names from the latest scan."],
  stock: ["Stock Lookup", "Price, rule scoring, and news sentiment for any symbol."],
  chat: ["AI Assistant", "Ask about today's scan — English or Urdu."],
  settings: ["Settings", "Connect this dashboard to your PSX API."],
};

export default function App() {
  const hasKey = !!getApiKey();
  const [tab, setTab] = useState(hasKey ? "home" : "settings");
  const [drawer, setDrawer] = useState(false);
  const [online, setOnline] = useState(null);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then(() => alive && setOnline(true))
      .catch(() => alive && setOnline(false));
    return () => {
      alive = false;
    };
  }, [tab]);

  const go = (id) => {
    setTab(id);
    setDrawer(false);
  };

  const [title, sub] = TITLES[tab];

  const nav = (
    <>
      <div className="brand">
        PSX AI Scanner
        <small>rule-based EOD · decision support</small>
      </div>
      <div style={{ height: 8 }} />
      {NAV.map((n) => (
        <button
          key={n.id}
          className={`navbtn ${tab === n.id ? "active" : ""}`}
          onClick={() => go(n.id)}
        >
          {n.label}
        </button>
      ))}
      <div className="conn">
        <span className={`dot ${online ? "ok" : "bad"}`} />
        {online === null ? "checking…" : online ? "API connected" : "API offline"}
      </div>
    </>
  );

  return (
    <div className="app">
      <div className="topbar">
        <button className="hamburger" onClick={() => setDrawer(true)}>
          ☰
        </button>
        <div className="brand" style={{ fontSize: 16 }}>
          PSX AI Scanner
        </div>
      </div>

      {drawer && <div className="backdrop" onClick={() => setDrawer(false)} />}
      <aside className={`sidebar ${drawer ? "open" : ""}`}>{nav}</aside>

      <main className="main">
        <h1 className="page-title">{title}</h1>
        <p className="page-sub">{sub}</p>
        {tab === "home" && <Home />}
        {tab === "opportunities" && <Opportunities />}
        {tab === "stock" && <StockLookup />}
        {tab === "chat" && <Chat />}
        {tab === "settings" && <Settings onSaved={() => setOnline(true)} />}
      </main>
    </div>
  );
}
