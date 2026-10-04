export type SecurityProgram = {
  id: string;
  name?: string;
  platform?: string;
  rules_url?: string;
  scope?: string[];
  [key: string]: unknown;
};

export type SecurityAudit = {
  id: string;
  program_id?: string;
  target_path?: string;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
};

export type SecurityFinding = {
  id: string;
  audit_id?: string;
  title?: string;
  severity?: string;
  evidence?: string;
  confidence?: number | string;
  rule_citation?: string | string[];
  description?: string;
  [key: string]: unknown;
};

export type SecurityReport = {
  id: string;
  audit_id?: string;
  title?: string;
  status?: string;
  summary?: string;
  findings?: string[];
  [key: string]: unknown;
};

export type ImportProgramRequest = { rules_url: string };
export type CreateAuditRequest = { program_id: string; target_path: string };
export type ApproveReportRequest = { approved_by: string; note?: string };

const API = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    signal: init.signal ?? signal,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: string; error?: string };
      detail = body.detail ?? body.error ?? detail;
    } catch { /* keep the HTTP status */ }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function list<T>(value: T[] | { programs?: T[]; audits?: T[]; findings?: T[]; reports?: T[] }): T[] {
  if (Array.isArray(value)) return value;
  const record = value as { programs?: T[]; audits?: T[]; findings?: T[]; reports?: T[] };
  return record.programs ?? record.audits ?? record.findings ?? record.reports ?? [];
}

export class SecurityApiClient {
  constructor(private readonly baseSignal?: AbortSignal) {}

  async getPrograms(signal?: AbortSignal): Promise<SecurityProgram[]> {
    return list(await request<SecurityProgram[] | { programs?: SecurityProgram[] }>("/api/security/programs", {}, signal ?? this.baseSignal));
  }
  async importProgram(body: ImportProgramRequest, signal?: AbortSignal): Promise<SecurityProgram> {
    return request<SecurityProgram>("/api/security/programs/import", { method: "POST", body: JSON.stringify(body) }, signal ?? this.baseSignal);
  }
  async createAudit(body: CreateAuditRequest, signal?: AbortSignal): Promise<SecurityAudit> {
    return request<SecurityAudit>("/api/security/audits", { method: "POST", body: JSON.stringify(body) }, signal ?? this.baseSignal);
  }
  async getAudits(signal?: AbortSignal): Promise<SecurityAudit[]> {
    return list(await request<SecurityAudit[] | { audits?: SecurityAudit[] }>("/api/security/audits", {}, signal ?? this.baseSignal));
  }
  async getFindings(signal?: AbortSignal): Promise<SecurityFinding[]> {
    return list(await request<SecurityFinding[] | { findings?: SecurityFinding[] }>("/api/security/findings", {}, signal ?? this.baseSignal));
  }
  async getReports(signal?: AbortSignal): Promise<SecurityReport[]> {
    return list(await request<SecurityReport[] | { reports?: SecurityReport[] }>("/api/security/reports", {}, signal ?? this.baseSignal));
  }
  async approveReport(id: string, body: ApproveReportRequest, signal?: AbortSignal): Promise<SecurityReport> {
    if (!id.trim()) throw new Error("A report id is required.");
    return request<SecurityReport>(`/api/security/reports/${encodeURIComponent(id)}/approve`, { method: "POST", body: JSON.stringify(body) }, signal ?? this.baseSignal);
  }
}
