#!/bin/bash

# ============================================================================
# UNINSTALL CLAUDE CODE - Desinstalación y limpieza completa
# ============================================================================
# Elimina completamente Claude Code del sistema:
#   - CLI (npm global)
#   - Extensión de VS Code
#   - Variables de entorno del shell profile
#   - Configuración (~/.claude, ~/.claude.json)
#   - Caché (npx, npm, ~/Library/Caches)
#   - Completions de shell
#
# Uso:
#   bash .claude/scripts/uninstall_claude_code.sh
#   sh .claude/scripts/uninstall_claude_code.sh
#   ./.claude/scripts/uninstall_claude_code.sh
#
# Compatible con bash, zsh y sh. No hace preguntas interactivas.
# ============================================================================

# Asegurar ejecución bajo bash
if [ -z "$BASH_VERSION" ]; then
    _SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    _SCRIPT_NAME="$(basename "$0")"
    /bin/bash "$_SCRIPT_DIR/$_SCRIPT_NAME" "$@"
    exit $?
fi

set -euo pipefail

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

# Helper: eliminar fichero, directorio o symlink
remove_path() {
    local target="$1"
    if [[ -L "$target" ]]; then
        rm -f "$target" && log_success "Eliminado symlink: $target" || log_warn "No se pudo eliminar: $target"
    elif [[ -d "$target" ]]; then
        rm -rf "$target" && log_success "Eliminado directorio: $target" || log_warn "No se pudo eliminar: $target"
    elif [[ -f "$target" ]]; then
        rm -f "$target" && log_success "Eliminado fichero: $target" || log_warn "No se pudo eliminar: $target"
    fi
}

echo ""
echo "============================================================"
echo "   CLAUDE CODE - Desinstalación completa"
echo "============================================================"
echo ""

# ============================================================================
# 1. Eliminar variables de entorno del shell profile
# ============================================================================
log_info "Paso 1: Eliminando variables de entorno del shell profile..."

# Detectar shell profile
if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == */zsh ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == */bash ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
elif [[ -f "$HOME/.zshrc" ]]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
else
    SHELL_PROFILE=""
fi

if [[ -n "$SHELL_PROFILE" && -f "$SHELL_PROFILE" ]]; then
    BACKUP_FILE="${SHELL_PROFILE}.bak.uninstall.$(date +%Y%m%d%H%M%S)"
    cp "$SHELL_PROFILE" "$BACKUP_FILE"
    log_info "Backup: $BACKUP_FILE"

    VARS_TO_REMOVE=(
        "ANTHROPIC_AUTH_TOKEN"
        "ANTHROPIC_BASE_URL"
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"
        "GITHUB_PAT"
        "CONTEXT7_API_KEY"
    )

    for var in "${VARS_TO_REMOVE[@]}"; do
        if grep -q "^export ${var}=" "$SHELL_PROFILE" 2>/dev/null; then
            sed -i.tmp "/^export ${var}=/d" "$SHELL_PROFILE"
            rm -f "${SHELL_PROFILE}.tmp"
            log_success "Eliminada: export ${var}"
        else
            log_info "${var} no encontrada en ${SHELL_PROFILE}"
        fi
    done

    # Restaurar NODE_EXTRA_CA_CERTS si fue comentado
    if grep -q "^# export NODE_EXTRA_CA_CERTS=" "$SHELL_PROFILE" 2>/dev/null; then
        sed -i.tmp 's/^# export NODE_EXTRA_CA_CERTS=/export NODE_EXTRA_CA_CERTS=/' "$SHELL_PROFILE"
        rm -f "${SHELL_PROFILE}.tmp"
        log_success "NODE_EXTRA_CA_CERTS restaurado (descomentado)"
    fi

    for var in "${VARS_TO_REMOVE[@]}"; do
        unset "$var" 2>/dev/null || true
    done
else
    log_warn "No se encontró shell profile — saltando limpieza de variables"
fi

# ============================================================================
# 2. Descubrir y eliminar binarios de claude
# ============================================================================
log_info "Paso 2: Buscando y eliminando binarios de claude..."

which -a claude 2>/dev/null | while IFS= read -r bin_path; do
    [[ -z "$bin_path" ]] && continue
    log_info "Encontrado: $bin_path"
    remove_path "$bin_path"
done || true

