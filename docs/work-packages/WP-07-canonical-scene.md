# WP-07 — Geometría canónica compartida

| | |
|---|---|
| **Fase** | F2 · El puente |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-24 (parcial) |
| **Invariantes que pone en verde** | — |
| **Depende de** | `WP-05` (la escena debe estar versionada antes de regenerarla) |
| **Nivel de verificación** | `sionna` |
| **Requiere intervención del usuario** | **sí — medir la escalera real y elegir la escena canónica** |

## Objetivo

Que los dos repositorios describan **la misma habitación**. Hoy `MVP-Sionna-Wifi` simula una
sala de 2,0 × 3,5 × 2,0 m y `wifi-csi-capture` mide una escalera de 3,0 × 4,0 × 2,8 m, con
transmisor y receptores en posiciones distintas. Cualquier comparación entre CSI real y
simulado es inválida mientras eso siga así — y esa comparación es todo el propósito de F4.

## Contexto

**Lectura obligatoria**:
[`../contracts/SCENE_GEOMETRY.md`](../contracts/SCENE_GEOMETRY.md), que ya define el esquema
de `scene.json` y las reglas.

Divergencia actual:

| Aspecto | MVP | wifi-csi-capture |
|---|---|---|
| Dimensiones | 2,0 × 3,5 × 2,0 m | 3,0 × 4,0 × 2,8 m |
| Tx | `[1.0, 3.62, 1.0]`, fuera de la pared trasera | `[1.5, 2.0, 1.5]`, centro |
| Rx altos | Z = 1,9 m, **fuera** de las paredes | Z = 2,5 m |
| Rx bajos | Z = 0,1 m | Z = 0,15 m |

Las cifras del lado hardware son **estimaciones**. El propio
`tools/measurement_protocol.py` lo advierte:

> `IMPORTANTE: Medir las dimensiones reales de tu escalera y actualizar las coordenadas en
> este archivo antes de capturar.`

## Decisión requerida del usuario

1. **¿Qué escena es la canónica?** Recomendación: la escalera real. El simulador debe imitar
   la realidad, no al revés; los datos se van a capturar allí. La sala 2,0 × 3,5 × 2,0 fue un
   banco de pruebas para aprender Sionna y ya cumplió.
2. **Medir la escalera.** Ancho, profundidad, altura, grosor de paredes, materiales reales
   (¿tabique de yeso? ¿ladrillo? ¿hormigón?), y las 8 posiciones donde irán los nodos más la
   del router. Sin medidas reales, F4 no puede dar resultados válidos: estarías atribuyendo a
   los materiales un error que en realidad es geométrico.
3. **Mecanismo de sincronización entre repos**: la opción 1 de
   `SCENE_GEOMETRY.md §5` (fichero replicado con verificación de hash) es la recomendada.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `docs/contracts/scene.json` | **Nuevo**. Fuente de verdad única |
| `docs/contracts/scene.schema.json` | **Nuevo**. Esquema JSON para validación |
| `backend/config.py` | Deriva los valores de `scene.json`, **manteniendo los nombres actuales** (`ROOM_WIDTH`, `TRANSMITTER`, `RECEIVERS`…) |
| `scripts/generate_scene_xml.py` | **Nuevo**. `scene.json` → Mitsuba XML |
| `scripts/validate_scene_contract.py` | **Nuevo**. Valida el JSON contra el esquema |
| `scripts/check_contract_sync.py` | **Nuevo**. Compara el SHA-256 con el del otro repo |
| `scenes/staircase.xml` | **Nuevo**, generado. Reemplaza a `room_simple.xml` como escena por defecto |
| `../wifi-csi-capture/tools/measurement_protocol.py` | `POSITIONS` y `ROUTER_POSITION` derivan del JSON |
| `../wifi-csi-capture/tools/digital_twin_sionna.py` | `SCENE_CONFIG`, `ROUTER_TX`, `RECEIVERS` derivan del JSON. Y **portar a la API de Sionna 1.x** (D-24) |

**NO tocar**: `scenes/room_simple.xml`. Se conserva como escena histórica de pruebas y sigue
sirviendo para tests rápidos.

