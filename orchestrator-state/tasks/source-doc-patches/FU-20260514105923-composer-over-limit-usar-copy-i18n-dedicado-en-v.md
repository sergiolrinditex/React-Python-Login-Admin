# Source-of-truth amendment — FU-20260514105923-composer-over-limit-usar-copy-i18n-dedicado-en-v

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P03-S02-T005 | ux | Composer over-limit: usar copy i18n dedicado en vez de reusar placeholder | Runtime follow-up P03-S02-T001 | current | planned | low | human | P03-S02-T001 | front:chat | frontend/src/features/chat/presentation/Composer.tsx, frontend/public/locales/es/chat.json, frontend/public/locales/en/chat.json, frontend/public/locales/fr/chat.json, frontend/src/i18n/index.ts | J101 | /chat | — | — | runtime-followup#FU-20260514105923-composer-over-limit-usar-copy-i18n-dedicado-en-v | runtime-followup#FU-20260514105923-composer-over-limit-usar-copy-i18n-dedicado-en-v | Escribir >4000 chars en Composer dispara inline alert (role=alert, aria-live=assertive) cuyo texto proviene de una i18n key dedicada (e.g. chat.errors.tooLong) y NO reusa el placeholder. Tres locales (es, en, fr) traducen la key. Composer.tsx referencia la nueva key en vez del placeholder. | En Chrome /chat, escribir 4001 chars en composer + click Enviar → alert text es el i18n dedicado (no el placeholder). Cambiar locale a en y fr y reproducir → texto traducido. Tests vitest de Composer cubren el nuevo copy. Design tokens enforcer sigue verde. |
```