for bin_dir in /usr/local/bin /usr/bin "$HOME/.local/bin" "$HOME/.npm-global/bin"; do
    for name in claude claude-code; do
        if [[ -e "$bin_dir/$name" || -L "$bin_dir/$name" ]]; then
            remove_path "$bin_dir/$name"
        fi
    done
done

# ============================================================================
# 3. Desinstalar paquete npm/bun global
# ============================================================================
log_info "Paso 3: Desinstalando paquete global..."

if command -v npm &> /dev/null; then
    npm uninstall -g @anthropic-ai/claude-code 2>/dev/null && \
        log_success "npm: @anthropic-ai/claude-code desinstalado" || \
        log_info "npm: paquete no instalado globalmente"

    if command -v asdf &> /dev/null; then
        asdf reshim ivm-node 2>/dev/null || true
    fi
else
    log_info "npm no disponible — saltando"
fi

if command -v bun &> /dev/null; then
    bun uninstall -g @anthropic-ai/claude-code 2>/dev/null && \
        log_success "bun: @anthropic-ai/claude-code desinstalado" || \
        log_info "bun: paquete no instalado globalmente"
fi

# ============================================================================
# 4. Desinstalar extensión de VS Code
# ============================================================================
log_info "Paso 4: Desinstalando extensión de VS Code..."

CODE_CMD=""
if command -v code &> /dev/null; then
    CODE_CMD="code"
