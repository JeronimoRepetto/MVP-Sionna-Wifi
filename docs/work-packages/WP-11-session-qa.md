# WP-11 — QA automático de sesión

| | |
|---|---|
| **Fase** | F3 · Dataset real |
| **Estado** | `ESBOZO` — se detalla al activar F3 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-10` (necesita al menos una sesión) |
| **Nivel de verificación** | `hardware` |
| **Requiere intervención del usuario** | no |
| **Repositorio** | `wifi-csi-capture` |

## Objetivo

Un comando que diga si una sesión capturada es utilizable, **antes** de que alguien la use
para calibrar o entrenar. Una sesión con el 30 % de frames perdidos, MAC contaminada o deriva
temporal excesiva puede pasar desapercibida y envenenar todo lo que venga después.

## Alcance

`tools/session_qa.py`, nuevo. Por sesión y por nodo:

| Comprobación | Criterio propuesto | De dónde sale |
|---|---|---|
| Tasa efectiva | ≥ 45 Hz | `timestamps` de `analyze_csi.load_csi_file` |
| Frames perdidos | gaps de `rx_seq` < 1 % | campo `rx_seq` del CSV |
| Contaminación de MAC | 100 % la MAC esperada | `record_session.py` ya lo valida; consolidarlo |
| Subportadoras | 114 en ≥ 99 % de los frames | campo `len` |
| `sig_mode` | 1 (HT) en ≥ 99 % | campo `sig_mode` |
| Deriva temporal entre nodos | < 35 ms al final de la sesión | `t_abs_us` + `align_nodes_by_timestamp` |
| Cobertura de alineación | ≥ 95 % de frames con pareja en todos los nodos | tasa de descarte de `align_nodes_by_timestamp` |
| Estabilidad de RSSI | sin saltos > 10 dB sin causa | campo `rssi`; detecta problemas de AGC |
| Manifest | completo, con `t0_host_us` ≠ 0 | `session_manifest.json` |
| Baseline presente | existe una sesión `baseline_empty` de la misma ronda | estructura de directorios |

Salida: tabla verde/roja por nodo, veredicto global (`USABLE` / `DEGRADADA` / `DESCARTAR`), y
un `session_qa.json` junto al manifest para que la sesión lleve su calidad consigo.

**Reutilizar**: `analyze_csi.load_csi_file` y
`spatial_filter.align_nodes_by_timestamp`. No reimplementar parseo ni alineación.

## Puerta de salida

```bash
python tools/session_qa.py data/sessions/
# Esperado: todas las sesiones con veredicto USABLE, o un motivo explícito por cada una
```

```bash
python tools/session_qa.py data/sessions/<X> --json
# Esperado: session_qa.json escrito junto al manifest
```

## Pendiente de detallar

- Umbrales definitivos: los de arriba son propuestas informadas por el rendimiento medido
  (100 Hz internos, 50-93 Hz por serie) y por el presupuesto de error de `ADVANCED.md`. Hay
  que ajustarlos con datos reales.
- Si el QA debe rechazar automáticamente o solo avisar.
- Umbral de estabilidad de RSSI: depende de cuánto varíe el AGC en la práctica.
