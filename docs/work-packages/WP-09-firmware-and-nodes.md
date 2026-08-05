# WP-09 — Reparar el firmware y flashear los nodos

| | |
|---|---|
| **Fase** | F3 · Dataset real |
| **Estado** | `ESBOZO` — se detalla al activar F3 |
| **Defectos que cierra** | D-23, D-28, D-29, D-30, D-31, D-33 |
| **Depende de** | `WP-00c` (ESP-IDF operativo) |
| **Nivel de verificación** | `hardware` |
| **Requiere intervención del usuario** | **sí — hardware físico y router dedicado** |
| **Repositorio** | `wifi-csi-capture` |

## Objetivo

Dejar los N nodos ESP32-S3 disponibles compilados, flasheados y verificados a ~100 Hz de
CSI, y cerrar los defectos del firmware detectados en la revisión.

## Alcance

**Correcciones de firmware** (`main/csi_capture_main.c`):

| Defecto | Cambio |
|---|---|
| D-23 | Leer `CONFIG_CSI_UART_BAUD` en lugar de hardcodear `921600`. Hoy la opción de `menuconfig` es inerte y `ADVANCED.md` la documenta como funcional |
| D-28 | `xQueueSendFromISR` → `xQueueSend(..., 0)`. El callback de CSI corre en contexto de tarea Wi-Fi, no en una ISR |
| D-29 | Mover el formateo fuera del callback: encolar los 228 bytes `int8` crudos y hacer el `snprintf` en `csi_output_task`. Es el objetivo declarado del diseño y hoy no se cumple |
| D-30 | Eliminar `#define PING_TARGET_IP "0.0.0.0"`, que no se usa |
| D-33 | Consecuencia de D-29: la cola baja de ~45 KB (32 × 1.404 B) a ~8 KB |

**Higiene del repositorio**: D-31 — añadir `tests/tmp/` al `.gitignore` (el `conftest.py`
redirige `tmp_path` ahí y no limpia).

**Puesta en marcha**: router dedicado a 2,4 GHz / 802.11n / HT40 / canal fijo y aislado;
`menuconfig` con SSID, contraseña, canal y BSSID; build, flash y verificación por nodo.

## Puerta de salida

```bash
# Por cada nodo
python tools/diagnose_serial.py --port COM<N> --duration 15
# Esperado: Tasa CSI ≈ 100 Hz · Subportadoras 114 · Frames HT 100 % · Drops 0

# Los 73 tests del repo
pip install -r tools/requirements.txt && python -m pytest tests/ -q
# Esperado: 73 passed
```

Y que el cambio de D-29 no haya degradado nada: la tasa de CSI debe mantenerse o mejorar, y
`[STATUS]` debe seguir reportando `Drops: 0`.

## Pendiente de detallar

- Número de nodos realmente disponibles (condiciona el protocolo de F3 y la diversidad
  espacial). Con 2 nodos se usan las 4 rondas de `record_session.py`; con 8, captura
  paralela.
- Hub USB alimentado: 8 nodos consumen ~2 A.
- Si merece la pena implementar el bloqueo de AGC ya planificado en `ADVANCED.md` (basado en
  la investigación de ESPectre). Estabilizaría las amplitudes y reduciría el trabajo de
  normalización en `WP-08`.
