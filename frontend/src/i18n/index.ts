/**
 * Hilo People — i18n bootstrap with real ES/EN/FR resources.
 *
 * Slice/Phase: P00-S01-T005 — i18n resources ES/EN/FR / Phase 0 Scaffold.
 *
 * Responsibility: initialise the i18next singleton with all 8 namespaces loaded
 *   inline for 3 locales (ES, EN, FR) with fallback to Spanish. Replaces the
 *   resource-less stub created in T002.
 *
 * Design decisions (from task pack §8.3 and instrucciones.md §3.3):
 *   - Detector OFF: i18next-browser-languagedetector crashes jsdom (inherited T002 R1).
 *     Activation deferred to AccountPage (P03-S02-T004).
 *   - Inline static resources: no HTTP backend, no lazy-load. 8ns × 3 langs ≈ 5KB gzip.
 *   - Interpolation simple {{var}}: no ICU (not needed in P0).
 *   - saveMissing: false, missingKeyHandler: false (silence warnings; real keys added here).
 *
 * Wire contract: providers.tsx imports `default i18n` from this file and passes it
 *   to <I18nextProvider>. The default export must always be the singleton instance.
 *   Do NOT change the module shape — downstream providers.tsx has i18n?: I18nType.
 *
 * Logging: BEFORE/AFTER init, gated by VITE_ENABLE_VERBOSE_LOGGING. No PII.
 *
 * Key deps: i18next ^26.1.0, react-i18next ^17.0.7.
 * Source ref: instrucciones.md §6, TECHNICAL_GUIDE §6.5, §11.1, UX_CONTRACT §4.2.
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { DEFAULT_LANGUAGE, DEFAULT_NAMESPACE, I18N_NAMESPACES } from "./languages";

// ---------------------------------------------------------------------------
// Verbose logging helper — gated by VITE_ENABLE_VERBOSE_LOGGING
// ---------------------------------------------------------------------------

/**
 * Emits a console.info message only when VITE_ENABLE_VERBOSE_LOGGING === "true".
 * Never logs PII, tokens, or secrets.
 *
 * @param msg - Log message.
 * @param rest - Additional structured data.
 */
function verboseLog(msg: string, ...rest: unknown[]): void {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info(msg, ...rest);
  }
}

// ---------------------------------------------------------------------------
// Translation resources — inline static bundles
// JSON bundles also live in frontend/public/locales/{lng}/{ns}.json for
// reference; they are NOT fetched at runtime (YAGNI HTTP backend in P0).
// ---------------------------------------------------------------------------

/**
 * All translation resources for ES, EN, and FR.
 * Each namespace matches a file in frontend/public/locales/{lng}/{ns}.json.
 * Sync any key changes here WITH the corresponding JSON file.
 */
