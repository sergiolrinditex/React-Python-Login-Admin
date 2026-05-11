// GENERATED FILE - do not edit by hand.
// Source: orchestrator-state/tasks/api-contracts/openapi.json
class ApiEndpointMeta {
  const ApiEndpointMeta({required this.operationId, required this.method, required this.path, required this.sliceIds, required this.journeyRefs, required this.pathParams});
  final String operationId;
  final String method;
  final String path;
  final List<String> sliceIds;
  final List<String> journeyRefs;
  final List<String> pathParams;
}
String buildApiPath(String path, Map<String, Object?> params) {
  var out = path;
  params.forEach((key, value) { out = out.replaceAll('{$key}', Uri.encodeComponent(value.toString())); });
  return out;
}
const apiEndpoints = <ApiEndpointMeta>[
  ApiEndpointMeta(operationId: "getApiV1AdminAiAgents", method: "GET", path: "/api/v1/admin/ai/agents", sliceIds: ["P02-S08-T001", "P04-S02-T005", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: []),
  ApiEndpointMeta(operationId: "patchApiV1AdminAiAgentsIdTools", method: "PATCH", path: "/api/v1/admin/ai/agents/{id}/tools", sliceIds: ["P02-S08-T001", "P04-S02-T005", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1AdminAiMcpServers", method: "GET", path: "/api/v1/admin/ai/mcp/servers", sliceIds: ["P02-S07-T001", "P04-S02-T003", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AdminAiMcpServers", method: "POST", path: "/api/v1/admin/ai/mcp/servers", sliceIds: ["P02-S07-T001", "P04-S02-T004", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AdminAiMcpServersIdSync", method: "POST", path: "/api/v1/admin/ai/mcp/servers/{id}/sync", sliceIds: ["P02-S07-T001", "P04-S02-T003", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "patchApiV1AdminAiMcpToolsId", method: "PATCH", path: "/api/v1/admin/ai/mcp/tools/{id}", sliceIds: ["P02-S07-T001", "P05-S01-T006"], journeyRefs: ["J105"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1AdminAiModels", method: "GET", path: "/api/v1/admin/ai/models", sliceIds: ["P02-S05-T001", "P04-S01-T002", "P04-S01-T003", "P05-S01-T004"], journeyRefs: ["J103"], pathParams: []),
  ApiEndpointMeta(operationId: "patchApiV1AdminAiModelsId", method: "PATCH", path: "/api/v1/admin/ai/models/{id}", sliceIds: ["P02-S05-T001", "P04-S01-T004", "P05-S01-T004"], journeyRefs: ["J103"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "postApiV1AdminAiModelsIdTest", method: "POST", path: "/api/v1/admin/ai/models/{id}/test", sliceIds: ["P02-S05-T002", "P04-S01-T004", "P05-S01-T004"], journeyRefs: ["J103"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1AdminAiProviders", method: "GET", path: "/api/v1/admin/ai/providers", sliceIds: ["P02-S05-T001", "P04-S01-T002", "P05-S01-T004"], journeyRefs: ["J103"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AdminAiProviders", method: "POST", path: "/api/v1/admin/ai/providers", sliceIds: ["P02-S05-T001", "P04-S01-T003", "P05-S01-T004"], journeyRefs: ["J103"], pathParams: []),
  ApiEndpointMeta(operationId: "getApiV1AdminAudit", method: "GET", path: "/api/v1/admin/audit", sliceIds: ["P04-S03-T001", "P05-S02-T001"], journeyRefs: ["J103", "J104", "J105"], pathParams: []),
  ApiEndpointMeta(operationId: "getApiV1AdminRagCollections", method: "GET", path: "/api/v1/admin/rag/collections", sliceIds: ["P02-S06-T002", "P04-S02-T002", "P05-S01-T005"], journeyRefs: ["J104"], pathParams: []),
  ApiEndpointMeta(operationId: "patchApiV1AdminRagCollectionsId", method: "PATCH", path: "/api/v1/admin/rag/collections/{id}", sliceIds: ["P02-S06-T002", "P04-S02-T002", "P05-S01-T005"], journeyRefs: ["J104"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1AdminRagDocuments", method: "GET", path: "/api/v1/admin/rag/documents", sliceIds: ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], journeyRefs: ["J104"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AdminRagDocuments", method: "POST", path: "/api/v1/admin/rag/documents", sliceIds: ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], journeyRefs: ["J104"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AdminRagDocumentsIdIndex", method: "POST", path: "/api/v1/admin/rag/documents/{id}/index", sliceIds: ["P02-S06-T001", "P04-S02-T001", "P05-S01-T005"], journeyRefs: ["J104"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1AdminUsage", method: "GET", path: "/api/v1/admin/usage", sliceIds: ["P02-S05-T002", "P04-S01-T001", "P04-S03-T002"], journeyRefs: ["J103"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AgentsRuns", method: "POST", path: "/api/v1/agents/runs", sliceIds: ["P02-S08-T001", "P04-S02-T005"], journeyRefs: ["J105"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1Auth2faVerify", method: "POST", path: "/api/v1/auth/2fa/verify", sliceIds: ["P01-S02-T006", "P03-S01-T005", "P05-S01-T001"], journeyRefs: ["J100"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthForgotPassword", method: "POST", path: "/api/v1/auth/forgot-password", sliceIds: ["P01-S02-T005", "P03-S01-T003"], journeyRefs: ["J100"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthLogout", method: "POST", path: "/api/v1/auth/logout", sliceIds: ["P01-S02-T004", "P03-S02-T004"], journeyRefs: ["J102"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthRefresh", method: "POST", path: "/api/v1/auth/refresh", sliceIds: ["P01-S02-T003", "P01-S03-T001"], journeyRefs: ["J100", "J102"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthResetPassword", method: "POST", path: "/api/v1/auth/reset-password", sliceIds: ["P01-S02-T005"], journeyRefs: ["J100"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthSignIn", method: "POST", path: "/api/v1/auth/sign-in", sliceIds: ["P01-S02-T002", "P03-S01-T001", "P05-S01-T001"], journeyRefs: ["J100"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1AuthSignUp", method: "POST", path: "/api/v1/auth/sign-up", sliceIds: ["P01-S02-T001", "P03-S01-T002"], journeyRefs: ["J100"], pathParams: []),
  ApiEndpointMeta(operationId: "getApiV1ChatConversations", method: "GET", path: "/api/v1/chat/conversations", sliceIds: ["P02-S03-T001", "P03-S02-T003", "P05-S01-T003"], journeyRefs: ["J101", "J102"], pathParams: []),
  ApiEndpointMeta(operationId: "postApiV1ChatConversations", method: "POST", path: "/api/v1/chat/conversations", sliceIds: ["P02-S03-T001", "P03-S02-T001", "P05-S01-T002"], journeyRefs: ["J101", "J102", "J100"], pathParams: []),
  ApiEndpointMeta(operationId: "getApiV1ChatConversationsId", method: "GET", path: "/api/v1/chat/conversations/{id}", sliceIds: ["P02-S03-T001", "P03-S02-T002", "P05-S01-T002", "P05-S01-T003"], journeyRefs: ["J101", "J102"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "postApiV1ChatConversationsIdStream", method: "POST", path: "/api/v1/chat/conversations/{id}/stream", sliceIds: ["P02-S03-T002", "P03-S02-T002", "P05-S01-T002"], journeyRefs: ["J101", "J102"], pathParams: ["id"]),
  ApiEndpointMeta(operationId: "getApiV1UsersMe", method: "GET", path: "/api/v1/users/me", sliceIds: ["P01-S02-T007", "P01-S03-T001", "P03-S02-T001", "P03-S02-T004", "P05-S01-T001"], journeyRefs: ["J100", "J102", "J101"], pathParams: []),
  ApiEndpointMeta(operationId: "patchApiV1UsersMeLanguage", method: "PATCH", path: "/api/v1/users/me/language", sliceIds: ["P01-S02-T007", "P03-S02-T004", "P05-S01-T003"], journeyRefs: ["J100", "J102"], pathParams: []),
  ApiEndpointMeta(operationId: "getHealth", method: "GET", path: "/health", sliceIds: ["P00-S01-T001", "P00-S02-T002"], journeyRefs: [], pathParams: []),
  ApiEndpointMeta(operationId: "getLive", method: "GET", path: "/live", sliceIds: ["P00-S02-T002"], journeyRefs: [], pathParams: []),
  ApiEndpointMeta(operationId: "getReady", method: "GET", path: "/ready", sliceIds: ["P00-S02-T002"], journeyRefs: [], pathParams: []),
];
abstract class ApiTransport {
  Future<Map<String, dynamic>> send(ApiEndpointMeta endpoint, {Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body});
}
class ApiClient {
  ApiClient(this.transport);
  final ApiTransport transport;
  Future<Map<String, dynamic>> requestByOperation(String operationId, {Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    final endpoint = apiEndpoints.firstWhere((e) => e.operationId == operationId);
    return transport.send(endpoint, pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminAiAgents({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminAiAgents', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> patchApiV1AdminAiAgentsIdTools({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('patchApiV1AdminAiAgentsIdTools', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminAiMcpServers({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminAiMcpServers', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminAiMcpServers({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminAiMcpServers', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminAiMcpServersIdSync({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminAiMcpServersIdSync', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> patchApiV1AdminAiMcpToolsId({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('patchApiV1AdminAiMcpToolsId', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminAiModels({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminAiModels', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> patchApiV1AdminAiModelsId({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('patchApiV1AdminAiModelsId', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminAiModelsIdTest({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminAiModelsIdTest', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminAiProviders({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminAiProviders', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminAiProviders({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminAiProviders', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminAudit({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminAudit', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminRagCollections({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminRagCollections', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> patchApiV1AdminRagCollectionsId({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('patchApiV1AdminRagCollectionsId', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminRagDocuments({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminRagDocuments', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminRagDocuments({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminRagDocuments', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AdminRagDocumentsIdIndex({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AdminRagDocumentsIdIndex', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1AdminUsage({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1AdminUsage', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AgentsRuns({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AgentsRuns', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1Auth2faVerify({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1Auth2faVerify', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthForgotPassword({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthForgotPassword', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthLogout({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthLogout', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthRefresh({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthRefresh', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthResetPassword({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthResetPassword', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthSignIn({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthSignIn', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1AuthSignUp({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1AuthSignUp', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1ChatConversations({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1ChatConversations', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1ChatConversations({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1ChatConversations', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1ChatConversationsId({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1ChatConversationsId', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> postApiV1ChatConversationsIdStream({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('postApiV1ChatConversationsIdStream', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getApiV1UsersMe({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getApiV1UsersMe', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> patchApiV1UsersMeLanguage({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('patchApiV1UsersMeLanguage', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getHealth({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getHealth', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getLive({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getLive', pathParams: pathParams, query: query, body: body);
  }
  Future<Map<String, dynamic>> getReady({Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {
    return requestByOperation('getReady', pathParams: pathParams, query: query, body: body);
  }
}
