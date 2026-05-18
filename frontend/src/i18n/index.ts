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
      // §D-T003-I18N (ForgotPasswordPage namespace — extended in P03-S01-T005 to fix T003 gap)
      forgot: {
        title: "Recuperar acceso",
        titleHint: "Área de empleados",
        email: "Email corporativo",
        emailPlaceholder: "nombre@empresa.com",
        submit: "Enviar enlace de recuperación",
        cta: "Enviar enlace de recuperación",
        status: { submitting: "Enviando…" },
        successFlash: "Si el email está registrado, recibirás las instrucciones en breve.",
        actions: { signIn: "Volver a iniciar sesión" },
        errors: {
          emailRequired: "El email es obligatorio.",
          emailFormat: "Introduce un email válido.",
          rateLimited: "Demasiados intentos. Espera {{seconds}} segundos e inténtalo de nuevo.",
          network: "Sin conexión. Comprueba tu red e inténtalo de nuevo.",
          serverInternal: "Error interno del servidor. Inténtalo de nuevo más tarde.",
        },
      },
      // §D-T004-I18N: reset_sent keys (ES) — anti-enumeration tone, {{maskedEmail}} only in body.with_email
      // §D-T004-I18N-BUNDLE: resource bundle insertion ES
      reset_sent: {
        title: "Revisa tu correo",
        body: {
          with_email: "Si {{maskedEmail}} está registrado en Hilo, recibirás un correo con instrucciones en breve.",
          fallback: "Si la dirección está registrada en Hilo, recibirás un correo con instrucciones en breve.",
        },
        actions: {
          back_to_sign_in: "Volver al inicio de sesión",
        },
      },
      // §D-T005-I18N: twoFactor namespace extended (P03-S01-T005)
      // §D-T005-I18N-LOCKSTEP: all keys present in ES/EN/FR (parallel update)
      twoFactor: {
        title: "Verificación en dos pasos",
        titleHint: "Área de empleados",
        intro: "Introduce el código de 6 dígitos de tu app de autenticación.",
        codeLabel: "Código de verificación",
        codePlaceholder: "123456",
        submit: "Verificar",
        cta: "Verificar y entrar",
        status: { submitting: "Verificando…" },
        errors: {
          codeRequired: "El código es obligatorio.",
          codeFormat: "Introduce un código de 6 dígitos numéricos.",
          invalidCode: "Código incorrecto. Vuelve a intentarlo.",
          challengeExpired: "Tu desafío ha expirado. Inicia sesión de nuevo.",
          rateLimited: "Demasiados intentos. Espera {{seconds}} segundos e inténtalo de nuevo.",
          network: "Sin conexión. Comprueba tu red e inténtalo de nuevo.",
          serverInternal: "Error interno del servidor. Inténtalo de nuevo más tarde.",
          missingChallenge: "No hay desafío activo. Inicia sesión de nuevo.",
        },
        actions: { backToSignIn: "Volver a iniciar sesión" },
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
      // §D-T008-I18N: conversation namespace added (P03-S02-T008 — ConversationPage)
      // §D-T008-I18N-LOCKSTEP: all keys present in ES/EN/FR (parallel update)
      conversation: {
        title: "Conversación",
        you: "Tú",
        assistant: "Asistente",
        empty: {
          title: "Aún no hay mensajes. Escribe tu primera pregunta.",
          cta: "Nueva conversación",
        },
        loading: { label: "Cargando..." },
        streaming: { label: "Asistente" },
        citations: { label: "Fuentes" },
        errors: {
          notFound: {
            title: "Conversación no encontrada.",
            cta: "Nuevo chat",
          },
          network: {
            title: "Error de conexión. Por favor, inténtalo de nuevo.",
            retry: "Reintentar",
          },
          permission: {
            title: "No tienes acceso a esta conversación.",
            cta: "Volver al chat",
          },
        },
      },
    },
    // §D-T007-WRITE-SET-DRIFT-I18N (P03-S02-T007): account namespace extended with profile,
    // languagePicker, states and logoutAction keys. Same drift pattern as §D-T003-I18N,
    // §D-T004-I18N-EXTEND. Validator accepts when documented.
    // §D-T009-I18N-KEYS (P03-S02-T009): account.nav.openAccount added (chat-shell navbar).
    account: {
      title: "Mi cuenta",
      language: "Idioma",
      languageHint: "El idioma seleccionado se aplica a toda la interfaz",
      logout: "Cerrar sesión",
      nav: {
        openAccount: "Abrir cuenta",
      },
      profile: {
        email: "Email",
        fullName: "Nombre completo",
        brand: "Marca",
        department: "Departamento",
        country: "País",
        center: "Centro",
      },
      languagePicker: {
        aria: "Selecciona idioma",
        options: {
          es: "Español",
          en: "Inglés",
          fr: "Francés",
        },
      },
      states: {
        loading: "Cargando tu cuenta...",
        errorNetwork: {
          title: "Error de conexión",
          body: "No pudimos cargar tus datos. Comprueba tu red.",
          retry: "Reintentar",
        },
        errorValidation: {
          title: "No pudimos cambiar el idioma",
          body: "El idioma seleccionado no es válido.",
        },
        permissionDenied: {
          title: "Sesión caducada",
          body: "Vuelve a iniciar sesión para continuar.",
          cta: "Iniciar sesión",
        },
      },
      logoutAction: {
        inProgress: "Cerrando sesión...",
        error: "No pudimos cerrar sesión. Inténtalo de nuevo.",
      },
    },
    // §D-T003-I18N: history namespace added (P03-S02-T003 — HistoryPage)
    history: {
      pageTitle: "CONVERSACIONES",
      groups: {
        today: "HOY",
        yesterday: "AYER",
        thisWeek: "ESTA SEMANA",
        thisMonth: "ESTE MES",
        earlier: "ANTERIORES",
      },
      empty: {
        title: "SIN CONVERSACIONES",
        body: "Empieza una nueva conversación para ver el historial aquí.",
        cta: "Nueva conversación",
      },
      errorNetwork: {
        title: "Error de conexión. Comprueba tu red.",
        retry: "Reintentar",
      },
      permissionDenied: "No tienes permiso para ver el historial.",
      loading: "Cargando historial...",
      untitledConversation: "Conversación sin título",
      list: { aria: "Historial de conversaciones" },
      row: { openLabel: "Abrir conversación, {{title}}" },
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      // §D-T004-I18N: models.table.headers.actions + models.actions.testModel added (P04-S01-T004)
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
            actions: "Acciones",
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
          testModel: "Probar",
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
      // §D-T003-I18N: modelsNew.* added for ModelWizardPage (P04-S01-T003)
      modelsNew: {
        title: "Nuevo proveedor de IA",
        subtitle: "Configura un nuevo proveedor con credenciales de acceso",
        steps: {
          aria: "Paso del asistente",
          modelsLabel: "Modelos",
          provider: { title: "Selecciona el proveedor" },
          credentials: { title: "Credenciales de acceso" },
        },
        fields: {
          providerType: "Tipo de proveedor",
          providerTypePlaceholder: "Selecciona un proveedor",
          name: "Nombre del proveedor",
          namePlaceholder: "ej. litellm_produccion",
          baseUrl: "URL base (opcional)",
          baseUrlPlaceholder: "ej. http://localhost:4000",
          authType: "Tipo de autenticación",
          secretPlain: "Clave de API o token",
          secretPlainPlaceholder: "sk-••••••••••••••••",
          secretPlainHint: "La clave se cifra en el servidor y nunca se muestra de nuevo.",
          secretShow: "Mostrar",
          secretHide: "Ocultar",
        },
        providerOptions: {
          openai: "OpenAI",
          anthropic: "Anthropic",
          azure: "Azure OpenAI",
          litellm: "LiteLLM",
          ollama: "Ollama",
          google: "Google AI",
          custom: "Personalizado",
        },
        authTypeOptions: {
          api_key: "Clave de API",
          oauth2: "OAuth 2.0",
          bearer: "Bearer token",
        },
        actions: {
          next: "Siguiente",
          back: "Atrás",
          submit: "Crear y continuar",
          submitting: "Creando…",
          backToModels: "Ver modelos",
          testModel: "Probar modelo",
        },
        success: {
          title: "Proveedor creado",
          body: "El proveedor se ha registrado correctamente. Los modelos disponibles aparecen a continuación.",
          loadingModels: "Cargando modelos…",
          noModels: "Aún no hay modelos disponibles para este proveedor. Los modelos se descubren automáticamente.",
          modelCount: "{{count}} modelo(s) disponible(s)",
          modelsListLabel: "Modelos del proveedor",
          defaultBadge: "Por defecto",
        },
        errors: {
          network: {
            title: "Error de conexión",
            body: "No se pudo crear el proveedor. Comprueba tu conexión e inténtalo de nuevo.",
          },
          validation: {
            generic: "Los datos no son válidos. Revisa los campos e inténtalo de nuevo.",
            providerTypeRequired: "Selecciona un tipo de proveedor.",
            nameRequired: "El nombre del proveedor es obligatorio.",
            nameTooLong: "El nombre no puede superar los 200 caracteres.",
            secretRequired: "La clave de API o token es obligatoria.",
            authTypeRequired: "Selecciona un tipo de autenticación.",
          },
          permissionDenied: {
            title: "Acceso restringido",
            body: "No tienes permisos para crear proveedores de IA. Necesitas el rol de administrador.",
          },
        },
      },
      // §D-T004-I18N: modelTest.* added for ModelTestDrawer (P04-S01-T004)
      modelTest: {
        title: "Probar modelo",
        subtitle: "Envía un prompt real y comprueba la respuesta, latencia y coste del modelo.",
        promptLabel: "Prompt",
        promptPlaceholder: "Escribe tu pregunta o prompt aquí…",
        actions: {
          submit: "Probar",
          submitting: "Probando…",
          activate: "Activar como modelo por defecto",
          activating: "Activando…",
          retry: "Reintentar",
          back: "Volver a modelos",
        },
        success: {
          title: "Respuesta del modelo",
          latency: "Latencia",
          cost: "Coste",
          activated: "Modelo activado como predeterminado.",
        },
        errors: {
          network: "No se pudo conectar. Comprueba tu red e inténtalo de nuevo.",
          upstream: "El proveedor LLM no respondió. Inténtalo de nuevo en unos segundos.",
          validation: "El prompt no es válido. Revisa el campo e inténtalo de nuevo.",
          permissionDenied: "No tienes permiso para probar modelos. Necesitas el rol de administrador.",
          activateFailed: "No se pudo activar el modelo. Inténtalo de nuevo.",
          notFound: "El modelo no existe o ha sido eliminado.",
        },
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
    // §D-T004-I18N: mcp.wizard.* added for McpWizardPage (P04-S02-T004)
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
          risk_per_tool: "El nivel de riesgo se gestiona por herramienta.",
        },
        tools: {
          none: "—",
        },
      },
      wizard: {
        title: "Conectar servidor MCP",
        subtitle: "Registra un servidor MCP externo. Las tools quedarán desactivadas hasta que las apruebes.",
        fields: {
          name: "Nombre",
          transport: "Transporte",
          "transport.http": "HTTP",
          "transport.sse": "SSE",
          endpoint: "Endpoint",
          authType: "Tipo de autenticación",
          "authType.none": "Ninguna",
          "authType.api_key": "API key",
          "authType.bearer": "Bearer",
          "authType.oauth2": "OAuth2",
          secret: "Secreto",
          refreshToken: "Refresh token",
        },
        actions: {
          submit: "Conectar",
          submitting: "Conectando…",
          cancel: "Cancelar",
        },
        errors: {
          nameRequired: "Nombre obligatorio",
          nameMax: "Máximo 200 caracteres",
          endpointRequired: "Endpoint obligatorio",
          endpointInvalid: "Debe empezar por http:// o https:// o sse://",
          endpointNotAllowed: "Este endpoint no está en la allowlist autorizada",
          secretRequired: "Se requiere un secreto para este tipo de autenticación",
          forbidden: "No tienes permiso para registrar servidores MCP",
          network: "Error de red. Vuelve a intentarlo.",
          rateLimited: "Demasiados intentos. Espera unos segundos.",
          serverError: "Error del servidor. Vuelve a intentarlo.",
        },
        success: {
          title: "Servidor conectado",
          body: "Las tools se descubrirán en la próxima sincronización.",
        },
        permissionDenied: {
          title: "Acceso denegado",
          body: "No tienes permiso para registrar servidores MCP.",
          back: "Volver a servidores MCP",
        },
      },
    },
    // §D-T005-I18N: agents.* namespace for AgentsPage (P04-S02-T005)
    agents: {
      title: "Agentes IA",
      subtitle: "Gestiona los agentes de IA y sus herramientas aprobadas",
      empty: "No hay agentes configurados",
      "empty.body": "Los agentes se configuran mediante migraciones y datos de verificación.",
      columns: {
        name: "Nombre",
        description: "Descripción",
        enabled: "Habilitado",
        toolCount: "Herramientas",
        actions: "Herramientas asignadas",
      },
      tools: {
        none: "—",
        add: "Asignar herramienta",
        remove: "Quitar herramienta",
        save: "Guardar selección",
      },
      actions: {
        run: "Ejecutar",
        running: "Ejecutando…",
      },
      run: {
        title: "Lanzar agente",
        inputPlaceholder: "Escribe un mensaje para el agente…",
        submit: "Ejecutar",
        success: "Ejecución iniciada · estado: {{status}}",
        errors: {
          disabled: "Este agente está deshabilitado.",
          empty: "El mensaje no puede estar vacío.",
          tooLong: "El mensaje no puede superar {{max}} caracteres.",
        },
      },
      errors: {
        patch_tool_not_found: "Una o más herramientas no existen.",
        patch_tool_not_approved: "Una o más herramientas no están aprobadas.",
        patch_not_found: "Agente no encontrado.",
        run_rate_limited: "Demasiadas ejecuciones. Inténtalo en un momento.",
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
      AGENT_NOT_FOUND: "Agente no encontrado",
      AGENT_TOOL_NOT_FOUND: "Una o más herramientas no existen",
      AGENT_TOOL_NOT_APPROVED: "Una o más herramientas no están aprobadas",
      AGENT_DISABLED: "Este agente está deshabilitado",
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
      // §D-T003-I18N EN (ForgotPasswordPage namespace — extended in P03-S01-T005 to fix T003 gap)
      forgot: {
        title: "Reset access",
        titleHint: "Employee area",
        email: "Corporate email",
        emailPlaceholder: "name@company.com",
        submit: "Send recovery link",
        cta: "Send recovery link",
        status: { submitting: "Sending…" },
        successFlash: "If the email is registered, you will receive the instructions shortly.",
        actions: { signIn: "Back to sign in" },
        errors: {
          emailRequired: "Email is required.",
          emailFormat: "Enter a valid email address.",
          rateLimited: "Too many attempts. Wait {{seconds}} seconds and try again.",
          network: "No connection. Check your network and try again.",
          serverInternal: "Internal server error. Please try again later.",
        },
      },
      // §D-T004-I18N-BUNDLE: resource bundle insertion EN
      reset_sent: {
        title: "Check your email",
        body: {
          with_email: "If {{maskedEmail}} is registered in Hilo, you will receive an email with instructions shortly.",
          fallback: "If the address is registered in Hilo, you will receive an email with instructions shortly.",
        },
        actions: {
          back_to_sign_in: "Back to sign in",
        },
      },
      // §D-T005-I18N-BUNDLE: twoFactor namespace extended EN (P03-S01-T005)
      twoFactor: {
        title: "Two-step verification",
        titleHint: "Employee area",
        intro: "Enter the 6-digit code from your authenticator app.",
        codeLabel: "Verification code",
        codePlaceholder: "123456",
        submit: "Verify",
        cta: "Verify and continue",
        status: { submitting: "Verifying…" },
        errors: {
          codeRequired: "The code is required.",
          codeFormat: "Enter a 6-digit numeric code.",
          invalidCode: "Incorrect code. Please try again.",
          challengeExpired: "Your challenge has expired. Please sign in again.",
          rateLimited: "Too many attempts. Try again in {{seconds}} seconds.",
          network: "No connection. Check your network and try again.",
          serverInternal: "Internal server error. Please try again later.",
          missingChallenge: "No active challenge. Please sign in again.",
        },
        actions: { backToSignIn: "Back to sign in" },
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
      // §D-T008-I18N: conversation namespace added (P03-S02-T008 — ConversationPage)
      // §D-T008-I18N-LOCKSTEP: all keys present in ES/EN/FR (parallel update)
      conversation: {
        title: "Conversation",
        you: "You",
        assistant: "Assistant",
        empty: {
          title: "No messages yet. Type your first question.",
          cta: "New conversation",
        },
        loading: { label: "Loading..." },
        streaming: { label: "Assistant" },
        citations: { label: "Sources" },
        errors: {
          notFound: {
            title: "Conversation not found.",
            cta: "New chat",
          },
          network: {
            title: "Connection error. Please try again.",
            retry: "Try again",
          },
          permission: {
            title: "You do not have access to this conversation.",
            cta: "Back to chat",
          },
        },
      },
    },
    // §D-T007-WRITE-SET-DRIFT-I18N (P03-S02-T007): account namespace extended (EN).
    // §D-T009-I18N-KEYS (P03-S02-T009): account.nav.openAccount added (chat-shell navbar).
    account: {
      title: "My account",
      language: "Language",
      languageHint: "The selected language applies to the entire interface",
      logout: "Sign out",
      nav: {
        openAccount: "Open account",
      },
      profile: {
        email: "Email",
        fullName: "Full name",
        brand: "Brand",
        department: "Department",
        country: "Country",
        center: "Center",
      },
      languagePicker: {
        aria: "Select language",
        options: {
          es: "Spanish",
          en: "English",
          fr: "French",
        },
      },
      states: {
        loading: "Loading your account...",
        errorNetwork: {
          title: "Connection error",
          body: "We couldn't load your data. Check your network.",
          retry: "Retry",
        },
        errorValidation: {
          title: "We couldn't change the language",
          body: "The selected language is not valid.",
        },
        permissionDenied: {
          title: "Session expired",
          body: "Sign in again to continue.",
          cta: "Sign in",
        },
      },
      logoutAction: {
        inProgress: "Signing out...",
        error: "We couldn't sign you out. Please try again.",
      },
    },
    // §D-T003-I18N: history namespace added (P03-S02-T003 — HistoryPage)
    history: {
      pageTitle: "CONVERSATIONS",
      groups: {
        today: "TODAY",
        yesterday: "YESTERDAY",
        thisWeek: "THIS WEEK",
        thisMonth: "THIS MONTH",
        earlier: "EARLIER",
      },
      empty: {
        title: "NO CONVERSATIONS",
        body: "Start a new conversation to see history here.",
        cta: "New conversation",
      },
      errorNetwork: {
        title: "Connection error. Check your network.",
        retry: "Try again",
      },
      permissionDenied: "You do not have permission to view the history.",
      loading: "Loading history...",
      untitledConversation: "Untitled conversation",
      list: { aria: "Conversation history" },
      row: { openLabel: "Open conversation, {{title}}" },
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      // §D-T004-I18N: models.table.headers.actions + models.actions.testModel added (P04-S01-T004)
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
            actions: "Actions",
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
          testModel: "Test",
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
      // §D-T003-I18N: modelsNew.* added for ModelWizardPage (P04-S01-T003)
      modelsNew: {
        title: "New AI provider",
        subtitle: "Configure a new provider with access credentials",
        steps: {
          aria: "Wizard step",
          modelsLabel: "Models",
          provider: { title: "Select provider" },
          credentials: { title: "Access credentials" },
        },
        fields: {
          providerType: "Provider type",
          providerTypePlaceholder: "Select a provider",
          name: "Provider name",
          namePlaceholder: "e.g. litellm_production",
          baseUrl: "Base URL (optional)",
          baseUrlPlaceholder: "e.g. http://localhost:4000",
          authType: "Authentication type",
          secretPlain: "API key or token",
          secretPlainPlaceholder: "sk-••••••••••••••••",
          secretPlainHint: "The key is encrypted on the server and never shown again.",
          secretShow: "Show",
          secretHide: "Hide",
        },
        providerOptions: {
          openai: "OpenAI",
          anthropic: "Anthropic",
          azure: "Azure OpenAI",
          litellm: "LiteLLM",
          ollama: "Ollama",
          google: "Google AI",
          custom: "Custom",
        },
        authTypeOptions: {
          api_key: "API key",
          oauth2: "OAuth 2.0",
          bearer: "Bearer token",
        },
        actions: {
          next: "Next",
          back: "Back",
          submit: "Create and continue",
          submitting: "Creating…",
          backToModels: "View models",
          testModel: "Test model",
        },
        success: {
          title: "Provider created",
          body: "The provider was registered successfully. Available models are listed below.",
          loadingModels: "Loading models…",
          noModels: "No models available yet for this provider. Models are discovered automatically.",
          modelCount: "{{count}} model(s) available",
          modelsListLabel: "Provider models",
          defaultBadge: "Default",
        },
        errors: {
          network: {
            title: "Connection error",
            body: "Could not create the provider. Check your connection and try again.",
          },
          validation: {
            generic: "The data is not valid. Review the fields and try again.",
            providerTypeRequired: "Select a provider type.",
            nameRequired: "Provider name is required.",
            nameTooLong: "Name cannot exceed 200 characters.",
            secretRequired: "API key or token is required.",
            authTypeRequired: "Select an authentication type.",
          },
          permissionDenied: {
            title: "Access restricted",
            body: "You do not have permission to create AI providers. You need the admin role.",
          },
        },
      },
      // §D-T004-I18N: modelTest.* added for ModelTestDrawer (P04-S01-T004)
      modelTest: {
        title: "Test model",
        subtitle: "Send a real prompt and check the model's response, latency and cost.",
        promptLabel: "Prompt",
        promptPlaceholder: "Type your question or prompt here…",
        actions: {
          submit: "Test",
          submitting: "Testing…",
          activate: "Set as default model",
          activating: "Activating…",
          retry: "Try again",
          back: "Back to models",
        },
        success: {
          title: "Model response",
          latency: "Latency",
          cost: "Cost",
          activated: "Model set as default.",
        },
        errors: {
          network: "Could not connect. Check your network and try again.",
          upstream: "The LLM provider did not respond. Please try again in a few seconds.",
          validation: "The prompt is not valid. Review the field and try again.",
          permissionDenied: "You do not have permission to test models. You need the admin role.",
          activateFailed: "Could not activate the model. Please try again.",
          notFound: "The model does not exist or has been removed.",
        },
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
    // §D-T004-I18N: mcp.wizard.* added for McpWizardPage (P04-S02-T004)
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
          risk_per_tool: "Risk level is managed per tool.",
        },
        tools: {
          none: "—",
        },
      },
      wizard: {
        title: "Connect MCP server",
        subtitle: "Register an external MCP server. Tools will be disabled until you approve them.",
        fields: {
          name: "Name",
          transport: "Transport",
          "transport.http": "HTTP",
          "transport.sse": "SSE",
          endpoint: "Endpoint",
          authType: "Auth type",
          "authType.none": "None",
          "authType.api_key": "API key",
          "authType.bearer": "Bearer",
          "authType.oauth2": "OAuth2",
          secret: "Secret",
          refreshToken: "Refresh token",
        },
        actions: {
          submit: "Connect",
          submitting: "Connecting…",
          cancel: "Cancel",
        },
        errors: {
          nameRequired: "Name is required",
          nameMax: "Max 200 characters",
          endpointRequired: "Endpoint is required",
          endpointInvalid: "Must start with http://, https:// or sse://",
          endpointNotAllowed: "This endpoint is not in the authorised allowlist",
          secretRequired: "A secret is required for this authentication type",
          forbidden: "You do not have permission to register MCP servers",
          network: "Network error. Please try again.",
          rateLimited: "Too many attempts. Please wait a moment.",
          serverError: "Server error. Please try again.",
        },
        success: {
          title: "Server connected",
          body: "Tools will be discovered on the next sync.",
        },
        permissionDenied: {
          title: "Access denied",
          body: "You do not have permission to register MCP servers.",
          back: "Back to MCP servers",
        },
      },
    },
    // §D-T005-I18N: agents.* namespace for AgentsPage (P04-S02-T005)
    agents: {
      title: "AI Agents",
      subtitle: "Manage AI agents and their approved tools",
      empty: "No agents configured",
      "empty.body": "Agents are configured through migrations and verification data.",
      columns: {
        name: "Name",
        description: "Description",
        enabled: "Enabled",
        toolCount: "Tools",
        actions: "Assigned tools",
      },
      tools: {
        none: "—",
        add: "Assign tool",
        remove: "Remove tool",
        save: "Save selection",
      },
      actions: {
        run: "Run",
        running: "Running…",
      },
      run: {
        title: "Launch agent",
        inputPlaceholder: "Type a message for the agent…",
        submit: "Run",
        success: "Run started · status: {{status}}",
        errors: {
          disabled: "This agent is disabled.",
          empty: "The message cannot be empty.",
          tooLong: "The message cannot exceed {{max}} characters.",
        },
      },
      errors: {
        patch_tool_not_found: "One or more tools do not exist.",
        patch_tool_not_approved: "One or more tools are not approved.",
        patch_not_found: "Agent not found.",
        run_rate_limited: "Too many runs. Please try again in a moment.",
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
      AGENT_NOT_FOUND: "Agent not found",
      AGENT_TOOL_NOT_FOUND: "One or more tools do not exist",
      AGENT_TOOL_NOT_APPROVED: "One or more tools are not approved",
      AGENT_DISABLED: "This agent is disabled",
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
      // §D-T003-I18N FR (ForgotPasswordPage namespace — extended in P03-S01-T005 to fix T003 gap)
      forgot: {
        title: "Réinitialiser l'accès",
        titleHint: "Espace employé",
        email: "Email professionnel",
        emailPlaceholder: "nom@entreprise.com",
        submit: "Envoyer le lien de récupération",
        cta: "Envoyer le lien de récupération",
        status: { submitting: "Envoi en cours…" },
        successFlash: "Si l'email est enregistré, vous recevrez les instructions sous peu.",
        actions: { signIn: "Retour à la connexion" },
        errors: {
          emailRequired: "L'email est obligatoire.",
          emailFormat: "Entrez une adresse email valide.",
          rateLimited: "Trop de tentatives. Attendez {{seconds}} secondes et réessayez.",
          network: "Pas de connexion. Vérifiez votre réseau et réessayez.",
          serverInternal: "Erreur interne du serveur. Veuillez réessayer plus tard.",
        },
      },
      // §D-T004-I18N-BUNDLE: resource bundle insertion FR
      reset_sent: {
        title: "Vérifiez votre email",
        body: {
          with_email: "Si {{maskedEmail}} est enregistré dans Hilo, vous recevrez un email contenant les instructions sous peu.",
          fallback: "Si l'adresse est enregistrée dans Hilo, vous recevrez un email contenant les instructions sous peu.",
        },
        actions: {
          back_to_sign_in: "Retour à la connexion",
        },
      },
      // §D-T005-I18N-BUNDLE: twoFactor namespace extended FR (P03-S01-T005)
      twoFactor: {
        title: "Vérification en deux étapes",
        titleHint: "Espace employé",
        intro: "Saisis le code à 6 chiffres de ton application d'authentification.",
        codeLabel: "Code de vérification",
        codePlaceholder: "123456",
        submit: "Vérifier",
        cta: "Vérifier et continuer",
        status: { submitting: "Vérification…" },
        errors: {
          codeRequired: "Le code est obligatoire.",
          codeFormat: "Saisis un code de 6 chiffres numériques.",
          invalidCode: "Code incorrect. Réessaie.",
          challengeExpired: "Ton défi a expiré. Reconnecte-toi.",
          rateLimited: "Trop de tentatives. Réessaie dans {{seconds}} secondes.",
          network: "Pas de connexion. Vérifie ton réseau et réessaie.",
          serverInternal: "Erreur interne du serveur. Réessaie plus tard.",
          missingChallenge: "Aucun défi actif. Reconnecte-toi.",
        },
        actions: { backToSignIn: "Retour à la connexion" },
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
      // §D-T008-I18N: conversation namespace added (P03-S02-T008 — ConversationPage)
      // §D-T008-I18N-LOCKSTEP: all keys present in ES/EN/FR (parallel update)
      conversation: {
        title: "Conversation",
        you: "Vous",
        assistant: "Assistant",
        empty: {
          title: "Aucun message pour l'instant. Rédigez votre première question.",
          cta: "Nouvelle conversation",
        },
        loading: { label: "Chargement..." },
        streaming: { label: "Assistant" },
        citations: { label: "Sources" },
        errors: {
          notFound: {
            title: "Conversation introuvable.",
            cta: "Nouveau chat",
          },
          network: {
            title: "Erreur de connexion. Veuillez réessayer.",
            retry: "Réessayer",
          },
          permission: {
            title: "Vous n'avez pas accès à cette conversation.",
            cta: "Retour au chat",
          },
        },
      },
    },
    // §D-T007-WRITE-SET-DRIFT-I18N (P03-S02-T007): account namespace extended (FR).
    // §D-T009-I18N-KEYS (P03-S02-T009): account.nav.openAccount added (chat-shell navbar).
    account: {
      title: "Mon compte",
      language: "Langue",
      languageHint: "La langue sélectionnée s'applique à toute l'interface",
      logout: "Se déconnecter",
      nav: {
        openAccount: "Ouvrir le compte",
      },
      profile: {
        email: "Email",
        fullName: "Nom complet",
        brand: "Marque",
        department: "Département",
        country: "Pays",
        center: "Centre",
      },
      languagePicker: {
        aria: "Sélectionnez la langue",
        options: {
          es: "Espagnol",
          en: "Anglais",
          fr: "Français",
        },
      },
      states: {
        loading: "Chargement de votre compte...",
        errorNetwork: {
          title: "Erreur de connexion",
          body: "Nous n'avons pas pu charger vos données. Vérifiez votre réseau.",
          retry: "Réessayer",
        },
        errorValidation: {
          title: "Nous n'avons pas pu changer la langue",
          body: "La langue sélectionnée n'est pas valide.",
        },
        permissionDenied: {
          title: "Session expirée",
          body: "Reconnectez-vous pour continuer.",
          cta: "Se connecter",
        },
      },
      logoutAction: {
        inProgress: "Déconnexion...",
        error: "Nous n'avons pas pu vous déconnecter. Veuillez réessayer.",
      },
    },
    // §D-T003-I18N: history namespace added (P03-S02-T003 — HistoryPage)
    history: {
      pageTitle: "CONVERSATIONS",
      groups: {
        today: "AUJOURD'HUI",
        yesterday: "HIER",
        thisWeek: "CETTE SEMAINE",
        thisMonth: "CE MOIS-CI",
        earlier: "PLUS ANCIENS",
      },
      empty: {
        title: "AUCUNE CONVERSATION",
        body: "Démarrez une nouvelle conversation pour voir l'historique ici.",
        cta: "Nouvelle conversation",
      },
      errorNetwork: {
        title: "Erreur de connexion. Vérifiez votre réseau.",
        retry: "Réessayer",
      },
      permissionDenied: "Vous n'avez pas la permission de voir l'historique.",
      loading: "Chargement de l'historique...",
      untitledConversation: "Conversation sans titre",
      list: { aria: "Historique des conversations" },
      row: { openLabel: "Ouvrir la conversation, {{title}}" },
    },
    "admin-ai": {
      // §D-T002-I18N: models.* extended for AdminAiModelsPage (P04-S01-T002)
      // §D-T004-I18N: models.table.headers.actions + models.actions.testModel added (P04-S01-T004)
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
            actions: "Actions",
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
          testModel: "Tester",
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
      // §D-T003-I18N: modelsNew.* added for ModelWizardPage (P04-S01-T003)
      modelsNew: {
        title: "Nouveau fournisseur IA",
        subtitle: "Configurez un nouveau fournisseur avec des identifiants d'accès",
        steps: {
          aria: "Étape de l'assistant",
          modelsLabel: "Modèles",
          provider: { title: "Sélectionner le fournisseur" },
          credentials: { title: "Identifiants d'accès" },
        },
        fields: {
          providerType: "Type de fournisseur",
          providerTypePlaceholder: "Sélectionnez un fournisseur",
          name: "Nom du fournisseur",
          namePlaceholder: "ex. litellm_production",
          baseUrl: "URL de base (facultatif)",
          baseUrlPlaceholder: "ex. http://localhost:4000",
          authType: "Type d'authentification",
          secretPlain: "Clé API ou token",
          secretPlainPlaceholder: "sk-••••••••••••••••",
          secretPlainHint: "La clé est chiffrée côté serveur et ne sera plus affichée.",
          secretShow: "Afficher",
          secretHide: "Masquer",
        },
        providerOptions: {
          openai: "OpenAI",
          anthropic: "Anthropic",
          azure: "Azure OpenAI",
          litellm: "LiteLLM",
          ollama: "Ollama",
          google: "Google AI",
          custom: "Personnalisé",
        },
        authTypeOptions: {
          api_key: "Clé API",
          oauth2: "OAuth 2.0",
          bearer: "Token Bearer",
        },
        actions: {
          next: "Suivant",
          back: "Retour",
          submit: "Créer et continuer",
          submitting: "Création…",
          backToModels: "Voir les modèles",
          testModel: "Tester le modèle",
        },
        success: {
          title: "Fournisseur créé",
          body: "Le fournisseur a été enregistré avec succès. Les modèles disponibles sont listés ci-dessous.",
          loadingModels: "Chargement des modèles…",
          noModels: "Aucun modèle disponible pour ce fournisseur. Les modèles sont découverts automatiquement.",
          modelCount: "{{count}} modèle(s) disponible(s)",
          modelsListLabel: "Modèles du fournisseur",
          defaultBadge: "Par défaut",
        },
        errors: {
          network: {
            title: "Erreur de connexion",
            body: "Impossible de créer le fournisseur. Vérifiez votre connexion et réessayez.",
          },
          validation: {
            generic: "Les données ne sont pas valides. Vérifiez les champs et réessayez.",
            providerTypeRequired: "Sélectionnez un type de fournisseur.",
            nameRequired: "Le nom du fournisseur est obligatoire.",
            nameTooLong: "Le nom ne peut pas dépasser 200 caractères.",
            secretRequired: "La clé API ou le token est obligatoire.",
            authTypeRequired: "Sélectionnez un type d'authentification.",
          },
          permissionDenied: {
            title: "Accès restreint",
            body: "Vous n'avez pas la permission de créer des fournisseurs IA. Vous avez besoin du rôle administrateur.",
          },
        },
      },
      // §D-T004-I18N: modelTest.* added for ModelTestDrawer (P04-S01-T004)
      modelTest: {
        title: "Tester le modèle",
        subtitle: "Envoyez un prompt réel et vérifiez la réponse, la latence et le coût du modèle.",
        promptLabel: "Prompt",
        promptPlaceholder: "Tapez votre question ou prompt ici…",
        actions: {
          submit: "Tester",
          submitting: "Test en cours…",
          activate: "Définir comme modèle par défaut",
          activating: "Activation en cours…",
          retry: "Réessayer",
          back: "Retour aux modèles",
        },
        success: {
          title: "Réponse du modèle",
          latency: "Latence",
          cost: "Coût",
          activated: "Modèle défini comme modèle par défaut.",
        },
        errors: {
          network: "Impossible de se connecter. Vérifiez votre réseau et réessayez.",
          upstream: "Le fournisseur LLM n'a pas répondu. Veuillez réessayer dans quelques secondes.",
          validation: "Le prompt n'est pas valide. Vérifiez le champ et réessayez.",
          permissionDenied: "Vous n'avez pas la permission de tester les modèles. Vous avez besoin du rôle administrateur.",
          activateFailed: "Impossible d'activer le modèle. Veuillez réessayer.",
          notFound: "Le modèle n'existe pas ou a été supprimé.",
        },
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
    // §D-T005-I18N: agents.* namespace for AgentsPage (P04-S02-T005)
    agents: {
      title: "Agents IA",
      subtitle: "Gérez les agents IA et leurs outils approuvés",
      empty: "Aucun agent configuré",
      "empty.body": "Les agents sont configurés via les migrations et les données de vérification.",
      columns: {
        name: "Nom",
        description: "Description",
        enabled: "Activé",
        toolCount: "Outils",
        actions: "Outils assignés",
      },
      tools: {
        none: "—",
        add: "Assigner un outil",
        remove: "Retirer l'outil",
        save: "Enregistrer la sélection",
      },
      actions: {
        run: "Exécuter",
        running: "Exécution…",
      },
      run: {
        title: "Lancer l'agent",
        inputPlaceholder: "Rédigez un message pour l'agent…",
        submit: "Exécuter",
        success: "Exécution démarrée · statut : {{status}}",
        errors: {
          disabled: "Cet agent est désactivé.",
          empty: "Le message ne peut pas être vide.",
          tooLong: "Le message ne peut pas dépasser {{max}} caractères.",
        },
      },
      errors: {
        patch_tool_not_found: "Un ou plusieurs outils n'existent pas.",
        patch_tool_not_approved: "Un ou plusieurs outils ne sont pas approuvés.",
        patch_not_found: "Agent introuvable.",
        run_rate_limited: "Trop d'exécutions. Veuillez réessayer dans un moment.",
      },
    },
    // §D-T003-I18N: mcp.servers.* extended for McpServersPage (P04-S02-T003)
    // §D-T004-I18N: mcp.wizard.* added for McpWizardPage (P04-S02-T004)
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
          risk_per_tool: "Le niveau de risque est géré par outil.",
        },
        tools: {
          none: "—",
        },
      },
      wizard: {
        title: "Connecter serveur MCP",
        subtitle: "Enregistrez un serveur MCP externe. Les outils resteront désactivés jusqu'à votre approbation.",
        fields: {
          name: "Nom",
          transport: "Transport",
          "transport.http": "HTTP",
          "transport.sse": "SSE",
          endpoint: "Endpoint",
          authType: "Type d'authentification",
          "authType.none": "Aucune",
          "authType.api_key": "API key",
          "authType.bearer": "Bearer",
          "authType.oauth2": "OAuth2",
          secret: "Secret",
          refreshToken: "Refresh token",
        },
        actions: {
          submit: "Connecter",
          submitting: "Connexion…",
          cancel: "Annuler",
        },
        errors: {
          nameRequired: "Nom obligatoire",
          nameMax: "Maximum 200 caractères",
          endpointRequired: "Endpoint obligatoire",
          endpointInvalid: "Doit commencer par http://, https:// ou sse://",
          endpointNotAllowed: "Cet endpoint n'est pas dans la liste autorisée",
          secretRequired: "Un secret est requis pour ce type d'authentification",
          forbidden: "Vous n'avez pas la permission d'enregistrer des serveurs MCP",
          network: "Erreur réseau. Veuillez réessayer.",
          rateLimited: "Trop de tentatives. Veuillez patienter.",
          serverError: "Erreur serveur. Veuillez réessayer.",
        },
        success: {
          title: "Serveur connecté",
          body: "Les outils seront découverts lors de la prochaine synchronisation.",
        },
        permissionDenied: {
          title: "Accès refusé",
          body: "Vous n'avez pas la permission d'enregistrer des serveurs MCP.",
          back: "Retour aux serveurs MCP",
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
      AGENT_NOT_FOUND: "Agent introuvable",
      AGENT_TOOL_NOT_FOUND: "Un ou plusieurs outils n'existent pas",
      AGENT_TOOL_NOT_APPROVED: "Un ou plusieurs outils ne sont pas approuvés",
      AGENT_DISABLED: "Cet agent est désactivé",
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
