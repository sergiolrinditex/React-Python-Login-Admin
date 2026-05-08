#!/bin/bash

# ============================================================================
# INSTALL & CONFIGURE CLAUDE CODE - Script completo
# ============================================================================
# Instala Claude Code (CLI + extensión VS Code) y configura todas las
# variables de entorno necesarias para el entorno Inditex/LiteLLM.
#
# Uso:
#   bash .claude/scripts/install_claude_code.sh
#
# Variables configurables (editar abajo según necesidad):
#   - ANTHROPIC_AUTH_TOKEN_VALUE  → API key de LiteLLM
#   - ANTHROPIC_BASE_URL_VALUE   → URL del proxy LiteLLM
#   - MODEL                      → Modelo por defecto
# ============================================================================

# Asegurar ejecución bajo bash (arrays, [[ ]], etc.)
if [ -z "$BASH_VERSION" ]; then
    _SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    _SCRIPT_NAME="$(basename "$0")"
    /bin/bash "$_SCRIPT_DIR/$_SCRIPT_NAME" "$@"
    exit $?
fi

set -euo pipefail

# ========================= CONFIGURACIÓN =========================
# ⚠️  NUNCA commitear secrets reales. Usar variables de entorno o .env
ANTHROPIC_AUTH_TOKEN_VALUE="${ANTHROPIC_AUTH_TOKEN:-YOUR_ANTHROPIC_TOKEN_HERE}"
ANTHROPIC_BASE_URL_VALUE="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
CLAUDE_CODE_DISABLE_BETAS_VALUE="1"
GITHUB_PAT_VALUE="${GITHUB_PAT:-YOUR_GITHUB_PAT_HERE}"
CONTEXT7_API_KEY_VALUE="${CONTEXT7_API_KEY:-YOUR_CONTEXT7_KEY_HERE}"
# URL de PostgreSQL para el MCP de postgres (desarrollo local o remoto)
# Formato: postgresql://user:password@host:port/dbname
POSTGRES_MCP_DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/aifoundry}"
# =================================================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
log_success() { printf "${GREEN}[✔]${NC} %s\n" "$1"; }
log_warn()    { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
log_error()   { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

echo ""
echo "============================================================"
echo "   CLAUDE CODE - Instalación y configuración completa"
echo "============================================================"
echo ""

# ============================================================================
# 1. Verificar prerrequisitos (Node.js y npm)
# ============================================================================
log_info "Paso 1: Verificando prerrequisitos..."

if ! command -v node &> /dev/null; then
    log_error "Node.js no está instalado. Se requiere Node.js >= 18 (recomendado >= 22.13.1 con ivm-node)."
    log_info "Instálalo con: asdf install ivm-node 22.13.1 && asdf set --home ivm-node 22.13.1"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_VERSION" -lt 18 ]]; then
    log_error "Node.js versión $(node -v) es demasiado antigua. Se requiere >= 18 (recomendado >= 22.13.1)."
    exit 1
fi
if [[ "$NODE_VERSION" -lt 22 ]]; then
    log_warn "Node.js $(node -v) detectado. Se recomienda >= 22.13.1 con ivm-node para compatibilidad total."
fi
log_success "Node.js $(node -v) detectado"

if ! command -v npm &> /dev/null; then
    log_error "npm no está instalado."
    exit 1
fi
log_success "npm $(npm -v) detectado"

# ============================================================================
# 2. Instalar Claude Code CLI
# ============================================================================
log_info "Paso 2: Instalando Claude Code CLI..."

if command -v claude &> /dev/null; then
    CURRENT_VERSION=$(claude --version 2>/dev/null || echo "desconocida")
    log_info "Claude Code ya instalado (versión: $CURRENT_VERSION). Actualizando..."
fi

# Instalar via npm primero (necesario para obtener el comando claude)
npm install -g @anthropic-ai/claude-code 2>&1 | tail -3
if command -v asdf &> /dev/null; then
    asdf reshim ivm-node 2>/dev/null || true
fi

if ! command -v claude &> /dev/null; then
    log_error "No se pudo instalar Claude Code CLI. Revisa los errores anteriores."
    exit 1
fi
log_success "Claude Code CLI instalado via npm: $(claude --version 2>/dev/null || echo 'OK')"

# Cambiar al instalador nativo (recomendado por Anthropic)
log_info "Paso 2b: Instalando build nativo de Claude Code..."
claude install --force 2>&1 || true
if command -v asdf &> /dev/null; then
    asdf reshim ivm-node 2>/dev/null || true
fi
log_success "Build nativo instalado: $(claude --version 2>/dev/null || echo 'OK')"

# ============================================================================
# 3. Instalar extensión de VS Code
# ============================================================================
log_info "Paso 3: Instalando extensión de Claude Code en VS Code..."

CODE_CMD=""
if command -v code &> /dev/null; then
    CODE_CMD="code"
elif [[ -f "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
    CODE_CMD="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
fi

if [[ -n "$CODE_CMD" ]]; then
    EXT_INSTALLED=false

    # Comprobar si ya está instalada
    if "$CODE_CMD" --list-extensions 2>/dev/null | grep -q "anthropic.claude-code"; then
        log_success "Extensión anthropic.claude-code ya instalada en VS Code"
        EXT_INSTALLED=true
    else
        # Intento 1: instalación directa desde marketplace
        if "$CODE_CMD" --install-extension anthropic.claude-code --force 2>&1 | grep -q "successfully installed"; then
            EXT_INSTALLED=true
            log_success "Extensión anthropic.claude-code instalada en VS Code"
        else
            # Intento 2: descarga manual con curl (para certificados corporativos)
            log_warn "Instalación directa falló. Descargando .vsix manualmente..."
            VSIX_TMP="/tmp/claude-code-$$.vsix"

            # Obtener URL del .vsix para la plataforma actual (darwin-arm64, darwin-x64, linux-x64, etc.)
            TARGET_PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m | sed 's/aarch64/arm64/')"
            VSIX_URL=""
            VSIX_URL=$(curl -k -s --max-time 15 -X POST "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery" \
                -H "Content-Type: application/json" \
                -H "Accept: application/json;api-version=7.2-preview.1" \
                -d "{\"filters\":[{\"criteria\":[{\"filterType\":7,\"value\":\"anthropic.claude-code\"}],\"pageNumber\":1,\"pageSize\":1}],\"assetTypes\":[\"Microsoft.VisualStudio.Services.VSIXPackage\"],\"flags\":2151}" 2>/dev/null \
                | python3 -c "
import json,sys
data=json.load(sys.stdin)
for ext in data.get('results',[{}])[0].get('extensions',[]):
    for v in ext.get('versions',[]):
        tp=v.get('targetPlatform','')
        if '${TARGET_PLATFORM}' in str(tp):
            for f in v.get('files',[]):
                if 'VSIX' in f.get('assetType',''):
                    print(f['source']); break
            break
" 2>/dev/null || true)

            # Fallback: URL genérica si no se encontró la específica
            if [[ -z "$VSIX_URL" ]]; then
                VSIX_URL="https://marketplace.visualstudio.com/_apis/public/gallery/publishers/anthropic/vsextensions/claude-code/latest/vspackage"
            fi

            log_info "Descargando desde marketplace (puede tardar ~30s)..."
            if curl -fsSL -k --compressed --max-time 180 -o "$VSIX_TMP" "$VSIX_URL" 2>/dev/null && [[ -s "$VSIX_TMP" ]]; then
                if file "$VSIX_TMP" | grep -q "Zip"; then
                    "$CODE_CMD" --install-extension "$VSIX_TMP" --force 2>&1 && EXT_INSTALLED=true || true
                else
                    log_warn "Fichero descargado no es un .vsix válido"
                fi
            fi
            rm -f "$VSIX_TMP" 2>/dev/null
        fi
    fi

    if [[ "$EXT_INSTALLED" == true ]]; then
        if pgrep -f "Visual Studio Code" &>/dev/null; then
            log_info "VS Code está abierto — ejecuta Cmd+Shift+P → 'Reload Window' para activar la extensión"
        fi
    else
        log_warn "No se pudo instalar la extensión automáticamente."
        log_info "Instálala manualmente desde VS Code:"
        log_info "  1. Abre VS Code → Cmd+Shift+X (Extensiones)"
        log_info "  2. Busca 'Claude Code' de Anthropic → Instalar"
    fi
else
    log_warn "VS Code (comando 'code') no encontrado en PATH — extensión no instalada"
    log_info "Instálala manualmente desde: https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code"
fi

# ============================================================================
# 4. Detectar shell profile
# ============================================================================
log_info "Paso 4: Detectando shell profile..."

if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == */zsh ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == */bash ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
elif [[ -f "$HOME/.zshrc" ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
else
    log_error "No se pudo detectar el shell profile (.zshrc / .bashrc)"
    exit 1
fi

log_success "Shell profile: $SHELL_PROFILE"

# Crear backup
BACKUP_FILE="${SHELL_PROFILE}.bak.install.$(date +%Y%m%d%H%M%S)"
cp "$SHELL_PROFILE" "$BACKUP_FILE"
log_info "Backup creado: $BACKUP_FILE"

# ============================================================================
# 5. Configurar variables de entorno en shell profile
# ============================================================================
log_info "Paso 5: Configurando variables de entorno..."

# Función: forzar valor de variable (actualiza si existe, añade si no)
set_env_var() {
    local var_name="$1"
    local var_value="$2"
    local profile="$3"
    local export_line="export ${var_name}=${var_value}"

    if grep -q "^export ${var_name}=" "$profile" 2>/dev/null; then
        # Actualizar valor existente
        sed -i.tmp "s|^export ${var_name}=.*|${export_line}|" "$profile"
        rm -f "${profile}.tmp"
        log_success "Actualizado: ${var_name}"
    else
        # Añadir al principio del fichero
        local tmp_file
        tmp_file=$(mktemp)
        echo "$export_line" > "$tmp_file"
        cat "$profile" >> "$tmp_file"
        mv "$tmp_file" "$profile"
        log_success "Añadido: ${var_name}"
    fi
}

set_env_var "ANTHROPIC_AUTH_TOKEN" "$ANTHROPIC_AUTH_TOKEN_VALUE" "$SHELL_PROFILE"
set_env_var "ANTHROPIC_BASE_URL" "$ANTHROPIC_BASE_URL_VALUE" "$SHELL_PROFILE"
set_env_var "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS" "$CLAUDE_CODE_DISABLE_BETAS_VALUE" "$SHELL_PROFILE"
set_env_var "GITHUB_PAT" "$GITHUB_PAT_VALUE" "$SHELL_PROFILE"
set_env_var "CONTEXT7_API_KEY" "$CONTEXT7_API_KEY_VALUE" "$SHELL_PROFILE"

# ============================================================================
# 6. Configurar SSL para proxy corporativo (Inditex SSL Proxy)
# ============================================================================
# Claude Code es un binario Bun que usa CAs de Mozilla por defecto, NO el
# keychain del sistema. El proxy corporativo re-firma HTTPS con una CA propia
# que sí está en el keychain de macOS pero NO en el bundle de Bun.
# NODE_USE_SYSTEM_CA=1 le dice a Bun que use el keychain del sistema.
# NODE_EXTRA_CA_CERTS se respeta si ya existía (solo añade, nunca reemplaza).
# ============================================================================
log_info "Paso 6: Configurando SSL para proxy corporativo..."

# 6a. NODE_USE_SYSTEM_CA=1 — le dice a Bun que use el keychain de macOS
set_env_var "NODE_USE_SYSTEM_CA" "1" "$SHELL_PROFILE"
log_success "NODE_USE_SYSTEM_CA=1 configurado (Bun usará el keychain de macOS)"

# 6b. Exportar CAs corporativos a PEM como respaldo (NODE_EXTRA_CA_CERTS)
#     Esto es para herramientas que NO leen el keychain (algunas versiones de Bun, npm, etc.)
INDITEX_CA_FILE="$HOME/.claude/inditex-ca-bundle.pem"
log_info "Exportando CAs corporativos a ${INDITEX_CA_FILE}..."

EXPORTED_CERTS=0
: > "$INDITEX_CA_FILE"  # truncar
for ca_name in "ITX Root CA" "Inditex SSL Proxy" "Inditex Corporate Root" "ITX Corporate SubCA"; do
    if security find-certificate -a -c "$ca_name" -p /Library/Keychains/System.keychain >> "$INDITEX_CA_FILE" 2>/dev/null; then
        EXPORTED_CERTS=$((EXPORTED_CERTS + 1))
    fi
done

if [[ $EXPORTED_CERTS -gt 0 ]] && [[ -s "$INDITEX_CA_FILE" ]]; then
    CERT_COUNT=$(grep -c "BEGIN CERTIFICATE" "$INDITEX_CA_FILE" 2>/dev/null || echo 0)
    set_env_var "NODE_EXTRA_CA_CERTS" "$INDITEX_CA_FILE" "$SHELL_PROFILE"
    log_success "Exportados ${CERT_COUNT} certificados corporativos a ${INDITEX_CA_FILE}"
else
    log_warn "No se encontraron CAs corporativos en el keychain — NODE_EXTRA_CA_CERTS no configurado"
    log_info "Si tienes problemas SSL, importa los CAs de Inditex al keychain del sistema"
fi

# 6c. Descomentar NODE_EXTRA_CA_CERTS si lo habíamos comentado en una ejecución anterior
if grep -q "^# export NODE_EXTRA_CA_CERTS=" "$SHELL_PROFILE" 2>/dev/null; then
    sed -i.tmp 's/^# export NODE_EXTRA_CA_CERTS=/export NODE_EXTRA_CA_CERTS=/' "$SHELL_PROFILE"
    rm -f "${SHELL_PROFILE}.tmp"
    log_success "NODE_EXTRA_CA_CERTS descomentado (había sido comentado por una ejecución anterior)"
fi

# ============================================================================
# 7. Configurar ~/.claude/settings.json
# ============================================================================
log_info "Paso 7: Configurando settings.json..."

# Global: permisos permisivos para no pedir confirmación en cada tool call
CLAUDE_GLOBAL_DIR="$HOME/.claude"
CLAUDE_GLOBAL_FILE="$CLAUDE_GLOBAL_DIR/settings.json"
mkdir -p "$CLAUDE_GLOBAL_DIR"
cat > "$CLAUDE_GLOBAL_FILE" <<'GLOBAL_SETTINGS_EOF'
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep",
      "WebSearch",
      "WebFetch",
      "Agent",
      "NotebookEdit"
    ]
  }
}
GLOBAL_SETTINGS_EOF
log_success "Configurado ~/.claude/settings.json (permisos permisivos globales)"

# Local del proyecto: configurar modelos específicos
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAUDE_LOCAL_DIR="$PROJECT_DIR/.claude"
CLAUDE_SETTINGS_FILE="$CLAUDE_LOCAL_DIR/settings.json"

mkdir -p "$CLAUDE_LOCAL_DIR"

cat > "$CLAUDE_SETTINGS_FILE" <<'SETTINGS_EOF'
{
  "model": "bedrock/claude-opus-4.6",
  "env": {
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "bedrock/claude-sonnet-4.6",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "bedrock/claude-opus-4.6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "bedrock/claude-haiku-4.5"
  }
}
SETTINGS_EOF

log_success "Configurado $CLAUDE_SETTINGS_FILE (modelos por defecto del proyecto)"

# Local del proyecto: settings.local.json con permisos permisivos y MCP servers habilitados
CLAUDE_LOCAL_SETTINGS_FILE="$CLAUDE_LOCAL_DIR/settings.local.json"

cat > "$CLAUDE_LOCAL_SETTINGS_FILE" <<'LOCAL_SETTINGS_EOF'
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep",
      "WebSearch",
      "WebFetch",
      "Agent",
      "NotebookEdit"
    ]
  },
  "enabledMcpjsonServers": [
    "docs-langchain",
    "context7",
    "github",
    "sentry",
    "postgres",
    "pgvector"
  ]
}
LOCAL_SETTINGS_EOF

