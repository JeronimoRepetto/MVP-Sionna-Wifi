# Contrato — geometría de la escena

> Contrato compartido entre `MVP-Sionna-Wifi` (simulación) y `wifi-csi-capture`
> (hardware real). Si las dos escenas no son la misma, **cualquier comparación entre CSI
> real y simulado carece de sentido**.
>
> Estado: **el contrato está definido pero NO implementado.** Hoy los dos repos describen
> habitaciones distintas. Lo implementa [`WP-07`](../work-packages/WP-07-canonical-scene.md).

---

## 1. El problema

| Aspecto | `MVP-Sionna-Wifi` (`backend/config.py`) | `wifi-csi-capture` (`tools/measurement_protocol.py`, `tools/digital_twin_sionna.py`) |
|---|---|---|
| Descripción | Sala genérica | Escalera real |
| Ancho (X) | 2,0 m | 3,0 m |
| Profundidad (Y) | 3,5 m | 4,0 m |
| Altura (Z) | 2,0 m | 2,8 m |
| Grosor de pared | 0,12 m | no modelado |
| Tx | `[1.0, 3.62, 1.0]` — fuera, tras la pared trasera | `[1.5, 2.0, 1.5]` — centro, media altura |
| Rx altos | Z = 1,9 m, X = −0,12 / 2,12 (**fuera** de las paredes) | Z = 2,5 m, X = 0,0 / 3,0 |
| Rx bajos | Z = 0,1 m | Z = 0,15 m |
| Materiales | `itu_concrete` en las 6 superficies (ver D-08) | `drywall`, `concrete`, `wood`, `metal_railing`, `human_tissue` |
| Frecuencia | 2,437 GHz | 2,437 GHz ✅ |
| Ancho de banda | 40 MHz | 40 MHz ✅ |
| Subportadoras | 114 | 114 ✅ |

Lo único que ya coincide son los parámetros de RF. La geometría no coincide en nada.

**Consecuencia práctica**: un receptor llamado `ESP32_3` en la simulación y el nodo en
`pos03` del hardware están en sitios distintos, midiendo canales distintos. Compararlos
produciría un error de calibración que se atribuiría erróneamente a los materiales.

---

## 2. Decisión: la escalera real es la canónica

**Razón**: el simulador debe imitar la realidad, no al revés. Los datos se van a capturar
en la escalera; la geometría de esa escalera es la verdad. La sala 2,0 × 3,5 × 2,0 del MVP
fue un banco de pruebas para aprender Sionna, y ya cumplió su función.

**Acción previa requerida del usuario**: medir la escalera real. Las cifras actuales de
`measurement_protocol.py` son estimaciones — el propio fichero lo dice:

> `IMPORTANTE: Medir las dimensiones reales de tu escalera y actualizar las coordenadas en
> este archivo antes de capturar.`

Sin medidas reales, F4 (calibración) no puede dar resultados válidos.

---

## 3. Esquema de `scene.json`

Fuente de verdad única, consumida por ambos repos. Ubicación propuesta:
`docs/contracts/scene.json` en este repo, replicada o referenciada desde el otro.

```json
{
  "schema_version": "1.0",
  "name": "staircase",
  "description": "Escalera real, medida el <fecha> con <método>",
  "units": "meters",
  "coordinate_system": {
    "up_axis": "Z",
    "origin": "esquina frontal izquierda del suelo",
    "x": "ancho (izquierda → derecha)",
    "y": "profundidad (frente → fondo)",
    "z": "altura (suelo → techo)"
  },
  "room": {
    "width": 3.0,
    "depth": 4.0,
    "height": 2.8,
    "wall_thickness": 0.12
  },
  "rf": {
    "frequency_hz": 2.437e9,
    "bandwidth_hz": 40e6,
    "num_subcarriers": 114,
    "num_data_subcarriers": 108,
    "subcarrier_spacing_hz": 312500,
    "channel": 6,
    "standard": "802.11n HT40"
  },
  "materials": {
    "walls":   { "id": "itu_brick",    "thickness": 0.12 },
    "floor":   { "id": "itu_concrete", "thickness": 0.20 },
    "ceiling": { "id": "itu_concrete", "thickness": 0.20 },
    "human":   { "id": "itu_wet_ground" }
  },
  "transmitter": {
    "id": "router",
    "label": "Router 2.4 GHz dedicado",
    "position": [1.5, 2.0, 1.5],
    "orientation": [0.0, 0.0, 0.0],
    "antenna": { "pattern": "dipole", "polarization": "V", "gain_dbi": 2.0 },
    "power_dbm": 20
  },
  "receivers": [
    { "id": "ESP32_1", "position_id": 1, "position": [0.0, 0.0, 2.5],
      "zone": "ceiling", "label": "Techo frontal izquierda",
      "antenna": { "pattern": "dipole", "polarization": "V", "gain_dbi": 2.0 } }
  ]
}
```

