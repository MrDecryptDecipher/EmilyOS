import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import * as walletUtilities from "./wallet";
import SecurityView from "./SecurityView";

type WalletProvider = { info?: { uuid?: string; name?: string; icon?: string; rdns?: string }; provider?: { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> }; request?: (args: { method: string; params?: unknown[] }) => Promise<unknown>; uuid?: string; name?: string; icon?: string; rdns?: string };
type WalletState = { provider: WalletProvider | null; address: string | null; chainId: string | null; capabilities: string[] };
const SUPPORTED_CHAINS: Record<string, string> = { "0x1": "Ethereum", "0x89": "Polygon", "0xa4b1": "Arbitrum One", "0xa": "Optimism", "0x2105": "Base" };
const utility = walletUtilities as unknown as Record<string, (...args: any[]) => any>;
const requestOf = (item: WalletProvider | null) => item?.provider?.request ?? item?.request;
const shortAddress = (address: string) => `${address.slice(0, 6)}…${address.slice(-4)}`;

type Health = { status?: string; kernel?: string; version?: string };
type Telemetry = Record<string, string | number | null | undefined>;
type ChatMessage = { role: "user" | "assistant"; text: string };
const API = import.meta.env.VITE_API_BASE ?? "";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}
function value(data: Telemetry | null, key: string, suffix = "") {
  const v = data?.[key];
  return v === null || v === undefined ? "Unavailable" : `${v}${suffix}`;
}

export function App() {
  const [section, setSection] = useState("Overview");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [telemetryState, setTelemetryState] = useState<"connecting" | "live" | "stale" | "disconnected">("connecting");
  const [missions, setMissions] = useState<unknown[]>([]);
  const [agents, setAgents] = useState<unknown[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const chatAbort = useRef<AbortController | null>(null);
  const [walletState, setWalletState] = useState<WalletState>({ provider: null, address: null, chainId: null, capabilities: [] });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getJson<Health>("/api/health", controller.signal), getJson<{ missions?: unknown[] }>("/api/missions", controller.signal), getJson<{ agents?: unknown[] }>("/api/agents", controller.signal)])
      .then(([h, m, a]) => { setHealth(h); setMissions(m.missions ?? []); setAgents(a.agents ?? []); setHealthError(null); })
      .catch((e) => { if (e.name !== "AbortError") setHealthError(e instanceof Error ? e.message : "Backend unavailable"); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let cancelled = false; let timer: number | undefined;
    const connect = () => {
      if (cancelled) return;
      setTelemetryState("connecting");
      const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${API}/ws/telemetry`;
      const ws = new WebSocket(url); socket.current = ws;
      ws.onopen = () => setTelemetryState("live");
      ws.onmessage = (event) => { try { setTelemetry(JSON.parse(event.data) as Telemetry); setTelemetryState("live"); } catch { setTelemetryState("stale"); } };
      ws.onerror = () => setTelemetryState("stale");
      ws.onclose = () => { if (!cancelled) { setTelemetryState("disconnected"); timer = window.setTimeout(connect, 3000); } };
    };
    connect();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); socket.current?.close(); socket.current = null; };
  }, []);

  const send = useCallback(async (event: FormEvent) => {
    event.preventDefault(); const message = draft.trim();
    if (!message || sending) return;
    setChat((items) => [...items, { role: "user", text: message }]); setDraft(""); setSending(true); setChatError(null);
    chatAbort.current?.abort(); const controller = new AbortController(); chatAbort.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(`${API}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }), signal: controller.signal });
      if (!response.ok) throw new Error(`Chat failed (${response.status})`);
      const result = await response.json() as { reply?: string };
      setChat((items) => [...items, { role: "assistant", text: result.reply ?? "The backend returned no reply." }]);
    } catch (e) { if ((e as Error).name !== "AbortError") setChatError(e instanceof Error ? e.message : "Could not send message"); }
    finally { window.clearTimeout(timeout); setSending(false); }
  }, [draft, sending]);

  const nav = ["Overview", "Missions", "Agents", "Chat", "Wallet", "Security"];
  return <div className="app-shell">
     <aside className="sidebar"><div className="brand"><span className="brand-mark">E</span><span>EMILY <small>WORKBENCH</small></span></div><nav aria-label="Primary navigation">{nav.map((item) => <button className={section === item ? "active" : ""} key={item} onClick={() => setSection(item)}><span aria-hidden="true">{item === "Overview" ? "◈" : item === "Missions" ? "◌" : item === "Agents" ? "◉" : item === "Wallet" ? "▣" : "◇"}</span>{item}</button>)}</nav><a className="legacy-link" href="/ui/legacy.html">Open legacy voice UI ↗</a><div className="sidebar-foot">LOCAL CONTROL PLANE<br/><span className={health ? "dot online" : "dot"}></span>{health ? "Backend connected" : "Backend unavailable"}</div></aside>
    <main className="main"><header className="topbar"><div><p className="eyebrow">EMILY / CONTROL PLANE</p><h1>{section}</h1></div><div className={`connection ${health ? "connected" : ""}`}><span className="dot"></span>{health ? health.kernel ?? "Connected" : "Connection unavailable"}</div></header>
      {healthError && <div className="notice" role="alert">{healthError}. Live values will appear when the backend is reachable.</div>}
      {section === "Overview" && <Overview telemetry={telemetry} state={telemetryState} missions={missions.length} agents={agents.length} health={health} />}
      {section === "Missions" && <Collection title="Missions" items={missions} empty="No missions are currently registered." />}
      {section === "Agents" && <Collection title="Agents" items={agents} empty="No agents are currently registered." />}
       {section === "Chat" && <Chat chat={chat} draft={draft} setDraft={setDraft} send={send} sending={sending} error={chatError} cancel={() => chatAbort.current?.abort()} />}
       {section === "Wallet" && <WalletView state={walletState} setState={setWalletState} />}
       {section === "Security" && <SecurityView />}
    </main>
  </div>;
}