log_success "Configurado $CLAUDE_LOCAL_SETTINGS_FILE (permisos permisivos + MCP servers)"
log_info "  Default: bedrock/claude-opus-4.6"
log_info "  Sonnet: bedrock/claude-sonnet-4.6"
log_info "  Opus:   bedrock/claude-opus-4.6"
log_info "  Haiku:  bedrock/claude-haiku-4.5"

# ============================================================================
# 8. Configurar MCP servers
# ============================================================================
log_info "Paso 8: Configurando MCP servers..."

# --------------------------------------------------------------------------
# 8a. Instalar herramientas MCP locales (stdio) — requieren binario en PATH
# --------------------------------------------------------------------------
log_info "Instalando MCP servers locales (stdio)..."

install_pip_tool() {
    local pkg="$1"
    if command -v pipx &> /dev/null; then
        pipx install "$pkg" 2>/dev/null && \
            log_success "$pkg instalado via pipx" || \
            log_info "$pkg ya instalado o no se pudo instalar via pipx"
    elif command -v uv &> /dev/null; then
        uv tool install "$pkg" 2>/dev/null && \
            log_success "$pkg instalado via uv" || \
            log_info "$pkg ya instalado o no se pudo instalar via uv"
    else
        log_warn "Ni pipx ni uv disponibles — $pkg no instalado"
        log_info "Instálalo manualmente: pipx install $pkg"
    fi
}

