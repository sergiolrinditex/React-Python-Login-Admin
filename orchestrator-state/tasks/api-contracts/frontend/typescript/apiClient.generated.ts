// GENERATED FILE - do not edit by hand.
// Source: orchestrator-state/tasks/api-contracts/openapi.json
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';
export interface ApiEndpointMeta { operationId: string; method: HttpMethod; path: string; sliceIds: string[]; journeyRefs: string[]; pathParams: string[]; }
export const API_ENDPOINTS: ApiEndpointMeta[] = [
  {"operationId": "getApiV1AdminAiAgents", "method": "GET", "path": "/api/v1/admin/ai/agents", "sliceIds": ["P02-S08-T001", "P04-S02-T005", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": []},
  {"operationId": "patchApiV1AdminAiAgentsIdTools", "method": "PATCH", "path": "/api/v1/admin/ai/agents/{id}/tools", "sliceIds": ["P02-S08-T001", "P04-S02-T005", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": ["id"]},
  {"operationId": "getApiV1AdminAiMcpServers", "method": "GET", "path": "/api/v1/admin/ai/mcp/servers", "sliceIds": ["P02-S07-T001", "P04-S02-T003", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": []},
  {"operationId": "postApiV1AdminAiMcpServers", "method": "POST", "path": "/api/v1/admin/ai/mcp/servers", "sliceIds": ["P02-S07-T001", "P04-S02-T004", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": []},
  {"operationId": "postApiV1AdminAiMcpServersIdSync", "method": "POST", "path": "/api/v1/admin/ai/mcp/servers/{id}/sync", "sliceIds": ["P02-S07-T001", "P04-S02-T003", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": ["id"]},
  {"operationId": "patchApiV1AdminAiMcpToolsId", "method": "PATCH", "path": "/api/v1/admin/ai/mcp/tools/{id}", "sliceIds": ["P02-S07-T001", "P05-S01-T006"], "journeyRefs": ["J105"], "pathParams": ["id"]},
  {"operationId": "getApiV1AdminAiModels", "method": "GET", "path": "/api/v1/admin/ai/models", "sliceIds": ["P02-S05-T001", "P04-S01-T002", "P04-S01-T003", "P05-S01-T004"], "journeyRefs": ["J103"], "pathParams": []},
  {"operationId": "patchApiV1AdminAiModelsId", "method": "PATCH", "path": "/api/v1/admin/ai/models/{id}", "sliceIds": ["P02-S05-T001", "P04-S01-T004", "P05-S01-T004"], "journeyRefs": ["J103"], "pathParams": ["id"]},
  {"operationId": "postApiV1AdminAiModelsIdTest", "method": "POST", "path": "/api/v1/admin/ai/models/{id}/test", "sliceIds": ["P02-S05-T002", "P04-S01-T004", "P05-S01-T004"], "journeyRefs": ["J103"], "pathParams": ["id"]},
  {"operationId": "getApiV1AdminAiProviders", "method": "GET", "path": "/api/v1/admin/ai/providers", "sliceIds": ["P02-S05-T001", "P04-S01-T002", "P05-S01-T004"], "journeyRefs": ["J103"], "pathParams": []},
  {"operationId": "postApiV1AdminAiProviders", "method": "POST", "path": "/api/v1/admin/ai/providers", "sliceIds": ["P02-S05-T001", "P04-S01-T003", "P05-S01-T004"], "journeyRefs": ["J103"], "pathParams": []},
  {"operationId": "getApiV1AdminAudit", "method": "GET", "path": "/api/v1/admin/audit", "sliceIds": ["P04-S03-T001", "P05-S02-T001"], "journeyRefs": ["J103", "J104", "J105"], "pathParams": []},
  {"operationId": "getApiV1AdminRagCollections", "method": "GET", "path": "/api/v1/admin/rag/collections", "sliceIds": ["P02-S06-T002", "P04-S02-T002", "P05-S01-T005"], "journeyRefs": ["J104"], "pathParams": []},
  {"operationId": "patchApiV1AdminRagCollectionsId", "method": "PATCH", "path": "/api/v1/admin/rag/collections/{id}", "sliceIds": ["P02-S06-T002", "P04-S02-T002", "P05-S01-T005"], "journeyRefs": ["J104"], "pathParams": ["id"]},
  {"operationId": "getApiV1AdminRagDocuments", "method": "GET", "path": "/api/v1/admin/rag/documents", "sliceIds": ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], "journeyRefs": ["J104"], "pathParams": []},
  {"operationId": "postApiV1AdminRagDocuments", "method": "POST", "path": "/api/v1/admin/rag/documents", "sliceIds": ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], "journeyRefs": ["J104"], "pathParams": []},
  {"operationId": "postApiV1AdminRagDocumentsIdIndex", "method": "POST", "path": "/api/v1/admin/rag/documents/{id}/index", "sliceIds": ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], "journeyRefs": ["J104"], "pathParams": ["id"]},
  {"operationId": "getApiV1AdminUsage", "method": "GET", "path": "/api/v1/admin/usage", "sliceIds": ["P02-S05-T002", "P04-S01-T001", "P04-S03-T002"], "journeyRefs": ["J103"], "pathParams": []},
  {"operationId": "postApiV1AgentsRuns", "method": "POST", "path": "/api/v1/agents/runs", "sliceIds": ["P02-S08-T001", "P04-S02-T005"], "journeyRefs": ["J105"], "pathParams": []},
  {"operationId": "postApiV1Auth2faVerify", "method": "POST", "path": "/api/v1/auth/2fa/verify", "sliceIds": ["P01-S02-T006", "P03-S01-T005", "P05-S01-T001"], "journeyRefs": ["J100"], "pathParams": []},
  {"operationId": "postApiV1AuthForgotPassword", "method": "POST", "path": "/api/v1/auth/forgot-password", "sliceIds": ["P01-S02-T005", "P03-S01-T003"], "journeyRefs": ["J100"], "pathParams": []},
  {"operationId": "postApiV1AuthLogout", "method": "POST", "path": "/api/v1/auth/logout", "sliceIds": ["P01-S02-T004", "P03-S02-T004"], "journeyRefs": ["J102"], "pathParams": []},
  {"operationId": "postApiV1AuthRefresh", "method": "POST", "path": "/api/v1/auth/refresh", "sliceIds": ["P01-S02-T003", "P01-S03-T001"], "journeyRefs": ["J100", "J102"], "pathParams": []},
  {"operationId": "postApiV1AuthResetPassword", "method": "POST", "path": "/api/v1/auth/reset-password", "sliceIds": ["P01-S02-T005"], "journeyRefs": ["J100"], "pathParams": []},
  {"operationId": "postApiV1AuthSignIn", "method": "POST", "path": "/api/v1/auth/sign-in", "sliceIds": ["P01-S02-T002", "P03-S01-T001", "P05-S01-T001"], "journeyRefs": ["J100"], "pathParams": []},
  {"operationId": "postApiV1AuthSignUp", "method": "POST", "path": "/api/v1/auth/sign-up", "sliceIds": ["P01-S02-T001", "P03-S01-T002"], "journeyRefs": ["J100"], "pathParams": []},
  {"operationId": "getApiV1ChatConversations", "method": "GET", "path": "/api/v1/chat/conversations", "sliceIds": ["P02-S03-T001", "P03-S02-T003", "P05-S01-T003"], "journeyRefs": ["J101", "J102"], "pathParams": []},
  {"operationId": "postApiV1ChatConversations", "method": "POST", "path": "/api/v1/chat/conversations", "sliceIds": ["P02-S03-T001", "P03-S02-T001", "P05-S01-T002"], "journeyRefs": ["J101", "J102", "J100"], "pathParams": []},
  {"operationId": "getApiV1ChatConversationsId", "method": "GET", "path": "/api/v1/chat/conversations/{id}", "sliceIds": ["P02-S03-T001", "P03-S02-T002", "P05-S01-T002", "P05-S01-T003"], "journeyRefs": ["J101", "J102"], "pathParams": ["id"]},
  {"operationId": "postApiV1ChatConversationsIdStream", "method": "POST", "path": "/api/v1/chat/conversations/{id}/stream", "sliceIds": ["P02-S03-T002", "P03-S02-T002", "P05-S01-T002"], "journeyRefs": ["J101", "J102"], "pathParams": ["id"]},
  {"operationId": "getApiV1UsersMe", "method": "GET", "path": "/api/v1/users/me", "sliceIds": ["P01-S02-T007", "P01-S03-T001", "P03-S02-T001", "P03-S02-T004", "P05-S01-T001"], "journeyRefs": ["J100", "J102", "J101"], "pathParams": []},
  {"operationId": "patchApiV1UsersMeLanguage", "method": "PATCH", "path": "/api/v1/users/me/language", "sliceIds": ["P01-S02-T007", "P03-S02-T004", "P05-S01-T003"], "journeyRefs": ["J100", "J102"], "pathParams": []},
  {"operationId": "getHealth", "method": "GET", "path": "/health", "sliceIds": ["P00-S01-T001", "P00-S02-T002"], "journeyRefs": [], "pathParams": []},
  {"operationId": "getLive", "method": "GET", "path": "/live", "sliceIds": ["P00-S02-T002"], "journeyRefs": [], "pathParams": []},
  {"operationId": "getReady", "method": "GET", "path": "/ready", "sliceIds": ["P00-S02-T002"], "journeyRefs": [], "pathParams": []},
];
export function buildPath(path: string, params: Record<string, string | number> = {}): string {
  return path.replace(/\{([^}]+)\}/g, (_m, key) => encodeURIComponent(String(params[key] ?? '')));
}
export interface ApiClientOptions { baseUrl?: string; fetchImpl?: typeof fetch; defaultHeaders?: Record<string, string>; }
export class ApiClient {
  constructor(private readonly opts: ApiClientOptions = {}) {}
  async request<T = Json>(meta: ApiEndpointMeta, args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}): Promise<T> {
    const fetcher = this.opts.fetchImpl ?? fetch;
    const url = new URL((this.opts.baseUrl ?? '') + buildPath(meta.path, args.pathParams));
    for (const [key, value] of Object.entries(args.query ?? {})) if (value !== undefined) url.searchParams.set(key, String(value));
    const res = await fetcher(url.toString(), { method: meta.method, headers: { 'content-type': 'application/json', ...(this.opts.defaultHeaders ?? {}), ...(args.headers ?? {}) }, body: args.body === undefined ? undefined : JSON.stringify(args.body) });
    if (!res.ok) throw new Error(`${meta.method} ${meta.path} failed with ${res.status}`);
    return (await res.json()) as T;
  }
  getApiV1AdminAiAgents(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[0], args);
  }
  patchApiV1AdminAiAgentsIdTools(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[1], args);
  }
  getApiV1AdminAiMcpServers(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[2], args);
  }
  postApiV1AdminAiMcpServers(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[3], args);
  }
  postApiV1AdminAiMcpServersIdSync(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[4], args);
  }
  patchApiV1AdminAiMcpToolsId(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[5], args);
  }
  getApiV1AdminAiModels(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[6], args);
  }
  patchApiV1AdminAiModelsId(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[7], args);
  }
  postApiV1AdminAiModelsIdTest(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[8], args);
  }
  getApiV1AdminAiProviders(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[9], args);
  }
  postApiV1AdminAiProviders(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[10], args);
  }
  getApiV1AdminAudit(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[11], args);
  }
  getApiV1AdminRagCollections(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[12], args);
  }
  patchApiV1AdminRagCollectionsId(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[13], args);
  }
  getApiV1AdminRagDocuments(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[14], args);
  }
  postApiV1AdminRagDocuments(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[15], args);
  }
  postApiV1AdminRagDocumentsIdIndex(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[16], args);
  }
  getApiV1AdminUsage(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[17], args);
  }
  postApiV1AgentsRuns(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[18], args);
  }
  postApiV1Auth2faVerify(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[19], args);
  }
  postApiV1AuthForgotPassword(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[20], args);
  }
  postApiV1AuthLogout(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[21], args);
  }
  postApiV1AuthRefresh(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[22], args);
  }
  postApiV1AuthResetPassword(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[23], args);
  }
  postApiV1AuthSignIn(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[24], args);
  }
  postApiV1AuthSignUp(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[25], args);
  }
  getApiV1ChatConversations(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[26], args);
  }
  postApiV1ChatConversations(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[27], args);
  }
  getApiV1ChatConversationsId(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[28], args);
  }
  postApiV1ChatConversationsIdStream(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[29], args);
  }
  getApiV1UsersMe(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[30], args);
  }
  patchApiV1UsersMeLanguage(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[31], args);
  }
  getHealth(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[32], args);
  }
  getLive(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[33], args);
  }
  getReady(args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}) {
    return this.request(API_ENDPOINTS[34], args);
  }
}