elif [[ -f "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
    CODE_CMD="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
fi

if [[ -n "$CODE_CMD" ]]; then
    "$CODE_CMD" --uninstall-extension anthropic.claude-code 2>/dev/null && \
        log_success "Extensión anthropic.claude-code desinstalada" || \
        log_info "Extensión no encontrada en VS Code"

    if [[ -d "$HOME/.vscode/extensions" ]]; then
        find "$HOME/.vscode/extensions" -maxdepth 1 -type d -iname "anthropic.claude-code-*" 2>/dev/null | while IFS= read -r ext_dir; do
            [[ -z "$ext_dir" ]] && continue
            remove_path "$ext_dir"
        done || true
    fi
else
    log_info "VS Code no encontrado — saltando"
fi

# ============================================================================
# 5. Eliminar caché de npx
# ============================================================================
log_info "Paso 5: Limpiando caché de npx..."

NPX_CACHE_DIR="$HOME/.npm/_npx"
if [[ -d "$NPX_CACHE_DIR" ]]; then
    find "$NPX_CACHE_DIR" -path "*/@anthropic-ai/claude-code" -type d 2>/dev/null | while IFS= read -r npx_dir; do
        [[ -z "$npx_dir" ]] && continue
        local_npx_root="$(echo "$npx_dir" | sed "s|/node_modules/@anthropic-ai/claude-code.*||")"
        if [[ -n "$local_npx_root" && -d "$local_npx_root" ]]; then
            remove_path "$local_npx_root"
        fi
    done || true
fi

# ============================================================================
# 6. Eliminar node_modules residuales
# ============================================================================
log_info "Paso 6: Buscando instalaciones residuales en node_modules..."

for search_root in /usr/local/lib /usr/lib "$HOME/.npm-global" "$HOME/.nvm"; do
    [[ -d "$search_root" ]] || continue
    find "$search_root" -path "*node_modules/@anthropic-ai/claude-code" -type d 2>/dev/null | while IFS= read -r nm_dir; do
        [[ -z "$nm_dir" ]] && continue
        remove_path "$nm_dir"
    done || true
done

# ============================================================================
# 7. Eliminar MCP servers configurados
# ============================================================================
log_info "Paso 7: Eliminando MCP servers..."

# Eliminar .mcp.json de la raíz del proyecto (contiene tokens)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCP_JSON_FILE="${PROJECT_ROOT}/.mcp.json"

if [[ -f "$MCP_JSON_FILE" ]]; then
    rm -f "$MCP_JSON_FILE"
    log_success ".mcp.json eliminado de ${PROJECT_ROOT}"
else
    log_info ".mcp.json no encontrado en ${PROJECT_ROOT}"
fi

# Eliminar template antiguo si existe
OLD_TEMPLATE="${PROJECT_ROOT}/.claude/scripts/.mcp.json"
if [[ -f "$OLD_TEMPLATE" ]]; then
    rm -f "$OLD_TEMPLATE"
    log_success "Template antiguo .claude/scripts/.mcp.json eliminado"
fi

# Eliminar settings.local.json del proyecto (permisos y MCP servers habilitados)
CLAUDE_LOCAL_SETTINGS="${PROJECT_ROOT}/.claude/settings.local.json"
if [[ -f "$CLAUDE_LOCAL_SETTINGS" ]]; then
    rm -f "$CLAUDE_LOCAL_SETTINGS"
    log_success "settings.local.json eliminado de ${PROJECT_ROOT}/.claude/"
else
    log_info "settings.local.json no encontrado en ${PROJECT_ROOT}/.claude/"
fi

# Limpiar registros de MCP en claude CLI si está disponible
if command -v claude &> /dev/null; then
    MCP_SERVERS_TO_REMOVE=(docs-langchain context7 github sentry postgres pgvector)
    for mcp_name in "${MCP_SERVERS_TO_REMOVE[@]}"; do
        claude mcp remove "$mcp_name" 2>/dev/null && \
            log_success "MCP server $mcp_name eliminado de claude CLI" || \
            log_info "MCP server $mcp_name no registrado en claude CLI"
    done
else
    log_info "claude CLI no disponible — saltando limpieza de registros MCP"
fi

# Desinstalar herramientas MCP locales (stdio)
log_info "Desinstalando herramientas MCP locales..."
for pkg in postgres-mcp pgvector-mcp-server; do
    if command -v pipx &> /dev/null; then
        pipx uninstall "$pkg" 2>/dev/null && \
            log_success "$pkg desinstalado (pipx)" || \
            log_info "$pkg no estaba instalado via pipx"
    fi
    if command -v uv &> /dev/null; then
        uv tool uninstall "$pkg" 2>/dev/null && \
            log_success "$pkg desinstalado (uv)" || \
            log_info "$pkg no estaba instalado via uv"
    fi
done

# ============================================================================
# 8. Eliminar ~/.claude y ~/.claude.json
# ============================================================================
log_info "Paso 8: Eliminando directorio de configuración ~/.claude..."

remove_path "$HOME/.claude"
remove_path "$HOME/.claude.json"

# ============================================================================
# 9. Eliminar archivos de configuración y datos
# ============================================================================
log_info "Paso 9: Limpiando archivos de configuración y datos..."

DATA_SEARCH_DIRS=(
    "$HOME/.config"
    "$HOME/.local/share"
    "$HOME/.local/state"
)

for dir in "${DATA_SEARCH_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        find "$dir" -maxdepth 2 \( -iname "*claude*" -o -iname "*@anthropic-ai*" \) 2>/dev/null | while IFS= read -r found_path; do
            [[ -z "$found_path" ]] && continue
            case "$found_path" in
                *claude-code*|*claude_code*|*@anthropic-ai*|*/claude|*/claude/*)
                    remove_path "$found_path"
                    ;;
            esac
        done || true
    fi
done

for loc in "$HOME/.claude-code" "$HOME/.config/@anthropic-ai"; do
    remove_path "$loc"
done

# ============================================================================
# 10. Eliminar directorios de caché
# ============================================================================
log_info "Paso 10: Limpiando directorios de caché..."

CACHE_SEARCH_DIRS=(
    "$HOME/.cache"
    "$HOME/Library/Caches"
)

for dir in "${CACHE_SEARCH_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        find "$dir" -maxdepth 2 -iname "*claude*" 2>/dev/null | while IFS= read -r cache_path; do
            [[ -z "$cache_path" ]] && continue
            remove_path "$cache_path"
        done || true
    fi
done

# ============================================================================
# 11. Eliminar shell completions
# ============================================================================
log_info "Paso 11: Eliminando shell completions..."

COMPLETION_SEARCH_DIRS=(
    "$HOME/.zsh"
    "$HOME/.bash_completion.d"
    "/usr/local/share/zsh/site-functions"
    "/usr/share/bash-completion/completions"
    "/usr/local/share/bash-completion/completions"
)

for dir in "${COMPLETION_SEARCH_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        find "$dir" -maxdepth 2 -iname "*claude*" -type f 2>/dev/null | while IFS= read -r comp_file; do
            [[ -z "$comp_file" ]] && continue
            remove_path "$comp_file"
        done || true
    fi
done

# ============================================================================
# 12. Avisar sobre referencias en shell configs
# ============================================================================
log_info "Paso 12: Comprobando referencias residuales en shell configs..."

SHELL_CONFIGS=()
for rc in ".zshrc" ".bashrc" ".bash_profile" ".profile" ".zprofile"; do
    [[ -f "$HOME/$rc" ]] && SHELL_CONFIGS+=("$HOME/$rc")
done

for config in "${SHELL_CONFIGS[@]}"; do
    if grep -qi "claude" "$config" 2>/dev/null; then
        log_warn "Hay referencias a 'claude' en $config — revisa manualmente:"
        grep -n -i "claude" "$config" 2>/dev/null | head -5 | while read -r line; do
            echo "         $line"
        done
    fi
done

# ============================================================================
# 13. Verificación final
# ============================================================================
echo ""
log_info "Paso 13: Verificación final..."

ISSUES=0

if command -v claude &> /dev/null; then
    log_error "claude todavía existe: $(which claude)"
    ISSUES=$((ISSUES + 1))
else
    log_success "claude no encontrado en PATH"
fi

if [[ -d "$HOME/.claude" ]]; then
    log_warn "~/.claude todavía existe"
    ISSUES=$((ISSUES + 1))
else
    log_success "~/.claude eliminado"
fi

if [[ -f "$HOME/.claude.json" ]]; then
    log_warn "~/.claude.json todavía existe"
    ISSUES=$((ISSUES + 1))
else
    log_success "~/.claude.json eliminado"
fi

if [[ -n "$CODE_CMD" ]]; then
    if "$CODE_CMD" --list-extensions 2>/dev/null | grep -q "anthropic.claude-code"; then
        log_warn "Extensión de VS Code todavía instalada"
        ISSUES=$((ISSUES + 1))
    else
        log_success "Extensión de VS Code eliminada"
    fi
fi

REMAINING=$(find "$HOME" -maxdepth 4 \
    \( -iname "*claude-code*" -o -iname "*claude_code*" -o -iname "*claude-cli*" \) \
    -not -path "*/Desktop/*" \
    -not -path "*/.Trash/*" \
    -not -path "*/node_modules/.package-lock.json" \
    2>/dev/null | head -20 || true)

if [[ -n "$REMAINING" ]]; then
    log_warn "Archivos residuales encontrados:"
    echo "$REMAINING" | while read -r f; do
        echo "         $f"
    done
    ISSUES=$((ISSUES + 1))
fi

if [[ -n "${SHELL_PROFILE:-}" && -f "$SHELL_PROFILE" ]]; then
    for var in ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS GITHUB_PAT CONTEXT7_API_KEY; do
        if grep -q "^export ${var}=" "$SHELL_PROFILE" 2>/dev/null; then
            log_warn "${var} todavía en $SHELL_PROFILE"
            ISSUES=$((ISSUES + 1))
        else
            log_success "${var} eliminada de $SHELL_PROFILE"
        fi
    done
fi

# ============================================================================
# Resumen
# ============================================================================
echo ""
echo "============================================================"
if [[ $ISSUES -eq 0 ]]; then
    log_success "¡Claude Code eliminado completamente!"
else
    log_warn "Desinstalación completada con $ISSUES advertencia(s). Revisa los mensajes anteriores."
fi
echo "============================================================"
echo ""

# ============================================================================
# 14. Reiniciar VS Code para que se apliquen los cambios
# ============================================================================
log_info "Paso 14: Reiniciando VS Code..."

if [[ -n "$CODE_CMD" ]] && pgrep -f "Visual Studio Code" &>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
        osascript -e 'quit app "Visual Studio Code"' 2>/dev/null || true
    else
        pkill -f "Visual Studio Code" 2>/dev/null || true
    fi
    log_info "Esperando a que VS Code se cierre..."
    sleep 3

    if [[ "$(uname)" == "Darwin" ]]; then
        open -a "Visual Studio Code" 2>/dev/null && \
            log_success "VS Code reiniciado (extensión eliminada)" || \
            log_warn "No se pudo reabrir VS Code automáticamente"
    else
        nohup "$CODE_CMD" &>/dev/null &
        log_success "VS Code reiniciado"
    fi
else
    if [[ -n "$CODE_CMD" ]]; then
        log_info "VS Code no está abierto — no es necesario reiniciar"
    fi
fi

log_info "Reinicia tu terminal para que los cambios surtan efecto."
echo ""