install_pip_tool "postgres-mcp"
install_pip_tool "pgvector-mcp-server"

# --------------------------------------------------------------------------
# 8b. Escribir .mcp.json en la RAÍZ del proyecto
#     Claude Code lee este fichero automáticamente para project-scope MCPs.
#     Los valores usan sintaxis ${ENV_VAR} que Claude Code expande en runtime
#     a partir de las variables de entorno del shell (configuradas en paso 5).
# --------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MCP_JSON_FILE="${PROJECT_ROOT}/.mcp.json"

log_info "Escribiendo ${MCP_JSON_FILE} con todos los MCP servers..."

cat > "$MCP_JSON_FILE" << 'MCP_EOF'
{
  "mcpServers": {
    "docs-langchain": {
      "type": "http",
      "url": "https://docs.langchain.com/mcp"
    },
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "X-API-Key": "${CONTEXT7_API_KEY}"
      }
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    },
    "sentry": {
      "type": "http",
      "url": "https://mcp.sentry.dev/mcp"
    },
    "postgres": {
      "command": "postgres-mcp",
      "args": ["${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/aifoundry}"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/aifoundry}"
      }
    },
    "pgvector": {
      "command": "pgvector-mcp-server",
      "env": {
        "DATABASE_URL": "${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/aifoundry}"
      }
    }
  }
}
MCP_EOF