const resources = {
  es: {
    common: {
      productName: "Hilo",
      actions: {
        continue: "Continuar",
        cancel: "Cancelar",
        save: "Guardar",
        retry: "Reintentar",
        back: "Volver",
      },
      states: {
        loading: "Cargando...",
        empty: "Sin resultados",
        success: "Operación completada",
      },
      language: { es: "Español", en: "Inglés", fr: "Francés" },
    },
    auth: {
      signIn: {
        actions: {
          forgot: "¿Olvidaste tu contraseña?",
          signUp: "Crear cuenta",
        },
        cta: "Acceder con tu cuenta",
        email: "Email corporativo",
        emailPlaceholder: "nombre@empresa.com",
        errors: {
          accountLocked: "Cuenta bloqueada temporalmente, intenta de nuevo más tarde.",
          emailFormat: "Introduce un email válido.",
          emailRequired: "El email es obligatorio.",
          invalidCredentials: "Email o contraseña incorrectos.",
          network: "Sin conexión. Comprueba tu red e inténtalo de nuevo.",
          passwordRequired: "La contraseña es obligatoria.",
          rateLimited: "Demasiados intentos. Espera {{seconds}} segundos e inténtalo de nuevo.",
          serverInternal: "Error interno del servidor. Inténtalo de nuevo más tarde.",
        },
        password: "Contraseña",
        passwordPlaceholder: "••••••••",
        status: { submitting: "Accediendo…" },
        submit: "Iniciar sesión",
        title: "Entrar",
        titleHint: "Área de empleados",
      },
      signUp: {
        title: "Crear cuenta",
        titleHint: "Área de empleados",
        email: "Email corporativo",
        emailPlaceholder: "nombre@empresa.com",
        fullName: "Nombre completo",
        fullNamePlaceholder: "Tu nombre y apellidos",
        password: "Contraseña",
        passwordPlaceholder: "••••••••",
        passwordHint: "Mínimo 12 caracteres con letras y números",
        legalAcceptance: "He leído y acepto los términos y condiciones",
        legalAcceptanceHint: "Requerido para crear tu cuenta",
        submit: "Crear cuenta",
        cta: "Crear tu cuenta",
        status: { submitting: "Creando cuenta…" },
        actions: { signIn: "¿Ya tienes cuenta? Inicia sesión" },
        successFlash: "Cuenta creada. Inicia sesión para acceder.",
        errors: {
          emailRequired: "El email es obligatorio.",
          emailFormat: "Introduce un email válido.",
          nonCorporateEmail: "Este email no es un email corporativo válido. Usa tu email de empresa.",
          fullNameRequired: "El nombre es obligatorio.",
          fullNameTooLong: "El nombre no puede superar los 200 caracteres.",
          passwordRequired: "La contraseña es obligatoria.",
          passwordTooShort: "La contraseña debe tener al menos 12 caracteres.",
          passwordPolicy: "La contraseña debe tener al menos 12 caracteres, una letra y un número.",
          legalRequired: "Debes aceptar los términos y condiciones para continuar.",
          legalNotAccepted: "Debes aceptar los términos y condiciones para continuar.",
          emailTaken: "No se pudo crear la cuenta con ese email. Si ya tienes cuenta, intenta iniciar sesión.",
          rateLimited: "Demasiados intentos. Espera {{seconds}} segundos e inténtalo de nuevo.",
          network: "Sin conexión. Comprueba tu red e inténtalo de nuevo.",
          serverInternal: "Error interno del servidor. Inténtalo de nuevo más tarde.",
          payloadInvalid: "Datos de registro no válidos. Comprueba los campos e inténtalo de nuevo.",
        },
      },
      forgot: {
        title: "Recuperar acceso",
        cta: "Enviar enlace de recuperación",
      },
      twoFactor: {
        title: "Verificación en dos pasos",
        codeLabel: "Código de verificación",
      },
    },
    chat: {
      empty: {
        title: "¿En qué puedo ayudarte?",
        subtitle: "Escribe tu pregunta para empezar",
        promptVacation: "¿Cuántos días de vacaciones me quedan?",
        promptMobility: "Política de movilidad interna",
      },
      citation: { label: "Fuente" },
      composer: {
        placeholder: "Escribe tu mensaje...",
        send: "Enviar",
        errors: {
          tooLong: "El mensaje no puede superar {{max}} caracteres.",
        },
      },
    },
    account: {
      title: "Mi cuenta",
      language: "Idioma",
      languageHint: "El idioma seleccionado se aplica a toda la interfaz",
      logout: "Cerrar sesión",
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      models: {
        title: "Modelos LiteLLM",
        table: {
          caption: "Lista de modelos AI",
          headers: {
            model: "Modelo",
            type: "Tipo",
            provider: "Proveedor",
            status: "Estado",
            default: "Por defecto",
            cost: "Coste",
            latency: "Latencia",
          },
        },
        status: {
          active: "Activo",
          modelDisabled: "Modelo desactivado",
          providerInactive: "Proveedor inactivo",
          bothInactive: "Ambos inactivos",
          unknown: "Desconocido",
        },
        default: {
          yes: "Sí",
          no: "—",
        },
        cost: {
          unknown: "—",
        },
        latency: {
          unknown: "—",
          value: "{{ms}} ms",
        },
        empty: {
          body: "Aún no hay modelos configurados. Crea un modelo para empezar.",
          cta: "Nuevo modelo",
        },
        errors: {
          network: {
            title: "No se pudieron cargar los modelos",
            body: "Comprueba tu conexión e inténtalo de nuevo.",
          },
          forbidden: {
            title: "Acceso restringido",
            body: "No tienes permisos de administrador para ver esta página.",
          },
        },
        actions: {
          retry: "Reintentar",
          newModel: "Nuevo modelo",
        },
      },
      mcp: { title: "Integraciones MCP", empty: "No hay integraciones activas" },
      dashboard: {
        title: "Resumen Admin AI",
        window: {
          range: "Últimos 30 días — {{from}} → {{to}}",
        },
        kpi: {
          invocations: "Invocaciones",
          tokens: "Tokens (in + out)",
          cost: "Coste estimado",
          latency: "Latencia media (ms)",
        },
        table: {
          caption: "Uso por modelo",
          headers: {
            model: "Modelo",
            invocations: "Invocaciones",
            tokensIn: "Tokens in",
            tokensOut: "Tokens out",
            cost: "Coste",
            latency: "Latencia",
          },
        },
        empty: {
          title: "Sin uso registrado",
          body: "Aún no hay actividad LLM en los últimos 30 días. Activa un modelo para empezar.",
        },
        errors: {
          network: {
            title: "No se pudo cargar el resumen",
            body: "Comprueba tu conexión e inténtalo de nuevo.",
          },
          forbidden: {
            title: "Acceso restringido",
            body: "No tienes permisos de administrador para ver esta página.",
          },
        },
        actions: {
          retry: "Reintentar",
          manageModels: "Gestionar modelos",
        },
      },
      nav: {
        dashboard: "Resumen",
        models: "Modelos",
        modelsNew: "Nuevo modelo",
        ragDocuments: "Documentos RAG",
        ragCollections: "Colecciones",
        mcpServers: "Servidores MCP",
        mcpNew: "Nuevo MCP",
        agents: "Agentes",
        audit: "Auditoría",
        usage: "Coste y latencias",
      },
    },
    rag: {
      documents: {
        title: "Documentos de People",
        heading: "Documentos RAG",
        subtitle: "Gestiona los documentos disponibles para búsqueda semántica",
        empty: "No hay documentos indexados",
        "empty.body": "Sube un documento PDF o DOCX para que el asistente pueda responder preguntas sobre su contenido.",
        "empty.cta": "Subir primer documento",
        upload: {
          cta: "Subir documento",
          uploading: "Subiendo…",
          submit: "Subir",
          dedup: "Documento existente reutilizado",
          fields: {
            title: "Título",
            language: "Idioma",
            "language.es": "Español",
            "language.en": "Inglés",
            "language.fr": "Francés",
            collection: "Colección",
            file: "Archivo (PDF o DOCX)",
            "file.hint": "PDF o DOCX · máx. 25 MiB",
          },
        },
        table: {
          col: {
            title: "Título",
            language: "Idioma",
            collection: "Colección",
            status: "Estado",
            actions: "Acciones",
          },
        },
        status: {
          uploaded: "Subido",
          pending: "Pendiente",
          processing: "Procesando",
          indexed: "Indexado",
          failed: "Fallido",
        },
        action: {
          index: "Indexar",
          "index.inProgress": "Indexando",
        },
        nav: {
          collections: "Ver colecciones →",
        },
        error: {
          network: "Error de conexión. Comprueba tu red e inténtalo de nuevo.",
          permission: "No tienes permiso para gestionar documentos. Necesitas el rol de administrador.",
          validation: {
            title: "El título es obligatorio.",
            language: "El idioma es obligatorio.",
            collection: "La colección es obligatoria.",
            file: "Selecciona un archivo PDF o DOCX.",
          },
          tooLarge: "El archivo supera el tamaño máximo de {{maxMb}} MiB.",
          indexInProgress: "Ya existe un trabajo de indexación en progreso (estado: {{status}}).",
        },
        aria: {
          uploading: "Subiendo documento…",
          indexing: "Indexando documento…",
          list: "Lista de documentos",
        },
      },
      // §D-T002-I18N: rag.collections.* added for RagCollectionsPage (P04-S02-T002)
      collections: {
        title: "Colecciones RAG",
        heading: "Colecciones RAG",
        subtitle: "Gestiona las colecciones y verticales disponibles para búsqueda semántica",
        empty: "No hay colecciones",
        "empty.body": "Cuando se creen colecciones desde el backend, aparecerán aquí.",
        table: {
          caption: "Tabla de colecciones RAG",
          col: {
            name: "Nombre",
            vertical: "Vertical",
            language: "Idioma",
            enabled: "Estado",
          },
        },
        enabled: { on: "Activa", off: "Inactiva" },
        language: { es: "Español", en: "Inglés", fr: "Francés", null: "—" },
        action: {
          update: "Guardar",
          updating: "Guardando…",
          saved: "Guardado",
        },
        error: {
          network: "Error de conexión. Comprueba tu red e inténtalo de nuevo.",
          permission: "No tienes permiso para gestionar colecciones. Necesitas el rol de administrador.",
          validation: {
            name: "El nombre no es válido.",
            vertical: "La vertical no es válida.",
            language: "El idioma no es válido.",
            enabled: "El estado no es válido.",
            body: "Cambia al menos un campo.",
          },
          notFound: "La colección ya no existe. Actualiza la lista.",
          rateLimited: "Demasiadas peticiones. Inténtalo más tarde.",
          internal: "Error del servidor. Inténtalo más tarde.",
        },
        nav: { documents: "← Ver documentos" },
        aria: {
          list: "Lista de colecciones",
          updating: "Actualizando colección…",
          enabled_toggle: "Activar o desactivar colección {{name}}",
        },
      },
    },
    // §D-T003-I18N: mcp.servers.* extended for McpServersPage (P04-S02-T003)
    mcp: {
      servers: {
        title: "Servidores MCP",
        subtitle: "Gestiona las integraciones de servidores MCP de tu organización",
        empty: "No hay servidores conectados",
        columns: {
          name: "Nombre",
          status: "Estado",
          transport: "Transporte",
          lastSync: "Última sincronización",
          toolCount: "Herramientas",
          risk: "Riesgo",
          actions: "Acciones",
        },
        status: {
          draft: "Borrador",
          active: "Activo",
          error: "Error",
          unknown: "Desconocido",
        },
        lastSync: {
          never: "Nunca",
          relative: "Hace {{relative}}",
        },
        actions: {
          sync: "Sincronizar",
          syncing: "Sincronizando…",
          synced: "Sincronizado",
          connectFirst: "Conectar primer servidor",
        },
        errors: {
          sync_not_found: "Servidor no encontrado",
          sync_rate_limited: "Demasiadas sincronizaciones, espera unos segundos",
          sync_internal: "Error interno del servidor",
        },
        notes: {
          risk_per_tool: "El nivel de riesgo se gestiona por herramienta en P04-S02-T004.",
        },
        tools: {
          none: "—",
        },
      },
    },
    errors: {
      AUTH_INVALID_CREDENTIALS: "Email o contraseña incorrectos",
      AUTH_MFA_REQUIRED: "Se requiere verificación en dos pasos",
      AUTH_SESSION_EXPIRED: "Tu sesión ha expirado. Por favor, inicia sesión de nuevo",
      AUTH_FORBIDDEN: "No tienes permiso para realizar esta acción",
      CHAT_STREAM_FAILED: "Error al recibir la respuesta. Por favor, inténtalo de nuevo",
      RAG_DOCUMENT_INVALID: "El documento no es válido o no puede procesarse",
      RAG_INDEX_IN_PROGRESS: "El documento se está indexando. Estará disponible en breve",
      AI_PROVIDER_TEST_FAILED: "La prueba de conexión con el proveedor de IA ha fallado",
      MCP_SERVER_UNREACHABLE: "No se puede conectar con el servidor MCP",
      MCP_TOOL_REQUIRES_APPROVAL: "Esta herramienta requiere aprobación antes de ejecutarse",
      AGENT_RUN_FAILED: "El agente no pudo completar la tarea",
      UNKNOWN: "Ha ocurrido un error inesperado",
      NETWORK: "Error de conexión. Comprueba tu red e inténtalo de nuevo",
    },
  },
  en: {
    common: {
      productName: "Hilo",
      actions: {
        continue: "Continue",
        cancel: "Cancel",
        save: "Save",
        retry: "Try again",
        back: "Back",
      },
      states: {
        loading: "Loading...",
        empty: "No results found",
        success: "Done",
      },
      language: { es: "Spanish", en: "English", fr: "French" },
    },
    auth: {
      signIn: {
        actions: {
          forgot: "Forgot your password?",
          signUp: "Create account",
        },
        cta: "Access with your account",
        email: "Corporate email",
        emailPlaceholder: "name@company.com",
        errors: {
          accountLocked: "Account temporarily locked. Please try again later.",
          emailFormat: "Enter a valid email address.",
          emailRequired: "Email is required.",
          invalidCredentials: "Incorrect email or password.",
          network: "No connection. Check your network and try again.",
          passwordRequired: "Password is required.",
          rateLimited: "Too many attempts. Wait {{seconds}} seconds and try again.",
          serverInternal: "Internal server error. Please try again later.",
        },
        password: "Password",
        passwordPlaceholder: "••••••••",
        status: { submitting: "Signing in…" },
        submit: "Sign in",
        title: "Sign in",
        titleHint: "Employee area",
      },
      signUp: {
        title: "Create account",
        titleHint: "Employee area",
        email: "Corporate email",
        emailPlaceholder: "name@company.com",
        fullName: "Full name",
        fullNamePlaceholder: "Your first and last name",
        password: "Password",
        passwordPlaceholder: "••••••••",
        passwordHint: "At least 12 characters with letters and numbers",
        legalAcceptance: "I have read and accept the terms and conditions",
        legalAcceptanceHint: "Required to create your account",
        submit: "Create account",
        cta: "Create your account",
        status: { submitting: "Creating account…" },
        actions: { signIn: "Already have an account? Sign in" },
        successFlash: "Account created. Sign in to access.",
        errors: {
          emailRequired: "Email is required.",
          emailFormat: "Enter a valid email address.",
          nonCorporateEmail: "This email is not a valid corporate email. Use your company email.",
          fullNameRequired: "Full name is required.",
          fullNameTooLong: "Full name cannot exceed 200 characters.",
          passwordRequired: "Password is required.",
          passwordTooShort: "Password must be at least 12 characters.",
          passwordPolicy: "Password must have at least 12 characters, one letter and one number.",
          legalRequired: "You must accept the terms and conditions to continue.",
          legalNotAccepted: "You must accept the terms and conditions to continue.",
          emailTaken: "Could not create an account with that email. If you already have an account, try signing in.",
          rateLimited: "Too many attempts. Wait {{seconds}} seconds and try again.",
          network: "No connection. Check your network and try again.",
          serverInternal: "Internal server error. Please try again later.",
          payloadInvalid: "Invalid registration data. Check the fields and try again.",
        },
      },
      forgot: {
        title: "Reset access",
        cta: "Send recovery link",
      },
      twoFactor: {
        title: "Two-step verification",
        codeLabel: "Verification code",
      },
    },
    chat: {
      empty: {
        title: "How can I help?",
        subtitle: "Type your question to get started",
        promptVacation: "How many vacation days do I have left?",
        promptMobility: "Internal mobility policy",
      },
      citation: { label: "Source" },
      composer: {
        placeholder: "Type your message...",
        send: "Send",
        errors: {
          tooLong: "Messages cannot exceed {{max}} characters.",
        },
      },
    },
    account: {
      title: "My account",
      language: "Language",
      languageHint: "The selected language applies to the entire interface",
      logout: "Sign out",
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      models: {
        title: "LiteLLM models",
        table: {
          caption: "AI models list",
          headers: {
            model: "Model",
            type: "Type",
            provider: "Provider",
            status: "Status",
            default: "Default",
            cost: "Cost",
            latency: "Latency",
          },
        },
        status: {
          active: "Active",
          modelDisabled: "Model disabled",
          providerInactive: "Provider inactive",
          bothInactive: "Both inactive",
          unknown: "Unknown",
        },
        default: {
          yes: "Yes",
          no: "—",
        },
        cost: {
          unknown: "—",
        },
        latency: {
          unknown: "—",
          value: "{{ms}} ms",
        },
        empty: {
          body: "No models configured yet. Create a model to get started.",
          cta: "New model",
        },
        errors: {
          network: {
            title: "Failed to load models",
            body: "Check your connection and try again.",
          },
          forbidden: {
            title: "Access restricted",
            body: "You do not have administrator permissions to view this page.",
          },
        },
        actions: {
          retry: "Retry",
          newModel: "New model",
        },
      },
      mcp: { title: "MCP integrations", empty: "No active integrations" },
      dashboard: {
        title: "Admin AI overview",
        window: {
          range: "Last 30 days — {{from}} → {{to}}",
        },
        kpi: {
          invocations: "Invocations",
          tokens: "Tokens (in + out)",
          cost: "Estimated cost",
          latency: "Avg latency (ms)",
        },
        table: {
          caption: "Usage by model",
          headers: {
            model: "Model",
            invocations: "Invocations",
            tokensIn: "Tokens in",
            tokensOut: "Tokens out",
            cost: "Cost",
            latency: "Latency",
          },
        },
        empty: {
          title: "No usage yet",
          body: "No LLM activity in the last 30 days. Activate a model to get started.",
        },
        errors: {
          network: {
            title: "Failed to load summary",
            body: "Check your connection and try again.",
          },
          forbidden: {
            title: "Access restricted",
            body: "You do not have administrator permissions to view this page.",
          },
        },
        actions: {
          retry: "Retry",
          manageModels: "Manage models",
        },
      },
      nav: {
        dashboard: "Overview",
        models: "Models",
        modelsNew: "New model",
        ragDocuments: "RAG documents",
        ragCollections: "Collections",
        mcpServers: "MCP servers",
        mcpNew: "New MCP",
        agents: "Agents",
        audit: "Audit log",
        usage: "Cost & latency",
      },
    },
    rag: {
      documents: {
        title: "People documents",
        heading: "RAG Documents",
        subtitle: "Manage documents available for semantic search",
        empty: "No documents indexed yet",
        "empty.body": "Upload a PDF or DOCX document so the assistant can answer questions about its content.",
        "empty.cta": "Upload first document",
        upload: {
          cta: "Upload document",
          uploading: "Uploading…",
          submit: "Upload",
          dedup: "Existing document reused",
          fields: {
            title: "Title",
            language: "Language",
            "language.es": "Spanish",
            "language.en": "English",
            "language.fr": "French",
            collection: "Collection",
            file: "File (PDF or DOCX)",
            "file.hint": "PDF or DOCX · max 25 MiB",
          },
        },
        table: {
          col: {
            title: "Title",
            language: "Language",
            collection: "Collection",
            status: "Status",
            actions: "Actions",
          },
        },
        status: {
          uploaded: "Uploaded",
          pending: "Pending",
          processing: "Processing",
          indexed: "Indexed",
          failed: "Failed",
        },
        action: {
          index: "Index",
          "index.inProgress": "Indexing",
        },
        nav: {
          collections: "View collections →",
        },
        error: {
          network: "Connection error. Check your network and try again.",
          permission: "You do not have permission to manage documents. You need the admin role.",
          validation: {
            title: "Title is required.",
            language: "Language is required.",
            collection: "Collection is required.",
            file: "Select a PDF or DOCX file.",
          },
          tooLarge: "The file exceeds the maximum size of {{maxMb}} MiB.",
          indexInProgress: "An index job is already in progress (status: {{status}}).",
        },
        aria: {
          uploading: "Uploading document…",
          indexing: "Indexing document…",
          list: "Documents list",
        },
      },
      // §D-T002-I18N: rag.collections.* added for RagCollectionsPage (P04-S02-T002)
      collections: {
        title: "RAG Collections",
        heading: "RAG Collections",
        subtitle: "Manage collections and verticals available for semantic search",
        empty: "No collections",
        "empty.body": "When collections are created from the backend, they will appear here.",
        table: {
          caption: "RAG collections table",
          col: {
            name: "Name",
            vertical: "Vertical",
            language: "Language",
            enabled: "Status",
          },
        },
        enabled: { on: "Active", off: "Inactive" },
        language: { es: "Spanish", en: "English", fr: "French", null: "—" },
        action: {
          update: "Save",
          updating: "Saving…",
          saved: "Saved",
        },
        error: {
          network: "Connection error. Check your network and try again.",
          permission: "You do not have permission to manage collections. You need the admin role.",
          validation: {
            name: "Name is invalid.",
            vertical: "Vertical is invalid.",
            language: "Language is invalid.",
            enabled: "Status is invalid.",
            body: "Change at least one field.",
          },
          notFound: "The collection no longer exists. Refresh the list.",
          rateLimited: "Too many requests. Please try again later.",
          internal: "Server error. Please try again later.",
        },
        nav: { documents: "← View documents" },
        aria: {
          list: "Collections list",
          updating: "Updating collection…",
          enabled_toggle: "Enable or disable collection {{name}}",
        },
      },
    },
    // §D-T003-I18N: mcp.servers.* extended for McpServersPage (P04-S02-T003)
    mcp: {
      servers: {
        title: "MCP Servers",
        subtitle: "Manage your organisation's MCP server integrations",
        empty: "No servers connected",
        columns: {
          name: "Name",
          status: "Status",
          transport: "Transport",
          lastSync: "Last sync",
          toolCount: "Tools",
          risk: "Risk",
          actions: "Actions",
        },
        status: {
          draft: "Draft",
          active: "Active",
          error: "Error",
          unknown: "Unknown",
        },
        lastSync: {
          never: "Never",
          relative: "{{relative}} ago",
        },
        actions: {
          sync: "Sync",
          syncing: "Syncing…",
          synced: "Synced",
          connectFirst: "Connect first server",
        },
        errors: {
          sync_not_found: "Server not found",
          sync_rate_limited: "Too many sync requests, please wait",
          sync_internal: "Internal server error",
        },
        notes: {
          risk_per_tool: "Risk level is managed per tool in P04-S02-T004.",
        },
        tools: {
          none: "—",
        },
      },
    },
    errors: {
      AUTH_INVALID_CREDENTIALS: "Incorrect email or password",
      AUTH_MFA_REQUIRED: "Two-step verification is required",
      AUTH_SESSION_EXPIRED: "Your session has expired. Please sign in again",
      AUTH_FORBIDDEN: "You do not have permission to perform this action",
      CHAT_STREAM_FAILED: "Failed to receive the response. Please try again",
      RAG_DOCUMENT_INVALID: "The document is invalid or cannot be processed",
      RAG_INDEX_IN_PROGRESS: "The document is being indexed and will be available shortly",
      AI_PROVIDER_TEST_FAILED: "Connection test with the AI provider failed",
      MCP_SERVER_UNREACHABLE: "Unable to connect to the MCP server",
      MCP_TOOL_REQUIRES_APPROVAL: "This tool requires approval before it can run",
      AGENT_RUN_FAILED: "The agent could not complete the task",
      UNKNOWN: "An unexpected error occurred",
      NETWORK: "Connection error. Check your network and try again",
    },
  },
  fr: {
    common: {
      productName: "Hilo",
      actions: {
        continue: "Continuer",
        cancel: "Annuler",
        save: "Enregistrer",
        retry: "Réessayer",
        back: "Retour",
      },
      states: {
        loading: "Chargement...",
        empty: "Aucun résultat",
        success: "Opération réussie",
      },
      language: { es: "Espagnol", en: "Anglais", fr: "Français" },
    },
    auth: {
      signIn: {
        actions: {
          forgot: "Mot de passe oublié ?",
          signUp: "Créer un compte",
        },
        cta: "Accéder avec votre compte",
        email: "Email professionnel",
        emailPlaceholder: "nom@entreprise.com",
        errors: {
          accountLocked: "Compte temporairement bloqué. Veuillez réessayer plus tard.",
          emailFormat: "Entrez une adresse email valide.",
          emailRequired: "L'email est obligatoire.",
          invalidCredentials: "Email ou mot de passe incorrect.",
          network: "Pas de connexion. Vérifiez votre réseau et réessayez.",
          passwordRequired: "Le mot de passe est obligatoire.",
          rateLimited: "Trop de tentatives. Attendez {{seconds}} secondes et réessayez.",
          serverInternal: "Erreur interne du serveur. Veuillez réessayer plus tard.",
        },
        password: "Mot de passe",
        passwordPlaceholder: "••••••••",
        status: { submitting: "Connexion en cours…" },
        submit: "Se connecter",
        title: "Connexion",
        titleHint: "Espace employé",
      },
      signUp: {
        title: "Créer un compte",
        titleHint: "Espace employé",
        email: "Email professionnel",
        emailPlaceholder: "nom@entreprise.com",
        fullName: "Nom complet",
        fullNamePlaceholder: "Votre prénom et nom de famille",
        password: "Mot de passe",
        passwordPlaceholder: "••••••••",
        passwordHint: "Au moins 12 caractères avec des lettres et des chiffres",
        legalAcceptance: "J'ai lu et j'accepte les conditions générales",
        legalAcceptanceHint: "Requis pour créer votre compte",
        submit: "Créer un compte",
        cta: "Créer votre compte",
        status: { submitting: "Création en cours…" },
        actions: { signIn: "Vous avez déjà un compte ? Connectez-vous" },
        successFlash: "Compte créé. Connectez-vous pour accéder.",
        errors: {
          emailRequired: "L'email est obligatoire.",
          emailFormat: "Entrez une adresse email valide.",
          nonCorporateEmail: "Cet email n'est pas un email professionnel valide. Utilisez votre email d'entreprise.",
          fullNameRequired: "Le nom complet est obligatoire.",
          fullNameTooLong: "Le nom complet ne peut pas dépasser 200 caractères.",
          passwordRequired: "Le mot de passe est obligatoire.",
          passwordTooShort: "Le mot de passe doit comporter au moins 12 caractères.",
          passwordPolicy: "Le mot de passe doit comporter au moins 12 caractères, une lettre et un chiffre.",
          legalRequired: "Vous devez accepter les conditions générales pour continuer.",
          legalNotAccepted: "Vous devez accepter les conditions générales pour continuer.",
          emailTaken: "Impossible de créer un compte avec cet email. Si vous avez déjà un compte, essayez de vous connecter.",
          rateLimited: "Trop de tentatives. Attendez {{seconds}} secondes et réessayez.",
          network: "Pas de connexion. Vérifiez votre réseau et réessayez.",
          serverInternal: "Erreur interne du serveur. Veuillez réessayer plus tard.",
          payloadInvalid: "Données d'inscription invalides. Vérifiez les champs et réessayez.",
        },
      },
      forgot: {
        title: "Réinitialiser l'accès",
        cta: "Envoyer le lien de récupération",
      },
      twoFactor: {
        title: "Vérification en deux étapes",
        codeLabel: "Code de vérification",
      },
    },
    chat: {
      empty: {
        title: "Comment puis-je vous aider ?",
        subtitle: "Saisissez votre question pour commencer",
        promptVacation: "Combien de jours de congé me reste-t-il ?",
        promptMobility: "Politique de mobilité interne",
      },
      citation: { label: "Source" },
      composer: {
        placeholder: "Rédigez votre message...",
        send: "Envoyer",
        errors: {
          tooLong: "Le message ne peut pas dépasser {{max}} caractères.",
        },
      },
    },
    account: {
      title: "Mon compte",
      language: "Langue",
      languageHint: "La langue sélectionnée s'applique à toute l'interface",
      logout: "Se déconnecter",
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      models: {
        title: "Modèles LiteLLM",
        table: {
          caption: "Liste des modèles AI",
          headers: {
            model: "Modèle",
            type: "Type",
            provider: "Fournisseur",
            status: "Statut",
            default: "Par défaut",
            cost: "Coût",
            latency: "Latence",
          },
        },
        status: {
          active: "Actif",
          modelDisabled: "Modèle désactivé",
          providerInactive: "Fournisseur inactif",
          bothInactive: "Les deux inactifs",
          unknown: "Inconnu",
        },
        default: {
          yes: "Oui",
          no: "—",
        },
        cost: {
          unknown: "—",
        },
        latency: {
          unknown: "—",
          value: "{{ms}} ms",
        },
        empty: {
          body: "Aucun modèle configuré. Créez un modèle pour commencer.",
          cta: "Nouveau modèle",
        },
        errors: {
          network: {
            title: "Impossible de charger les modèles",
            body: "Vérifiez votre connexion et réessayez.",
          },
          forbidden: {
            title: "Accès restreint",
            body: "Vous n'avez pas les permissions d'administrateur pour afficher cette page.",
          },
        },
        actions: {
          retry: "Réessayer",
          newModel: "Nouveau modèle",
        },
      },
      mcp: { title: "Intégrations MCP", empty: "Aucune intégration active" },
      dashboard: {
        title: "Synthèse Admin AI",
        window: {
          range: "30 derniers jours — {{from}} → {{to}}",
        },
        kpi: {
          invocations: "Invocations",
          tokens: "Tokens (in + out)",
          cost: "Coût estimé",
          latency: "Latence moy. (ms)",
        },
        table: {
          caption: "Utilisation par modèle",
          headers: {
            model: "Modèle",
            invocations: "Invocations",
            tokensIn: "Tokens in",
            tokensOut: "Tokens out",
            cost: "Coût",
            latency: "Latence",
          },
        },
        empty: {
          title: "Aucune utilisation",
          body: "Aucune activité LLM ces 30 derniers jours. Activez un modèle pour commencer.",
        },
        errors: {
          network: {
            title: "Impossible de charger le résumé",
            body: "Vérifiez votre connexion et réessayez.",
          },
          forbidden: {
            title: "Accès restreint",
            body: "Vous n'avez pas les permissions d'administrateur pour afficher cette page.",
          },
        },
        actions: {
          retry: "Réessayer",
          manageModels: "Gérer les modèles",
        },
      },
      nav: {
        dashboard: "Vue d'ensemble",
        models: "Modèles",
        modelsNew: "Nouveau modèle",
        ragDocuments: "Documents RAG",
        ragCollections: "Collections",
        mcpServers: "Serveurs MCP",
        mcpNew: "Nouveau MCP",
        agents: "Agents",
        audit: "Journal d'audit",
        usage: "Coût & latence",
      },
    },
    rag: {
      documents: {
        title: "Documents People",
        heading: "Documents RAG",
        subtitle: "Gérez les documents disponibles pour la recherche sémantique",
        empty: "Aucun document indexé",
        "empty.body": "Téléversez un document PDF ou DOCX pour que l'assistant puisse répondre aux questions sur son contenu.",
        "empty.cta": "Téléverser le premier document",
        upload: {
          cta: "Téléverser un document",
          uploading: "Téléversement en cours…",
          submit: "Téléverser",
          dedup: "Document existant réutilisé",
          fields: {
            title: "Titre",
            language: "Langue",
            "language.es": "Espagnol",
            "language.en": "Anglais",
            "language.fr": "Français",
            collection: "Collection",
            file: "Fichier (PDF ou DOCX)",
            "file.hint": "PDF ou DOCX · max 25 Mio",
          },
        },
        table: {
          col: {
            title: "Titre",
            language: "Langue",
            collection: "Collection",
            status: "Statut",
            actions: "Actions",
          },
        },
        status: {
          uploaded: "Téléversé",
          pending: "En attente",
          processing: "En cours",
          indexed: "Indexé",
          failed: "Échoué",
        },
        action: {
          index: "Indexer",
          "index.inProgress": "Indexation",
        },
        nav: {
          collections: "Voir les collections →",
        },
        error: {
          network: "Erreur de connexion. Vérifiez votre réseau et réessayez.",
          permission: "Vous n'avez pas la permission de gérer les documents. Vous devez avoir le rôle administrateur.",
          validation: {
            title: "Le titre est obligatoire.",
            language: "La langue est obligatoire.",
            collection: "La collection est obligatoire.",
            file: "Sélectionnez un fichier PDF ou DOCX.",
          },
          tooLarge: "Le fichier dépasse la taille maximale de {{maxMb}} Mio.",
          indexInProgress: "Un travail d'indexation est déjà en cours (statut : {{status}}).",
        },
        aria: {
          uploading: "Téléversement du document…",
          indexing: "Indexation du document…",
          list: "Liste des documents",
        },
      },
      // §D-T002-I18N: rag.collections.* added for RagCollectionsPage (P04-S02-T002)
      collections: {
        title: "Collections RAG",
        heading: "Collections RAG",
        subtitle: "Gérez les collections et verticaux disponibles pour la recherche sémantique",
        empty: "Aucune collection",
        "empty.body": "Lorsque des collections seront créées depuis le backend, elles apparaîtront ici.",
        table: {
          caption: "Tableau des collections RAG",
          col: {
            name: "Nom",
            vertical: "Vertical",
            language: "Langue",
            enabled: "Statut",
          },
        },
        enabled: { on: "Active", off: "Inactive" },
        language: { es: "Espagnol", en: "Anglais", fr: "Français", null: "—" },
        action: {
          update: "Enregistrer",
          updating: "Enregistrement…",
          saved: "Enregistré",
        },
        error: {
          network: "Erreur de connexion. Vérifiez votre réseau et réessayez.",
          permission: "Vous n'avez pas la permission de gérer les collections. Vous devez avoir le rôle administrateur.",
          validation: {
            name: "Le nom est invalide.",
            vertical: "Le vertical est invalide.",
            language: "La langue est invalide.",
            enabled: "Le statut est invalide.",
            body: "Modifiez au moins un champ.",
          },
          notFound: "La collection n'existe plus. Actualisez la liste.",
          rateLimited: "Trop de requêtes. Veuillez réessayer plus tard.",
          internal: "Erreur serveur. Veuillez réessayer plus tard.",
        },
        nav: { documents: "← Voir les documents" },
        aria: {
          list: "Liste des collections",
          updating: "Mise à jour de la collection…",
          enabled_toggle: "Activer ou désactiver la collection {{name}}",
        },
      },
    },
    // §D-T003-I18N: mcp.servers.* extended for McpServersPage (P04-S02-T003)
    mcp: {
      servers: {
        title: "Serveurs MCP",
        subtitle: "Gérez les intégrations de serveurs MCP de votre organisation",
        empty: "Aucun serveur connecté",
        columns: {
          name: "Nom",
          status: "Statut",
          transport: "Transport",
          lastSync: "Dernière sync.",
          toolCount: "Outils",
          risk: "Risque",
          actions: "Actions",
        },
        status: {
          draft: "Brouillon",
          active: "Actif",
          error: "Erreur",
          unknown: "Inconnu",
        },
        lastSync: {
          never: "Jamais",
          relative: "Il y a {{relative}}",
        },
        actions: {
          sync: "Synchroniser",
          syncing: "Synchronisation…",
          synced: "Synchronisé",
          connectFirst: "Connecter le premier serveur",
        },
        errors: {
          sync_not_found: "Serveur introuvable",
          sync_rate_limited: "Trop de synchronisations, veuillez patienter",
          sync_internal: "Erreur interne du serveur",
        },
        notes: {
          risk_per_tool: "Le niveau de risque est géré par outil dans P04-S02-T004.",
        },
        tools: {
          none: "—",
        },
      },
    },
    errors: {
      AUTH_INVALID_CREDENTIALS: "Email ou mot de passe incorrect",
      AUTH_MFA_REQUIRED: "La vérification en deux étapes est requise",
      AUTH_SESSION_EXPIRED: "Votre session a expiré. Veuillez vous reconnecter",
      AUTH_FORBIDDEN: "Vous n'avez pas la permission d'effectuer cette action",
      CHAT_STREAM_FAILED: "Impossible de recevoir la réponse. Veuillez réessayer",
      RAG_DOCUMENT_INVALID: "Le document est invalide ou ne peut pas être traité",
      RAG_INDEX_IN_PROGRESS:
        "Le document est en cours d'indexation et sera disponible prochainement",
      AI_PROVIDER_TEST_FAILED: "Le test de connexion avec le fournisseur IA a échoué",
      MCP_SERVER_UNREACHABLE: "Impossible de se connecter au serveur MCP",
      MCP_TOOL_REQUIRES_APPROVAL: "Cet outil nécessite une approbation avant de s'exécuter",
      AGENT_RUN_FAILED: "L'agent n'a pas pu accomplir la tâche",
      UNKNOWN: "Une erreur inattendue s'est produite",
      NETWORK: "Erreur de connexion. Vérifiez votre réseau et réessayez",
    },
  },
} as const;

