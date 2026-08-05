# WP-05 — Reproducibilidad de la escena

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-05, D-07, D-08 |
| **Invariantes que pone en verde** | INV-09 (deja de hacer skip por falta de escena) |
| **Depende de** | — (paralelizable con WP-01…WP-04) |
| **Nivel de verificación** | `sionna` |
| **Requiere intervención del usuario** | **sí — decisión sobre `generate_room.py`** |

## Objetivo

Que un clon limpio del repositorio pueda simular. Hoy `scenes/room_simple.xml` está
gitignorado: quien clone no tiene escena, `rt.load_scene()` lanza, y el backend queda en
**modo mock permanente**. El proyecto no es reproducible por nadie más.

Y de paso resolver la trampa asociada: `blender/generate_room.py` escribe en esa misma ruta y
produciría una escena distinta, así que ejecutarlo destruye la única copia de la buena.

## Contexto

```
$ cat .gitignore | sed -n '45,48p'
# Generated data
scenes/*.xml
!scenes/.gitkeep

$ git ls-files scenes/
scenes/.gitkeep          ← solo esto

$ ls scenes/             # en la copia de trabajo del usuario
.gitkeep  room_simple.xml
```

**El XML está escrito a mano.** 79 líneas con 6 `<shape type="rectangle">` y comentarios
redactados por una persona, del tipo:

```xml
<!-- Rectangle is in XY. First scale so X is 1.0, Y is 1.75 -->
<!-- We want normal +Z to become +X. Rotate around Y by 90 -->
```

No lo generó Blender. `generate_room.py` produciría mallas exportadas por `mitsuba-blender`,
no primitivas `rectangle`. **El pipeline «Blender → Mitsuba → Sionna» que anuncia el README
nunca se ha usado.**

Y los materiales no coinciden con lo documentado (D-08):

| Fuente | Paredes |
|---|---|
| `README.md` | `itu_brick` |
| `backend/config.py::MATERIALS` | `itu_brick` |
| `scenes/room_simple.xml` — **lo usado** | `itu_concrete` en las 6 superficies |
| `blender/generate_room.py` | `itu_concrete` (crea `mat_itu_brick` y nunca lo asigna) |

Log de arranque real: `Material 'itu_concrete': thickness=0.12m` — un solo material.

## Decisión requerida del usuario

Antes de implementar, decide qué hacer con `blender/generate_room.py`:

| Opción | Implicación |
|---|---|
| **A · Retirarlo** | Moverlo a `blender/experimental/` con un README que explique que no genera la escena en uso. Menos código que mantener. **Recomendada** si la escena canónica va a venir de `scene.json` (`WP-07`) |
| **B · Hacerlo real** | Que genere de verdad el XML en uso, con `itu_brick` en las paredes, y usarlo como única fuente. Requiere el addon `mitsuba-blender` y validar que la escena resultante da resultados equivalentes |
| **C · Dejarlo y protegerlo** | Cambiar `OUTPUT_XML` a `scenes/generated/room_from_blender.xml` para que nunca sobrescriba la escena en uso, y documentar que es un experimento |

La opción **C** es el mínimo imprescindible: elimina el riesgo de destrucción con un cambio
de una línea. **A** o **B** requieren tu criterio.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `.gitignore` | `!scenes/room_simple.xml` para versionar la escena canónica |
| `scenes/room_simple.xml` | Se añade a git. Cabecera de comentario explicando su origen, autoría manual y que es la escena canónica |
| `scenes/README.md` | **Nuevo**. Qué es cada escena, cómo se genera, qué no tocar |
| `blender/generate_room.py` | Según la decisión A/B/C |
| `README.md` | Corregir la tabla de materiales (D-08) y la afirmación sobre el pipeline de Blender |
| `docs/HOW_IT_WORKS.md` | Corregir la afirmación sobre grosor de «brick, concrete, wood» |
| `docs/DEFECTS.md` | D-05, D-07, D-08 → `CERRADO` |

## Pasos

1. **Copia de seguridad primero.** El fichero no está en git; si algo va mal no hay vuelta
   atrás:

   ```bash
   cp scenes/room_simple.xml scenes/room_simple.xml.bak
   ```

2. Cambiar `.gitignore`:

   ```gitignore
   # Generated data
   scenes/*.xml
   !scenes/.gitkeep
   !scenes/room_simple.xml     # escena canónica, escrita a mano — ver scenes/README.md
   ```

   Se mantiene la exclusión general para escenas generadas, y se exceptúa la canónica.

