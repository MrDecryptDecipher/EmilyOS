import type { Address, CapabilityReport, ChainId, Eip1193Provider, Eip1559TransactionRequest, Eip2255Permission, Eip712TypedData, Hex, SignatureVerificationMetadata, WalletCall, CaipAccount, Eip1102Accounts } from "../types/wallet";

const HEX = /^0x[0-9a-fA-F]*$/;
const ADDRESS = /^0x[0-9a-fA-F]{40}$/;
export function normalizeAddress(value: string): Address { if (!ADDRESS.test(value)) throw new Error("Invalid EVM address"); return (`0x${value.slice(2).toLowerCase()}`) as Address; }
export function parseChainId(value: string | number | bigint): ChainId { const n = typeof value === "string" ? (value.trim().toLowerCase().startsWith("0x") ? BigInt(value) : BigInt(value.trim())) : BigInt(value); if (n < 0n) throw new Error("Chain id must be positive"); return (`0x${n.toString(16)}`) as ChainId; }
export function hexQuantity(value: bigint | number): Hex { const n = BigInt(value); if (n < 0n) throw new Error("Quantity must be positive"); return (`0x${n.toString(16) || "0"}`) as Hex; }
function bytes(value: string): string { if (!HEX.test(value) || value.length % 2) throw new Error("Invalid hex"); return value.slice(2); }
function word(value: bigint | number): string { return BigInt(value).toString(16).padStart(64, "0"); }
function addressWord(value: string): string { return normalizeAddress(value).slice(2).padStart(64, "0"); }
function dynamicBytes(value: string): string { const b = bytes(value); return word(b.length / 2) + b.padEnd(Math.ceil(b.length / 64) * 64, "0"); }
const SELECTORS = { erc20Transfer: "a9059cbb", erc20Approve: "095ea7b3", erc721TransferFrom: "23b872dd", erc721SafeTransferFrom: "42842e0e", erc1155SafeTransferFrom: "f242432a", erc1155SafeBatchTransferFrom: "2eb2c2d6" } as const;
export function encodeErc20Transfer(to: string, amount: bigint): Hex { return (`0x${SELECTORS.erc20Transfer}${addressWord(to)}${word(amount)}`) as Hex; }
export function encodeErc20Approve(spender: string, amount: bigint): Hex { return (`0x${SELECTORS.erc20Approve}${addressWord(spender)}${word(amount)}`) as Hex; }
export function encodeErc721Transfer(from: string, to: string, tokenId: bigint, safe = false): Hex { return (`0x${safe ? SELECTORS.erc721SafeTransferFrom : SELECTORS.erc721TransferFrom}${addressWord(from)}${addressWord(to)}${word(tokenId)}`) as Hex; }
export function encodeErc1155Transfer(from: string, to: string, id: bigint, amount: bigint, data: Hex = "0x"): Hex { const tail = dynamicBytes(data); return (`0x${SELECTORS.erc1155SafeTransferFrom}${addressWord(from)}${addressWord(to)}${word(id)}${word(amount)}${word(160)}${tail}`) as Hex; }
export function encodeErc1155BatchTransfer(from: string, to: string, ids: readonly bigint[], amounts: readonly bigint[], data: Hex = "0x"): Hex { if (!ids.length || ids.length !== amounts.length) throw new Error("IDs and amounts must have equal non-zero length"); const idsData = word(ids.length) + ids.map(word).join(""); const amountsData = word(amounts.length) + amounts.map(word).join(""); const idsOffset = 32 * 5; const amountsOffset = idsOffset + idsData.length / 2; const dataOffset = amountsOffset + amountsData.length / 2; return (`0x${SELECTORS.erc1155SafeBatchTransferFrom}${addressWord(from)}${addressWord(to)}${word(idsOffset)}${word(amountsOffset)}${word(dataOffset)}${idsData}${amountsData}${dynamicBytes(data)}`) as Hex; }
export function buildEip1559Transaction(input: Omit<Eip1559TransactionRequest, "type"> & { chainId: string | number | bigint }): Eip1559TransactionRequest { const result: Eip1559TransactionRequest = { ...input, chainId: parseChainId(input.chainId), type: "0x2" }; if (result.to) result.to = normalizeAddress(result.to); if (result.from) result.from = normalizeAddress(result.from); return result; }