log_success ".mcp.json escrito en ${MCP_JSON_FILE}"

# Añadir .mcp.json al .gitignore si no está (contiene tokens)
GITIGNORE_FILE="${PROJECT_ROOT}/.gitignore"
if [[ -f "$GITIGNORE_FILE" ]]; then
    if ! grep -q "^\.mcp\.json$" "$GITIGNORE_FILE" 2>/dev/null; then
        echo "" >> "$GITIGNORE_FILE"
        echo "# MCP config con tokens — no subir a git" >> "$GITIGNORE_FILE"
        echo ".mcp.json" >> "$GITIGNORE_FILE"
        log_success ".mcp.json añadido a .gitignore (contiene tokens sensibles)"
    else
        log_info ".mcp.json ya está en .gitignore"
    fi
else
    echo "# MCP config con tokens — no subir a git" > "$GITIGNORE_FILE"
    echo ".mcp.json" >> "$GITIGNORE_FILE"
    log_success ".gitignore creado con .mcp.json"
fi

# Eliminar template antiguo de scripts/ si existe
OLD_TEMPLATE="${PROJECT_ROOT}/.claude/scripts/.mcp.json"
if [[ -f "$OLD_TEMPLATE" ]]; then
    rm -f "$OLD_TEMPLATE"
    log_info "Template antiguo .claude/scripts/.mcp.json eliminado"