3. Añadir una cabecera al XML documentando su naturaleza:

   ```xml
   <!--
     Escena canónica de MVP-Sionna-Wifi — ESCRITA A MANO, no generada por Blender.
     Sala 2,0 x 3,5 x 2,0 m modelada con 6 primitivas 'rectangle' (single-sheet).
     El grosor físico lo aplica backend/scene_loader.py vía WALL_THICKNESS.
     NO regenerar con blender/generate_room.py: produciría una escena distinta.
     Ver scenes/README.md y docs/work-packages/WP-05-scene-reproducibility.md
   -->
   ```

4. **Resolver D-08** — hacer coincidir documentación y realidad. Dos caminos:
   - **Alinear la doc con el código** (menos riesgo): corregir el README para que diga
     `itu_concrete` en las 6 superficies. La física no cambia.
   - **Alinear el código con la doc**: asignar `itu_brick` a las 4 paredes en el XML. **Esto
     cambia los resultados de la simulación** (ladrillo y hormigón tienen permitividades
     distintas), así que hay que reejecutar las verificaciones y anotar el nuevo baseline.

   > Recomendación: alinear la doc ahora, y decidir el material real en `WP-07` cuando se
   > modele la escalera de verdad. Los materiales de la sala de pruebas van a desaparecer.

   En cualquier caso, `config.py::MATERIALS` debe reflejar la verdad — hoy dice `itu_brick` y
   además nunca se aplica a la escena real.

5. Aplicar la decisión A/B/C sobre `generate_room.py`. Si es C, basta:

   ```python
   OUTPUT_XML = os.path.join(..., 'scenes', 'generated', 'room_from_blender.xml')
   ```

6. Escribir `scenes/README.md`: inventario de escenas, origen de cada una, cuál es la
   canónica, cómo se regenera (o que no se regenera), y el aviso de `generate_room.py`.

7. Verificar que un clon limpio funciona (criterio de aceptación 1).

## Criterios de aceptación

```bash
# 1. Un clon limpio simula con Sionna real, no en modo mock
cd /tmp && rm -rf clone-test && git clone <ruta-del-repo> clone-test && cd clone-test
python -c "
import sys; sys.path.insert(0,'backend')
from scene_loader import load_scene, get_scene_info
s = load_scene()
info = get_scene_info(s)
assert info['sionna_active'], 'sigue en modo mock'
assert info['backend'] != 'mock'
print('clon limpio OK, backend:', info['backend'], '| objetos:', len(s.objects))"
# Esperado: sionna_active True, 6 objetos
```

```bash
# 2. La escena está versionada
git ls-files scenes/
# Esperado: scenes/.gitkeep y scenes/room_simple.xml
```

```bash
# 3. Los materiales documentados coinciden con los usados
python -c "
import sys, re; sys.path.insert(0,'backend')
xml = open('scenes/room_simple.xml').read()
used = set(re.findall(r'<ref id=\"(itu_\w+)\"', xml))
from config import MATERIALS
declared = set(MATERIALS.values())
assert used == declared, f'usados={used} declarados={declared}'
print('materiales coherentes:', used)"
```

```bash
# 4. generate_room.py no puede destruir la escena canónica
grep -n "OUTPUT_XML" blender/generate_room.py
# Esperado: NO apunta a scenes/room_simple.xml (o el fichero se ha movido a experimental/)
```

```bash
# 5. La suite sigue verde
python scripts/verify.py --level sionna
```

- [ ] Los cinco criterios pasan
- [ ] `scenes/README.md` escrito
- [ ] `README.md` y `HOW_IT_WORKS.md` corregidos
- [ ] D-05, D-07, D-08 marcados `CERRADO`
- [ ] `scenes/room_simple.xml.bak` eliminado tras confirmar que todo va bien

## Fuera de alcance

- Modelar la escalera real y unificar geometrías → `WP-07`.
- La licencia de `frontend/public/human.obj` → `WP-06` (es un problema distinto, aunque
  también sea un artefacto versionado que no debería estarlo).
- Cambiar el grosor o las propiedades de los materiales por criterio físico → `WP-13`
  (calibración).

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Perder `room_simple.xml` durante los cambios | Paso 1: copia de seguridad **antes de tocar nada**. No es opcional: el fichero no está en git |
| Cambiar a `itu_brick` altera todos los resultados | Por eso se recomienda alinear la doc, no el código. Si aun así se cambia, reejecutar `diag_compare.py` y anotar el nuevo baseline |
| Versionar el XML choca con `WP-07`, que lo generará desde `scene.json` | No hay conflicto: `WP-07` lo regenerará y seguirá versionado. Tener la escena en git es requisito previo, no obstáculo |
| Alguien ejecuta `generate_room.py` antes de aplicar este paquete | Riesgo real **hoy**. Es la regla R2 de `AGENTS.md`. Si te toca este paquete, empieza por el paso 5 |