## Pasos

1. Medir la escalera (usuario) y rellenar `scene.json` según el esquema de
   `SCENE_GEOMETRY.md §3`.
2. Escribir `scene.schema.json` y `scripts/validate_scene_contract.py`.
3. Refactorizar `config.py` para que lea el JSON y exponga las **mismas** constantes con los
   mismos tipos. Más de 30 sitios las importan; la interfaz no debe cambiar.
4. Escribir `scripts/generate_scene_xml.py` con el mismo enfoque *single-sheet* que el XML
   actual (primitivas `rectangle`, grosor aplicado por material). Reutilizar el XML escrito
   a mano como plantilla de referencia: funciona y está validado.
5. Generar `scenes/staircase.xml` y verificarlo cargándolo con Sionna.
6. Replicar `scene.json` en `wifi-csi-capture` y adaptar sus dos ficheros.
7. Portar `digital_twin_sionna.py` a Sionna 1.x, o —mejor— **borrar su lógica de simulación**
   y que importe el backend del MVP, que ya tiene el cargador correcto. Duplicar el motor de
   simulación en dos repos es cómo nació D-24.
8. Escribir `scripts/check_contract_sync.py` y añadir su comprobación a `verify.py`.

## Criterios de aceptación

Los cuatro criterios están detallados en
[`../contracts/SCENE_GEOMETRY.md §6`](../contracts/SCENE_GEOMETRY.md). Resumen:

```bash
python scripts/validate_scene_contract.py          # JSON válido, 1 Tx, 8 Rx
python scripts/check_contract_sync.py --other ../wifi-csi-capture   # SHA-256 idéntico
python scripts/verify.py --level gpu               # suite verde con la geometría nueva
```

Más:

```bash
# La escena generada carga en Sionna con la geometría esperada
python -c "
import sys, json; sys.path.insert(0,'backend')
from scene_loader import load_scene
s = json.load(open('docs/contracts/scene.json'))
sc = load_scene(scene_path='scenes/staircase.xml')
print('objetos:', len(sc.objects), '| Rx esperados:', len(s['receivers']))
assert len(sc.objects) >= 6"
```

```bash
# wifi-csi-capture usa las mismas posiciones
cd ../wifi-csi-capture && python -c "
import json, sys; sys.path.insert(0,'tools')
from measurement_protocol import POSITIONS, ROUTER_POSITION
s = json.load(open('docs/contracts/scene.json'))
for r in s['receivers']:
    p = POSITIONS[r['position_id']]
    assert [p['x'],p['y'],p['z']] == r['position'], r['id']
assert [ROUTER_POSITION['x'],ROUTER_POSITION['y'],ROUTER_POSITION['z']] == s['transmitter']['position']
print('posiciones sincronizadas')"
```

- [ ] Todos los criterios pasan
- [ ] `SCENE_GEOMETRY.md` actualizado: quitar la sección «el problema», documentar el estado
      final
- [ ] `README.md` actualizado con la geometría nueva
- [ ] D-24 marcado `CERRADO` (junto con `WP-08`)

## Fuera de alcance

- Normalizar los tensores de CSI → `WP-08`.
- Calibrar los materiales contra medidas → `WP-13`.
- Modelar los escalones individualmente. Empezar con una caja simple; añadir detalle solo si
  la calibración de F4 lo justifica.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Cambiar la geometría invalida todos los resultados anteriores | Es inevitable y correcto. Conservar `room_simple.xml` para tests rápidos y regresión |
| `config.py` leyendo un JSON añade un fallo posible en el arranque | Validar al importar y lanzar un error claro y accionable, no un `KeyError` opaco |
| Los dos repos derivan de todos modos | La comprobación de hash en `verify.py` lo detecta al instante |
| Medidas imprecisas de la escalera | Documentar el método y el error estimado en `scene.json`. Un error de 5 cm a 12,3 cm de longitud de onda es media longitud de onda: importa |
| El detalle geométrico de la escalera desborda el modelo simple | Empezar simple. F4 dirá si hace falta más detalle |
