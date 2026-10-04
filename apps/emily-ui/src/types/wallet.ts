/** Standards-facing wallet types. No secret material is represented here. */
export type Hex = `0x${string}`;
export type Address = `0x${string}`;
export type ChainId = `0x${string}`;

export interface Eip1193Provider {
  request<T = unknown>(args: { method: string; params?: readonly unknown[] | object }): Promise<T>;
  on?: (event: string, listener: (...args: unknown[]) => void) => void;
  removeListener?: (event: string, listener: (...args: unknown[]) => void) => void;
}
export interface Eip6963ProviderInfo { uuid: string; name: string; icon: string; rdns: string; }
export interface Eip6963ProviderDetail { info: Eip6963ProviderInfo; provider: Eip1193Provider; }
export interface Eip6963AnnounceEvent extends Event { detail: Eip6963ProviderDetail; }

export interface Eip1193RequestError { code?: number; message: string; data?: unknown; }
export interface Eip2255Permission { invoker: string; parentCapability: string; caveats: Array<{ type: string; value: unknown }>; }
export interface Eip1102Accounts { accounts: Address[]; optedIn: boolean; }
export interface WalletCapabilities { [chainId: string]: Record<string, unknown>; }
export interface Eip712Domain { name?: string; version?: string; chainId?: bigint | number | string; verifyingContract?: Address; salt?: Hex; [key: string]: unknown; }
export type Eip712Types = Record<string, Array<{ name: string; type: string }>>;
export interface Eip712TypedData { domain: Eip712Domain; types: Eip712Types; primaryType: string; message: Record<string, unknown>; }
export interface WalletCall { to: Address; data?: Hex; value?: Hex; }
export interface Eip1559TransactionRequest { from?: Address; to?: Address; data?: Hex; value?: Hex; nonce?: Hex; gas?: Hex; maxFeePerGas?: Hex; maxPriorityFeePerGas?: Hex; chainId?: ChainId; type?: "0x2"; }
export interface SendCallsRequest { version: "1.0"; from: Address; calls: WalletCall[]; chainId?: ChainId; capabilities?: Record<string, unknown>; }
export interface CapabilityReport { supported: boolean; standard: string; details?: Record<string, unknown>; }
export interface SignatureVerificationMetadata { standard: "ERC-1271" | "ERC-6492"; contract: Address; magicValue: Hex; callData?: Hex; factory?: Address; deploymentCalldata?: Hex; }

export type Ecosystem = "evm" | "solana" | "bitcoin" | "ton" | "stellar" | "aptos" | "algorand" | "hedera" | "near" | "xrpl";
export interface ChainInfo { namespace: Ecosystem; reference: string; caip2: string; name: string; network: "mainnet" | "testnet" | "devnet"; walletSupport: "injected-active" | "registry-only"; }
export interface WalletConnection { provider: Eip1193Provider; info?: Eip6963ProviderInfo; accounts: Address[]; chainId: ChainId; }
export interface CaipAccount { chainId: string; address: string; caip10: string; }

declare global {
  interface Window { ethereum?: Eip1193Provider; }
  interface WindowEventMap { "eip6963:announceProvider": Eip6963AnnounceEvent; }
}