export function typedDataParams(data: Eip712TypedData): [Address | undefined, string] { const address = typeof data.message.from === "string" ? normalizeAddress(data.message.from) : undefined; return [address, JSON.stringify({ ...data, domain: { ...data.domain, chainId: data.domain.chainId?.toString() } })]; }
export async function requestOptInAccounts(provider: Eip1193Provider): Promise<Eip1102Accounts> { const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" }); return { accounts: accounts.map(normalizeAddress), optedIn: true }; }
export async function readPermissionState(provider: Eip1193Provider): Promise<Eip2255Permission[]> { const permissions = await provider.request<Eip2255Permission[]>({ method: "wallet_getPermissions" }); return permissions ?? []; }
export async function signTypedData(provider: Eip1193Provider, account: string, data: Eip712TypedData): Promise<Hex> { const normalized = normalizeAddress(account); const [, json] = typedDataParams(data); return provider.request<Hex>({ method: "eth_signTypedData_v4", params: [normalized, json] }); }
export async function detectWalletCapabilities(provider: Eip1193Provider, chainId: ChainId): Promise<WalletCapabilitiesResult> { try { const capabilities = await provider.request<Record<string, unknown>>({ method: "wallet_getCapabilities", params: [chainId] }); return { eip5792: { standard: "EIP-5792", supported: true, details: capabilities }, erc4337: capabilityFrom(capabilities, "erc4337"), erc7769: capabilityFrom(capabilities, "erc7769"), eip7702: capabilityFrom(capabilities, "eip7702") }; } catch { return { eip5792: { standard: "EIP-5792", supported: false }, erc4337: { standard: "ERC-4337", supported: false }, erc7769: { standard: "ERC-7769", supported: false }, eip7702: { standard: "EIP-7702", supported: false, details: { authorizationRequests: false } } }; } }
export interface WalletCapabilitiesResult { eip5792: CapabilityReport; erc4337: CapabilityReport; erc7769: CapabilityReport; eip7702: CapabilityReport; }
function capabilityFrom(capabilities: Record<string, unknown>, key: string): CapabilityReport { return { standard: key === "eip7702" ? "EIP-7702" : key === "erc4337" ? "ERC-4337" : "ERC-7769", supported: Object.prototype.hasOwnProperty.call(capabilities, key), details: { authorizationRequests: false } }; }
export function sendCallsRequest(from: string, calls: WalletCall[], chainId?: ChainId): { method: "wallet_sendCalls"; params: [{ version: "1.0"; from: Address; calls: WalletCall[]; chainId?: ChainId }] } { return { method: "wallet_sendCalls", params: [{ version: "1.0", from: normalizeAddress(from), calls: buildCalls(calls), ...(chainId ? { chainId } : {}) }] }; }
export function caipAccount(chainId: string, address: string): CaipAccount { const normalizedChain = chainId.includes(":") ? chainId : `eip155:${parseChainId(chainId).slice(2)}`; const normalized = normalizeAddress(address); return { chainId: normalizedChain, address: normalized, caip10: `${normalizedChain}:${normalized}` }; }
export function capability(provider: Eip1193Provider, name: string): CapabilityReport { return { standard: name, supported: Boolean(provider) }; }
export function detectProviderFeatures(provider: Eip1193Provider): Record<string, CapabilityReport> {
  // A provider object proves EIP-1193 only. Other standards require probing a
  // method or an on-chain contract; claiming support here would mislead users.
  return {
    "eip-1193": capability(provider, "EIP-1193"),
    "eip-2255": { standard: "EIP-2255", supported: false, details: { probe: "wallet_getPermissions" } },
    "eip-5792": { standard: "EIP-5792", supported: false, details: { probe: "wallet_sendCalls" } },
    "eip-7702": { standard: "EIP-7702", supported: false, details: { authorizationRequests: false } },
    "erc-4337": { standard: "ERC-4337", supported: false, details: { probe: "eth_supportedEntryPoints" } },
    "erc-7769": { standard: "ERC-7769", supported: false, details: { probe: "eth_supportedEntryPoints" } },
  };
}
export function buildCalls(calls: WalletCall[]): WalletCall[] { return calls.map((call) => ({ ...call, to: normalizeAddress(call.to) })); }
export function erc1271Metadata(contract: string, signature: Hex): SignatureVerificationMetadata { return { standard: "ERC-1271", contract: normalizeAddress(contract), magicValue: "0x1626ba7e", callData: signature }; }
export function erc6492Metadata(factory: string, contract: string, factoryCalldata: Hex, signature: Hex): SignatureVerificationMetadata { return { standard: "ERC-6492", contract: normalizeAddress(contract), factory: normalizeAddress(factory), deploymentCalldata: factoryCalldata, magicValue: "0x1626ba7e", callData: signature }; }
