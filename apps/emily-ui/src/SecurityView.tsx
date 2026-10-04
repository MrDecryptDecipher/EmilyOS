import { FormEvent, useEffect, useMemo, useState } from "react";
import { SecurityApiClient, SecurityAudit, SecurityFinding, SecurityProgram, SecurityReport } from "./security";

const text = (value: unknown, fallback = "Unavailable") => typeof value === "string" && value.trim() ? value : fallback;
const idOf = (item: { id: string }) => item.id;

export function SecurityView() {
  const [programs, setPrograms] = useState<SecurityProgram[]>([]);
  const [audits, setAudits] = useState<SecurityAudit[]>([]);
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [reports, setReports] = useState<SecurityReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rulesUrl, setRulesUrl] = useState("");
  const [targetPath, setTargetPath] = useState("");
  const [programId, setProgramId] = useState("");
  const [draft, setDraft] = useState("");
  const [approver, setApprover] = useState("");
  const [selectedReport, setSelectedReport] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const api = new SecurityApiClient(controller.signal);
    Promise.all([api.getPrograms(), api.getAudits(), api.getFindings(), api.getReports()])
      .then(([p, a, f, r]) => { setPrograms(p); setAudits(a); setFindings(f); setReports(r); setError(null); })
      .catch((e: unknown) => { if ((e as Error).name !== "AbortError") setError(e instanceof Error ? e.message : "Security backend unavailable."); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const api = useMemo(() => new SecurityApiClient(), []);
  const importProgram = async (event: FormEvent) => {
    event.preventDefault();
    let url: URL;
    try { url = new URL(rulesUrl.trim()); if (!/^https?:$/.test(url.protocol)) throw new Error(); } catch { setError("Enter a valid HTTP(S) bounty rules URL."); return; }
    if (busy) return;
    setBusy("import"); setError(null); setFeedback(null);
    try { const program = await api.importProgram({ rules_url: url.toString() }); setPrograms((items) => items.some((item) => item.id === program.id) ? items : [...items, program]); setProgramId(program.id); setRulesUrl(""); setFeedback("Bounty rules imported."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not import bounty rules."); } finally { setBusy(null); }
  };
  const startAudit = async (event: FormEvent) => {
    event.preventDefault();
    if (!programId) { setError("Select a program before starting an audit."); return; }
    if (!targetPath.trim()) { setError("Add a local target path before starting an audit."); return; }
    if (busy) return;
    setBusy("audit"); setError(null); setFeedback(null);
    try { const audit = await api.createAudit({ program_id: programId, target_path: targetPath.trim() }); setAudits((items) => [audit, ...items.filter((item) => item.id !== audit.id)]); setTargetPath(""); setFeedback("Offline audit started."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not start offline audit."); } finally { setBusy(null); }
  };
  const approve = async () => {
    if (!selectedReport || busy) return;
    setBusy("approve"); setError(null); setFeedback(null);
     if (!approver.trim()) { setError("Enter your approver identity before approving."); return; }
     try { const updated = await api.approveReport(selectedReport, { approved_by: approver.trim(), note: draft.trim() || undefined }); setReports((items) => items.map((item) => item.id === updated.id ? updated : item)); setDraft(""); setFeedback("Report approval recorded by the backend."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not approve report."); } finally { setBusy(null); }
  };
  const visibleFindings = findings;
  return <section className="collection">
    <div className="section-intro"><p className="eyebrow">DEFENSIVE RESEARCH</p><h2>Security & bounty workbench</h2><p className="muted">Backend-reported programs, audits, findings, and reports only.</p></div>
    <div className="notice" role="note">Offline review only. Emily does not submit to bounty platforms, execute exploits, or initiate wallet payouts.</div>
    {error && <p className="error" role="alert">{error}</p>}{feedback && <p className="notice" role="status">{feedback}</p>}
    {loading ? <div className="empty"><h3>Loading security records…</h3></div> : <>
      <div className="grid-two">
        <section className="panel"><p className="eyebrow">PROGRAM INTAKE</p><h3>Import bounty rules</h3><form onSubmit={importProgram} className="url-form"><input type="url" value={rulesUrl} onChange={(e) => setRulesUrl(e.target.value)} placeholder="https://platform.example/rules" aria-label="Bounty rules URL" required disabled={busy !== null} /><button type="submit" disabled={busy !== null}>{busy === "import" ? "Importing…" : "Import"}</button></form><p className="muted small">Provide the rules URL yourself; Emily will not discover or submit to platforms.</p><h3>Add audit target</h3><form onSubmit={startAudit}><label className="muted">Program<select value={programId} onChange={(e) => setProgramId(e.target.value)} disabled={busy !== null} required><option value="">Select a backend-reported program</option>{programs.map((program) => <option value={program.id} key={program.id}>{text(program.name, program.id)}</option>)}</select></label><label className="muted">Local target path<input value={targetPath} onChange={(e) => setTargetPath(e.target.value)} placeholder="C:\repo\contract" aria-label="Local target path" disabled={busy !== null} required /></label><button type="submit" disabled={busy !== null || programs.length === 0}>{busy === "audit" ? "Starting…" : "Start offline audit"}</button></form></section>
        <section className="panel"><p className="eyebrow">PROGRAMS</p><h3>{programs.length} backend records</h3>{programs.length === 0 ? <div className="empty"><h3>No programs returned</h3><p className="muted">Import a user-provided bounty rules URL to begin.</p></div> : <div className="item-list">{programs.map((p) => <article key={idOf(p)}><strong>{text(p.name, p.id)}</strong><p className="muted">{text(p.platform, "Platform unavailable")} · {text(p.rules_url, "Rules URL unavailable")}</p></article>)}</div>}</section>
      </div>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">AUDITS</p><h3>Offline audit runs</h3></div><span className="badge">{audits.length}</span></div>{audits.length === 0 ? <p className="muted">No audits returned by the backend.</p> : <div className="item-list">{audits.map((a) => <article key={a.id}><strong>{a.id}</strong><p className="muted">{text(a.status)} · target {text(a.target_path)} · program {text(a.program_id)}</p></article>)}</div>}</section>
      <section className="panel"><p className="eyebrow">FINDINGS</p><h3>Evidence review</h3>{visibleFindings.length === 0 ? <p className="muted">No findings returned by the backend.</p> : <div className="item-list">{visibleFindings.map((f) => <article key={f.id}><strong>{text(f.title, f.id)}</strong><p>{text(f.description, "No description returned.")}</p><div className="rows"><div><span>Severity</span><b>{text(f.severity)}</b></div><div><span>Confidence</span><b>{text(f.confidence)}</b></div><div><span>Evidence</span><b>{text(f.evidence)}</b></div><div><span>Rule citation</span><b>{Array.isArray(f.rule_citation) ? f.rule_citation.join(", ") : text(f.rule_citation)}</b></div></div></article>)}</div>}</section>
       <section className="panel"><p className="eyebrow">REPORTS</p><h3>Draft and approve</h3>{reports.length === 0 ? <p className="muted">No reports returned by the backend.</p> : <><label className="muted">Report<select value={selectedReport} onChange={(e) => setSelectedReport(e.target.value)}><option value="">Select a report</option>{reports.map((r) => <option value={r.id} key={r.id}>{text(r.title, r.id)} · {text(r.status)}</option>)}</select></label><label className="muted">Approver identity<input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name or team identity" disabled={!selectedReport || busy !== null} /></label><label className="muted">Review notes<textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Record why this report is ready for your manual platform review…" disabled={!selectedReport || busy !== null} /></label><button onClick={() => void approve()} disabled={!selectedReport || busy !== null}>{busy === "approve" ? "Approving…" : "Approve report"}</button><p className="muted small">Approval only records human review. Platform submission and payout remain disabled.</p></>}</section>
    </>}
  </section>;
}

export default SecurityView;
