# WP-10 — Ejecutar el protocolo de captura

| | |
|---|---|
| **Fase** | F3 · Dataset real |
| **Estado** | `ESBOZO` — se detalla al activar F3 |
| **Defectos que cierra** | D-32 |
| **Depende de** | `WP-07` (posiciones canónicas), `WP-09` (nodos operativos) |
| **Nivel de verificación** | `hardware` |
| **Requiere intervención del usuario** | **sí — es una campaña de medición presencial** |
| **Repositorio** | `wifi-csi-capture` |

## Objetivo

Capturar el dataset real: sesiones etiquetadas en las 8 posiciones canónicas, con manifest
completo y trazabilidad, listas para calibrar el gemelo digital (F4) y entrenar (F6).

## Alcance

La infraestructura ya existe y es buena: `record_session.py` hace autodetección de puertos,
captura multinodo con `threading.Barrier`, ancla `t0_host_us`, manifest JSON y validación de
MAC. Lo que falta es **ejecutarla** de forma sistemática.

**Escenarios mínimos** (los que ya define `record_session.py`):

| Escenario | Duración sugerida | Propósito |
|---|---|---|
| `baseline_empty` | 300 s | Línea base electromagnética. Imprescindible para el filtro espacial |
| `stairs_walk` | 120 s | Persona subiendo/bajando |
| `stairs_still` | 120 s | Persona quieta — separa presencia de movimiento |

**Corrección incluida** — D-32: `measurement_protocol.py:225` pasa `--position str(round)`, y
los CSV de la ronda 2 (nodos en posiciones 3 y 4) se llaman `pos02`. `record_session.py` ya
lo hace bien; unificar o retirar `measurement_protocol.py`.

**Etiquetado**: para F6 hacen falta etiquetas más finas que el nombre del escenario. Decidir
el método al activar la fase: marcas de tiempo manuales, un pulsador GPIO, o vídeo de
referencia sincronizado (que reintroduce cámaras, aunque solo para etiquetar).

## Puerta de salida

```bash
python tools/session_qa.py data/sessions/
# Esperado por sesión: Hz ≥ 45 · drops = 0 · MAC 100 % esperada ·
#                      drift < 35 ms · manifest completo
```

Volumen: a definir según nodos disponibles y objetivo de F6. Como referencia, el presupuesto
de error temporal documentado en `ADVANCED.md` da ~35 ms en el peor caso a 5 minutos
(≈ 1,75 frames a 50 Hz), aceptable para clasificación de actividad pero **no** para pose con
alineación subframe.

## Pendiente de detallar

- Método de etiquetado y su precisión temporal.
- Número de sujetos y variabilidad (altura, corpulencia) — importa para la generalización y
  se corresponde con los `betas` de SMPL en `WP-15`.
- Cuántas repeticiones por escenario y posición.
- Protocolo de fotografía de las posiciones de los nodos (`measurement_protocol.py` ya lo
  pide en su paso 2).
