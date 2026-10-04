import type { Address, Eip6963ProviderDetail, Eip1193Provider, WalletConnection } from "../types/wallet";
export class WalletManager {
  private providers = new Map<string, Eip6963ProviderDetail>(); private listeners = new Set<() => void>(); private connected?: WalletConnection;
  discover(): Eip6963ProviderDetail[] { if (typeof window === "undefined") return []; if (window.ethereum && !this.providers.has("legacy")) this.providers.set("legacy", { info: { uuid: "legacy", name: "Injected wallet", icon: "", rdns: "legacy" }, provider: window.ethereum }); const event = (e: Event) => { const detail = (e as CustomEvent<Eip6963ProviderDetail>).detail; if (detail?.info?.uuid) { this.providers.set(detail.info.uuid, detail); this.listeners.forEach((fn) => fn()); } }; window.addEventListener("eip6963:announceProvider", event); window.dispatchEvent(new Event("eip6963:requestProvider")); window.setTimeout(() => window.removeEventListener("eip6963:announceProvider", event), 250); return [...this.providers.values()]; }
  subscribe(listener: () => void): () => void { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  getProviders(): Eip6963ProviderDetail[] { return [...this.providers.values()]; }
  getConnection(): WalletConnection | undefined { return this.connected; }
  async connect(provider: Eip1193Provider): Promise<WalletConnection> { const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" }); const chain = await provider.request<string>({ method: "eth_chainId" }); const connection: WalletConnection = { provider, info: [...this.providers.values()].find((p) => p.provider === provider)?.info, accounts: accounts.map((a) => a as Address), chainId: chain as `0x${string}` }; this.connected = connection; this.listeners.forEach((fn) => fn()); return connection; }
  disconnect(): void { this.connected = undefined; this.listeners.forEach((fn) => fn()); }
}
export function createWalletManager(): WalletManager { return new WalletManager(); }