fi

log_info ""
log_info "MCP servers configurados en .mcp.json:"
log_info "  Remotos (HTTP):"
log_info "    - docs-langchain: LangChain/LangGraph/LangSmith docs"
log_info "    - context7: Docs de cualquier librería (con API key)"
log_info "    - github: PRs, issues, code reviews (con PAT)"
log_info "    - sentry: Error monitoring (ejecuta '/mcp' en Claude para OAuth)"
log_info "  Locales (stdio):"
log_info "    - postgres: PostgreSQL tuning/analysis (DB: ${POSTGRES_MCP_DB_URL})"
log_info "    - pgvector: Vector search/CRUD con pgvector (DB: ${POSTGRES_MCP_DB_URL})"

# ============================================================================
# 9. Exportar variables en sesión actual
# ============================================================================
log_info "Paso 9: Exportando variables en sesión actual..."

export ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN_VALUE"
export ANTHROPIC_BASE_URL="$ANTHROPIC_BASE_URL_VALUE"
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="$CLAUDE_CODE_DISABLE_BETAS_VALUE"
export GITHUB_PAT="$GITHUB_PAT_VALUE"
export CONTEXT7_API_KEY="$CONTEXT7_API_KEY_VALUE"
export NODE_USE_SYSTEM_CA="1"
if [[ -f "$HOME/.claude/inditex-ca-bundle.pem" ]]; then
    export NODE_EXTRA_CA_CERTS="$HOME/.claude/inditex-ca-bundle.pem"