### Reglas del esquema

| Regla | Motivo |
|---|---|
| `schema_version` obligatorio | Permite evolucionar el formato sin romper lectores |
| Todas las posiciones en el sistema **Z-up** de Mitsuba | Un único sistema en el contrato. Las conversiones a Y-up son responsabilidad de quien lee — ver [`../agent/CONVENTIONS.md §1`](../agent/CONVENTIONS.md) |
| `id` de receptor estable y **compartido** | `ESP32_1` en la simulación debe ser el mismo nodo físico que `position_id: 1` en la captura. Es la clave del join |
| `position_id` 1-8 | Lo que ya usan `measurement_protocol.py` y los nombres de fichero `pos01…pos08` |
| `materials[*].id` = identificadores ITU-R P.2040 | Los que Sionna reconoce nativamente: `itu_concrete`, `itu_brick`, `itu_wood`, `itu_metal`, `itu_wet_ground` |
| Unidades siempre metros y hercios | Sin prefijos ni ambigüedad |

---

## 4. Quién consume qué

```
docs/contracts/scene.json          ← fuente de verdad única
        │
        ├──► MVP-Sionna-Wifi/backend/config.py
        │       Lee el JSON y expone las constantes actuales.
        │       Mantiene los nombres existentes (ROOM_WIDTH, TRANSMITTER, RECEIVERS…)
        │       para no romper los 30+ sitios que los importan.
        │
        ├──► MVP-Sionna-Wifi/scenes/*.xml
        │       Generado a partir del JSON — ver WP-05 y WP-07
        │
        ├──► wifi-csi-capture/tools/measurement_protocol.py
        │       POSITIONS y ROUTER_POSITION derivan del JSON
        │
        └──► wifi-csi-capture/tools/digital_twin_sionna.py
                SCENE_CONFIG, ROUTER_TX y RECEIVERS derivan del JSON
                (este fichero además está roto por API 0.x — defecto D-24)
```

**Compatibilidad hacia atrás**: `config.py` debe seguir exponiendo `ROOM_WIDTH`,
`ROOM_DEPTH`, `ROOM_HEIGHT`, `TRANSMITTER`, `RECEIVERS`, etc. con los mismos nombres y
tipos. El cambio es de dónde salen los valores, no de la interfaz.

---

## 5. Cómo se mantienen sincronizados los dos repos

Los repos son independientes; no hay submódulo. Mecanismo propuesto, por orden de
preferencia:

1. **Fichero replicado con verificación de hash.** `scene.json` vive aquí (canónico) y se
   copia al otro repo. Un test en ambos lados compara el SHA-256 y falla si divergen. Es lo
   que menos fricción añade.
2. **Submódulo git** de un tercer repo solo con contratos. Más limpio, más ceremonia.
3. Copia manual. Deriva garantizada — descartado.

`WP-07` implementa la opción 1.

---

## 6. Criterios de aceptación de `WP-07`

```bash
# 1. El JSON valida contra su esquema
python scripts/validate_scene_contract.py
# Esperado: OK, schema_version 1.0, 1 Tx, 8 Rx

# 2. config.py deriva del JSON y no contradice nada
python -c "
import sys; sys.path.insert(0,'backend')
from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT, RECEIVERS, TRANSMITTER
import json; s = json.load(open('docs/contracts/scene.json'))
assert ROOM_WIDTH == s['room']['width']
assert ROOM_DEPTH == s['room']['depth']
assert ROOM_HEIGHT == s['room']['height']
assert len(RECEIVERS) == len(s['receivers'])
assert TRANSMITTER['position'] == s['transmitter']['position']
print('config.py coherente con el contrato')"

# 3. Los dos repos tienen el mismo contrato
python scripts/check_contract_sync.py --other ../wifi-csi-capture
# Esperado: SHA-256 idéntico

# 4. La suite sigue verde con la geometría nueva
python scripts/verify.py --level gpu
```

⚠️ Cambiar la geometría invalida `scenes/room_simple.xml`. `WP-07` depende de `WP-05`
(que resuelve cómo se genera y versiona la escena) — no lo hagas al revés o perderás la
escena actual, que no está en git (defecto D-05).
