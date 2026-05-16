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
      models: { title: "Modelos LiteLLM", empty: "No hay modelos configurados" },
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
        empty: "No hay documentos indexados",
        upload: "Subir documento",
      },
    },
    mcp: {
      servers: {
        title: "Servidores MCP",
        empty: "No hay servidores conectados",
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
      models: { title: "LiteLLM models", empty: "No models configured" },
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
        empty: "No documents indexed yet",
        upload: "Upload document",
      },
    },
    mcp: {
      servers: {
        title: "MCP servers",
        empty: "No servers connected",
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
      models: { title: "Modèles LiteLLM", empty: "Aucun modèle configuré" },
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
        empty: "Aucun document indexé",
        upload: "Téléverser un document",
      },
    },
    mcp: {
      servers: {
        title: "Serveurs MCP",
        empty: "Aucun serveur connecté",
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