fi

log_success "Variables exportadas en sesión actual"

# ============================================================================
# 10. Verificación final
# ============================================================================
echo ""
log_info "Paso 10: Verificación final..."

ISSUES=0

# Verificar CLI
if command -v claude &> /dev/null; then
    log_success "CLI: claude disponible en $(which claude)"
else
    log_error "CLI: claude no encontrado en PATH"
    ISSUES=$((ISSUES + 1))
fi

# Verificar extensión VS Code
if [[ -n "$CODE_CMD" ]]; then
    if "$CODE_CMD" --list-extensions 2>/dev/null | grep -q "anthropic.claude-code"; then
        log_success "VS Code: extensión anthropic.claude-code instalada"
    else
        log_warn "VS Code: extensión no detectada"
        ISSUES=$((ISSUES + 1))
    fi
fi

# Verificar variables
for var in ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS GITHUB_PAT CONTEXT7_API_KEY NODE_USE_SYSTEM_CA; do
    if grep -q "^export ${var}=" "$SHELL_PROFILE" 2>/dev/null; then
        log_success "Env: ${var} configurada en $SHELL_PROFILE"
    else
        log_error "Env: ${var} NO encontrada en $SHELL_PROFILE"
        ISSUES=$((ISSUES + 1))
    fi
done

# Verificar settings.json
if [[ -f "$CLAUDE_SETTINGS_FILE" ]]; then
    log_success "Config: $CLAUDE_SETTINGS_FILE existe"
else
    log_error "Config: $CLAUDE_SETTINGS_FILE no encontrado"
    ISSUES=$((ISSUES + 1))
fi