// ---------------------------------------------------------------------------
// i18next bootstrap
// ---------------------------------------------------------------------------

// BEFORE init log
verboseLog("i18n.init.start", {
  phase: "P00",
  slice: "P00-S01-T005",
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  ns: I18N_NAMESPACES,
  defaultNS: DEFAULT_NAMESPACE,
});

/**
 * Configure and initialise the i18next singleton.
 *
 * Important invariants (see task pack §6.2 for provider contract):
 *   - Default export is the singleton (same as T002 stub). providers.tsx relies on this.
 *   - initReactI18next bridges the React rendering cycle; it must be chained BEFORE init().
 *   - No languageDetector: kept disabled (T002 R1 — crashes jsdom).
 *   - init() with resources object is synchronous when no plugins fetch async data.
 */
i18n.use(initReactI18next).init({
  // No languageDetector: browser-only plugin crashes in jsdom.
  // Activation deferred to AccountPage (P03-S02-T004).
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  ns: [...I18N_NAMESPACES],
  defaultNS: DEFAULT_NAMESPACE,
  resources,
  interpolation: {
    escapeValue: false, // React already escapes values.
  },
  saveMissing: false,
  missingKeyHandler: false,
});

// AFTER init log
verboseLog("i18n.init.ok", {
  phase: "P00",
  slice: "P00-S01-T005",
  isInitialized: i18n.isInitialized,
  language: i18n.language,
  namespaceCount: I18N_NAMESPACES.length,
  localeCount: Object.keys(resources).length,
});

export default i18n;
