# design_tokens_v1 — Stack-agnostic visual-token enforcer

The public enforcer name is capability-based, not framework-based.

`STACK_PROFILE.yaml` declares:

```yaml
frontend:
  framework: flutter | react | nextjs | vite | swiftui | none
  module_root: ...
  theme_root: ...
design_tokens_enforcer: design_tokens_v1
```

The dispatcher reads the framework and applies the relevant scanner:

- Flutter/Dart: uses `scripts/check_design_tokens.py` with `frontend.module_root` and `frontend.theme_root`.
- React/Next/Vite/TypeScript: forbids obvious inline hex/rgb literals outside token/theme files.
- SwiftUI: extension point; use a project-specific plugin for strict enforcement.
- `none`: explicit no-op.

The orchestrator engine must not depend on a Flutter-, React- or SwiftUI-named plugin.