# Verificar .mcp.json en raíz del proyecto
if [[ -f "$MCP_JSON_FILE" ]]; then
    log_success "MCP: .mcp.json existe en $(dirname "$MCP_JSON_FILE")"
    for mcp_name in docs-langchain context7 github sentry postgres pgvector; do
        if grep -q "\"$mcp_name\"" "$MCP_JSON_FILE" 2>/dev/null; then
            log_success "MCP: $mcp_name configurado en .mcp.json"
        else
            log_warn "MCP: $mcp_name no encontrado en .mcp.json"
            ISSUES=$((ISSUES + 1))
        fi
    done
else
    log_error "MCP: .mcp.json no encontrado en $(dirname "$MCP_JSON_FILE")"
    ISSUES=$((ISSUES + 1))
fi

# Verificar binarios MCP locales
for tool_bin in postgres-mcp pgvector-mcp-server; do
    if command -v "$tool_bin" &> /dev/null; then
        log_success "MCP local: $tool_bin disponible en $(which "$tool_bin")"
    else
        log_warn "MCP local: $tool_bin no encontrado en PATH (puede necesitar 'source $SHELL_PROFILE')"
    fi
done

# Verificar SSL corporativo
if grep -q "^export NODE_USE_SYSTEM_CA=1" "$SHELL_PROFILE" 2>/dev/null; then
    log_success "SSL: NODE_USE_SYSTEM_CA=1 configurado"
else
    log_warn "SSL: NODE_USE_SYSTEM_CA no encontrado en $SHELL_PROFILE"
    ISSUES=$((ISSUES + 1))
fi

INDITEX_CA_FILE_CHECK="$HOME/.claude/inditex-ca-bundle.pem"
if [[ -f "$INDITEX_CA_FILE_CHECK" ]] && [[ -s "$INDITEX_CA_FILE_CHECK" ]]; then
    CA_COUNT=$(grep -c "BEGIN CERTIFICATE" "$INDITEX_CA_FILE_CHECK" 2>/dev/null || echo 0)
    log_success "SSL: CA bundle corporativo ($CA_COUNT certificados en $INDITEX_CA_FILE_CHECK)"
else
    log_warn "SSL: CA bundle corporativo no encontrado o vacío ($INDITEX_CA_FILE_CHECK)"
fi

# Verificar conectividad SSL con un MCP HTTP (test rápido)
if command -v node &> /dev/null; then
    SSL_TEST=$(NODE_USE_SYSTEM_CA=1 node -e "
        fetch('https://docs.langchain.com/mcp', {method:'POST',headers:{'Content-Type':'application/json'},body:'{\"jsonrpc\":\"2.0\",\"method\":\"initialize\",\"id\":1,\"params\":{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"0.1\"}}}'})
        .then(r => console.log('OK:' + r.status))
        .catch(e => console.log('FAIL:' + e.message))
    " 2>&1 || echo "FAIL:node-error")
    if [[ "$SSL_TEST" == OK:* ]]; then
        log_success "SSL: Conectividad verificada con docs.langchain.com/mcp (${SSL_TEST})"
    else
        log_warn "SSL: No se pudo conectar a docs.langchain.com/mcp (${SSL_TEST})"
        log_info "  Asegúrate de que NODE_USE_SYSTEM_CA=1 está activo (source $SHELL_PROFILE)"
        ISSUES=$((ISSUES + 1))
    fi
fi

# ============================================================================
# Resumen
# ============================================================================
echo ""
echo "============================================================"
if [[ $ISSUES -eq 0 ]]; then
    log_success "¡Instalación completada correctamente!"
else
    log_warn "Instalación completada con $ISSUES advertencia(s). Revisa los mensajes anteriores."
fi
echo "============================================================"
echo ""

log_info "Para empezar a usar Claude Code:"
log_info "  1. Reinicia tu terminal (o ejecuta: source $SHELL_PROFILE)"
log_info "  2. Ejecuta: claude"
log_info "  3. En VS Code, la extensión ya debería estar disponible"
echo ""