function WalletView({ state, setState }: { state: WalletState; setState: (state: WalletState) => void }) {
  const [providers, setProviders] = useState<WalletProvider[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [signing, setSigning] = useState(false);
  const [url, setUrl] = useState("");
  const [requestBusy, setRequestBusy] = useState(false);
  const [payment, setPayment] = useState<Record<string, string> | null>(null);
  const [requestResult, setRequestResult] = useState<string | null>(null);
  const [maxSpend, setMaxSpend] = useState("1");
  const [confirm, setConfirm] = useState(false);

  const discover = useCallback(async () => {
    try {
      const found = utility.createWalletManager ? utility.createWalletManager().discover() : (utility.discoverWallets?.() ?? utility.discoverProviders?.());
      if (found) setProviders((await Promise.resolve(found)) as WalletProvider[]);
    } catch { setFeedback("Wallet discovery failed. Check your wallet extension."); }
  }, []);
  useEffect(() => {
    void discover();
    const onAnnounce = (event: Event) => { const detail = (event as CustomEvent<WalletProvider>).detail; if (detail) setProviders((items) => items.some((p) => (p.info?.uuid ?? p.uuid) === (detail.info?.uuid ?? detail.uuid)) ? items : [...items, detail]); };
    window.addEventListener("eip6963:announceProvider", onAnnounce);
    window.dispatchEvent(new Event("eip6963:requestProvider"));
    return () => window.removeEventListener("eip6963:announceProvider", onAnnounce);
  }, [discover]);
  const refresh = useCallback(async (providerOverride?: WalletProvider | null) => {
    const target = providerOverride ?? state.provider;
    const request = requestOf(target);
    if (!request) return;
    try {
      const [accounts, chainId] = await Promise.all([request({ method: "eth_accounts" }), request({ method: "eth_chainId" })]);
      const address = Array.isArray(accounts) && typeof accounts[0] === "string" ? accounts[0] : null;
      const features = utility.detectProviderFeatures?.(target?.provider ?? target) ?? {};
      setState({ provider: target, address, chainId: typeof chainId === "string" ? chainId : null, capabilities: Object.entries(features).filter(([, report]: any) => report?.supported).map(([name]) => name) });
    } catch { setFeedback("Could not refresh wallet state."); }
  }, [state, setState]);
  const connect = async (provider: WalletProvider) => {
    const id = provider.info?.uuid ?? provider.uuid ?? provider.info?.name ?? provider.name ?? "wallet"; setBusy(id); setFeedback(null);
    try {
      const result = utility.connectWallet ? await utility.connectWallet(provider) : await requestOf(provider)?.({ method: "eth_requestAccounts" });
      const address = Array.isArray(result) ? result[0] : result?.address;
      setState({ provider, address: typeof address === "string" ? address : null, chainId: null, capabilities: [] });
      await refresh(provider);
    } catch (e) { setFeedback((e as Error)?.message?.toLowerCase().includes("reject") ? "Connection rejected." : "Could not connect to this wallet."); }
    finally { setBusy(null); }
  };
  const disconnect = async () => { try { await utility.disconnectWallet?.(state.provider); } finally { setState({ provider: null, address: null, chainId: null, capabilities: [] }); setFeedback("Wallet disconnected."); } };
  const switchChain = async (chainId: string) => {
    const request = requestOf(state.provider); if (!request) return; setBusy("switch");
    try { if (utility.switchChain) await utility.switchChain(state.provider, chainId); else await request({ method: "wallet_switchEthereumChain", params: [{ chainId }] }); await refresh(); setFeedback(`Switched to ${SUPPORTED_CHAINS[chainId]}.`); }
    catch { setFeedback("Chain switch was rejected or unsupported by this wallet."); } finally { setBusy(null); }
  };
  const sign = async () => {
    if (!state.address || !message.trim()) return; setSigning(true); setFeedback(null);
    try { const signature = utility.signMessage ? await utility.signMessage(state.provider, message) : await requestOf(state.provider)?.({ method: "personal_sign", params: [message, state.address] }); setFeedback(signature ? "Message signed successfully." : "Wallet did not return a signature."); }
    catch { setFeedback("Message signing was rejected."); } finally { setSigning(false); }
  };
  const makeRequest = async (event: FormEvent) => {
    event.preventDefault(); if (requestBusy) return; let parsed: URL;
    try { parsed = new URL(url); if (!["http:", "https:"].includes(parsed.protocol)) throw new Error(); } catch { setRequestResult("Enter a valid HTTP(S) URL."); return; }
    setRequestBusy(true); setPayment(null); setRequestResult(null); setConfirm(false);
    try {
      const response = await fetch(parsed.toString());
       if (response.status === 402) {
         const raw = response.headers.get("PAYMENT-REQUIRED") ?? response.headers.get("payment-required");
         let data: any = null;
         if (raw) {
           try { data = JSON.parse(raw); }
           catch { try { data = JSON.parse(atob(raw)); } catch { throw new Error("The 402 response contained an invalid payment header."); } }
         }
         const accepted = data?.accepts?.[0] ?? data?.payments?.[0] ?? data;
        setPayment({ version: String(data?.x402Version ?? data?.version ?? "unknown"), resource: String(data?.resource ?? parsed.toString()), network: String(accepted?.network ?? accepted?.caip2Network ?? "unknown"), asset: String(accepted?.asset ?? "unknown"), amount: String(accepted?.maxAmountRequired ?? accepted?.amount ?? "unknown"), scheme: String(accepted?.scheme ?? "unknown"), payTo: String(accepted?.payTo ?? "unknown"), expiry: String(accepted?.maxTimeoutSeconds ?? accepted?.expiry ?? "unknown") });
        setRequestResult("Payment required. Review the details and confirm manually.");
      } else setRequestResult(`Request completed (${response.status}). Payment was not requested.`);
    } catch { setRequestResult("Network error while requesting that URL."); } finally { setRequestBusy(false); }
  };
  const providerName = (p: WalletProvider) => p.info?.name ?? p.name ?? p.info?.rdns ?? p.rdns ?? "Injected wallet";
  return <section className="wallet-view"><div className="section-intro"><p className="eyebrow">WEB3 CONTROL</p><h2>Wallet & x402</h2><p className="muted">Discover providers and inspect payment requests. Emily never signs or pays automatically.</p></div>{feedback && <p className="notice" role="status">{feedback}</p>}
    <div className="wallet-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">EIP-6963</p><h3>Wallet providers</h3></div><button className="secondary" onClick={() => void discover()}>Refresh</button></div>{providers.length === 0 ? <p className="muted">No wallet detected. Install an EIP-6963-compatible wallet to continue.</p> : <div className="provider-list">{providers.map((p, i) => <article className="provider-card" key={p.info?.uuid ?? p.uuid ?? i}>{p.info?.icon && <img src={p.info.icon} alt="" /> }<div><strong>{providerName(p)}</strong><small>{p.info?.rdns ?? p.rdns ?? "EIP-6963 provider"}</small></div><button onClick={() => void connect(p)} disabled={busy !== null}>{busy ? "Connecting…" : "Connect"}</button></article>)}</div>}{state.address && <div className="wallet-connected"><strong>{shortAddress(state.address)}</strong><span>{state.chainId ? SUPPORTED_CHAINS[state.chainId] ?? `Unsupported (${state.chainId})` : "Chain unknown"}</span><button className="secondary" onClick={() => void disconnect()}>Disconnect</button></div>}</section>
      <section className="panel"><p className="eyebrow">ACCOUNT</p><h3>Wallet state</h3><div className="rows"><div><span>Address</span><b>{state.address ? shortAddress(state.address) : "Not connected"}</b></div><div><span>Current chain</span><b>{state.chainId ? SUPPORTED_CHAINS[state.chainId] ?? `Unsupported (${state.chainId})` : "Unavailable"}</b></div><div><span>Capabilities</span><b>{state.capabilities.join(", ") || "Unknown"}</b></div></div><div className="button-row"><button className="secondary" onClick={() => void refresh()} disabled={!state.provider}>Refresh state</button>{Object.entries(SUPPORTED_CHAINS).map(([id, name]) => <button className="secondary" key={id} onClick={() => void switchChain(id)} disabled={!state.provider || busy !== null}>{name}</button>)}</div></section></div>
    <section className="panel sign-panel"><p className="eyebrow">EXPLICIT ACTION</p><h3>Sign a message</h3><p className="muted">Only your exact message below will be sent to the wallet for approval.</p><textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Message to sign" aria-label="Message to sign" rows={3} /><button onClick={() => void sign()} disabled={!state.address || !message.trim() || signing}>{signing ? "Waiting for wallet…" : "Sign message"}</button></section>
    <section className="panel x402-panel"><p className="eyebrow">HTTP 402 DISCOVERY</p><h3>Request a paid resource</h3><form onSubmit={makeRequest} className="url-form"><input value={url} onChange={(e) => setUrl(e.target.value)} type="url" placeholder="https://example.com/resource" aria-label="Resource URL" required /><button type="submit" disabled={requestBusy}>{requestBusy ? "Requesting…" : "Make request"}</button></form>{requestResult && <p className="muted" role="status">{requestResult}</p>}{payment && <div className="payment-details"><h4>Payment requirement</h4>{Object.entries(payment).map(([key, value]) => <div key={key}><span>{key}</span><b>{value}</b></div>)}<label>Spending guard (USD equivalent, max default $1)<input type="number" min="0" max="1" step="0.01" value={maxSpend} onChange={(e) => setMaxSpend(e.target.value)} /></label><label className="confirm-line"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> I understand this is a manual payment confirmation.</label><button disabled={!confirm || !state.address || Number(maxSpend) > 1} onClick={() => setRequestResult("wallet/payment scheme integration required")}>Confirm payment</button><p className="muted small">wallet/payment scheme integration required</p></div>}</section>
  </section>;
}

function Overview({ telemetry, state, missions, agents, health }: { telemetry: Telemetry | null; state: string; missions: number; agents: number; health: Health | null }) {
  const cards = [["CPU LOAD", value(telemetry, "cpu_usage", "%")], ["MEMORY", value(telemetry, "ram_mb", " MB")], ["ACTIVE AGENTS", value(telemetry, "active_agents")], ["PAPER PORTFOLIO", value(telemetry, "portfolio_value")]];
  return <><section className="hero"><div><p className="eyebrow">SYSTEM SNAPSHOT</p><h2>Quietly capable.<br /><em>Always observable.</em></h2><p className="muted">A grounded view of Emily’s local runtime. Values are reported by the backend and never estimated.</p></div><div className="hero-status"><span className="pulse"></span><strong>{health?.status ?? "Unavailable"}</strong><small>{state === "live" ? "Telemetry stream live" : `Telemetry ${state}`}</small></div></section><section className="metrics">{cards.map(([label, text]) => <article className="metric" key={label}><span>{label}</span><strong>{text}</strong></article>)}</section><div className="grid-two"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">RUNTIME</p><h3>Operational pulse</h3></div><span className={`badge ${state}`}>{state}</span></div><div className="rows"><div><span>Kernel</span><b>{health?.kernel ?? "Unavailable"}</b></div><div><span>Memory usage</span><b>{value(telemetry, "ram_percent", "%")}</b></div><div><span>Disk usage</span><b>{value(telemetry, "disk_percent", "%")}</b></div><div><span>Stored memories</span><b>{value(telemetry, "memory_count")}</b></div></div></section><section className="panel accent"><p className="eyebrow">WORKSPACE</p><h3>Activity at a glance</h3><div className="big-number">{missions}</div><p className="muted">registered missions</p><div className="mini-stat"><span>Agents</span><strong>{agents}</strong></div><p className="paper-note">PAPER MODE · Trading data is informational only.</p></section></div></>;
}
function Collection({ title, items, empty }: { title: string; items: unknown[]; empty: string }) { return <section className="collection"><div className="section-intro"><p className="eyebrow">WORKSPACE REGISTRY</p><h2>{title}</h2><p className="muted">Backend-reported records only.</p></div>{items.length === 0 ? <div className="empty"><span>○</span><h3>{empty}</h3><p className="muted">This view will update when the runtime publishes new records.</p></div> : <div className="item-list">{items.map((item, i) => <pre key={i}>{JSON.stringify(item, null, 2)}</pre>)}</div>}</section>; }
function Chat({ chat, draft, setDraft, send, sending, error, cancel }: { chat: ChatMessage[]; draft: string; setDraft: (v: string) => void; send: (e: FormEvent) => void; sending: boolean; error: string | null; cancel: () => void }) { return <section className="chat"><div className="section-intro"><p className="eyebrow">DIRECT CHANNEL</p><h2>Talk to Emily</h2><p className="muted">Messages are sent to the local Emily runtime.</p></div><div className="transcript" aria-live="polite">{chat.length === 0 && <div className="empty"><span>◇</span><h3>Start a conversation</h3><p className="muted">Ask Emily about your workspace or runtime.</p></div>}{chat.map((m, i) => <div className={`message ${m.role}`} key={i}><span>{m.role === "user" ? "YOU" : "EMILY"}</span><p>{m.text}</p></div>)}</div>{error && <p className="error" role="alert">{error}</p>}<form onSubmit={send} className="composer"><input aria-label="Message Emily" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Write a message…" disabled={sending} />{sending && <button type="button" onClick={cancel}>Cancel</button>}<button type="submit" disabled={sending || !draft.trim()}>{sending ? "Sending…" : "Send"}</button></form></section>; }
