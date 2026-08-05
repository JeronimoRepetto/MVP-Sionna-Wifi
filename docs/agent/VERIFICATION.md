# Verificación

> Cómo comprobar que el proyecto está sano, en cuatro niveles según lo que tengas
> disponible. Un cambio no está hecho hasta que el nivel que exige su paquete de trabajo
> sale verde.

---

## 1. Los cuatro niveles

| Nivel | Requiere | Qué cubre | Duración |
|---|---|---|---|
| `mock` | Nada. Sirve el Python de Windows | Lógica pura: config, poses, formato de datos, build del frontend | ~30 s |
| `sionna` | conda env `sionna` en WSL2 | Todo lo anterior + motor real de ray tracing en CPU | ~2 min |
| `gpu` | + las 3 variables de entorno | Todo lo anterior en CUDA/OptiX + comparación GPU/CPU | ~1 min |
| `hardware` | ESP32-S3 + router dedicado | Captura real de CSI | manual |

Los niveles son acumulativos: `gpu` ejecuta también lo de `sionna` y `mock`.

```bash
python scripts/verify.py --level mock
python scripts/verify.py --level sionna
python scripts/verify.py --level gpu
python scripts/verify.py --level hardware
```

---

## 2. Qué esperar de cada nivel

### `--level mock`

Único nivel que funciona desde Windows sin WSL. Fuerza `PYTHONUTF8=1`, así que no verás el
`UnicodeEncodeError` de los emojis.

```
[WARN ] env_check                        * modo mock / no disponible
[PASS ] pytest -m "mock"                   N passed
[PASS ] build del frontend               * 15 modulos
```

`*` marca los pasos **informativos**: se reportan pero no bloquean. En el nivel `mock`,
`env_check` es informativo porque la ausencia de Sionna es esperada.

La `suite legada` (`tests/run_all.py`, el runner anterior a pytest) solo se ejecuta en los
niveles `sionna` y superiores. Falla 3 tests conocidos (registrados como D-06) y aparece
como `WARN` informativo. Desaparece cuando WP-04 la absorba.

### `--level sionna`

```
[PASS ] env_check                          CPU (LLVM) - ~5x mas lento
[XFAIL] pytest -m "mock or sionna"         2 passed, 0 failed, 9 xfailed, 0 xpassed, 2 skipped
[PASS ] build del frontend               * 15 modulos
[WARN ] suite legada (informativa)       * 4 suites passed, 2 failed  (esperado: D-06)
```

**Los 9 `xfailed` son correctos y esperados hoy.** Cada uno corresponde a un defecto P0
abierto — la tabla completa está en
[`PHYSICS_INVARIANTS.md`](PHYSICS_INVARIANTS.md).

⚠️ **Cero `xpass`.** Un `xpass` significa que un invariante roto pasó a funcionar: has
arreglado algo y hay que quitar la marca `xfail`. La suite está configurada con
`strict=True` precisamente para que esto **rompa el build** y no pase desapercibido.

### `--level gpu`

Idéntico a `sionna`, pero `env_check` debe reportar GPU — y en este nivel **es bloqueante**:

```
[PASS ] env_check                          GPU (CUDA + OptiX)
```

Si dice `llvm_…` estando en el nivel `gpu`, las variables de entorno no están aplicadas.
Lanza a través de `scripts/run_backend.sh` o exporta las tres variables — ver
[`ENVIRONMENT.md §3`](ENVIRONMENT.md).

### `--level hardware`

Requiere `wifi-csi-capture` operativo. Hoy bloqueado por el fallo de ESP-IDF (D-27). Los
pasos están en `WP-09`.

---

## 3. Diagnóstico del entorno por separado

```bash
python scripts/env_check.py
```

Imprime una tabla verde/roja y **explica la causa** cuando algo falla. No se limita a decir
«CPU»: distingue entre falta de variables de entorno, driver nativo secuestrando
`libcuda.so`, y ausencia real de GPU. Sale con código ≠ 0 si falta algo crítico.

Si su salida no te dice qué hacer a continuación, el script tiene un bug — arréglalo, es
parte del harness.

---

## 4. Comprobar la GPU sin arrancar el servidor

```bash
bash scripts/run_backend.sh --check-only
```

Carga la escena con las variables correctas, imprime el variant activo y sale. Es la forma
más rápida de confirmar que la GPU está viva en un shell no interactivo.

---

## 5. Comparación con/sin humano

```bash
python tests/diag_compare.py
```

Corre dos simulaciones completas —una con la malla SMPL inyectada, otra sin ella— y compara
CIR, CSI y mapa de cobertura receptor a receptor. Es la comprobación de más alto nivel de
que la cadena entera funciona: SMPL → OBJ → inyección en XML → ray tracing → resultados.

Requiere `backend/models/smpl/*.pkl`. Su lógica es la base de INV-09.

---

## 6. Frontend

```bash
cd frontend && node ./node_modules/vite/bin/vite.js build --outDir /tmp/vitedist
```

Esperado: `✓ 15 modules transformed`, bundle de ~526 kB.

> Usa el binario local, no `npx`: el perfil de PowerShell redirige `npx` a `pnpm dlx` y la
> invocación falla. Ver [`ENVIRONMENT.md §8`](ENVIRONMENT.md).

Comprobación visual (no automatizable): arrancar backend + `npm run dev`, abrir
`http://localhost:5173` y confirmar el badge `🟢 Sionna RT: Active` y que el heatmap
muestra `🟢 Sionna RT` en lugar de `🟡 Mock Data`.

---

## 7. Qué hacer cuando algo sale rojo

| Salida | Significado | Acción |
|---|---|---|
| `FAIL` en `env_check` | Falta una dependencia o la GPU no arranca (bloqueante en `sionna`/`gpu`) | Lee la causa que imprime, luego [`ENVIRONMENT.md §9`](ENVIRONMENT.md) |
| `failed` en pytest | Regresión real | Tu cambio rompió un invariante. No lo marques `xfail`: arréglalo |
| `xpassed` en pytest | **Arreglaste algo** | Quita la marca `xfail` y cierra el defecto en [`../DEFECTS.md`](../DEFECTS.md) |
| `XFAIL` en la fila de pytest | Hay defectos P0 abiertos | Normal hoy. El recuento debe coincidir con [`PHYSICS_INVARIANTS.md`](PHYSICS_INVARIANTS.md) |
| `skipped` inesperado | Falta un recurso | Lee el motivo del skip; suele ser la escena (D-05) o los modelos SMPL |
| `FAIL` en frontend build | Error de sintaxis o import | La salida de Vite indica fichero y línea |
| `WARN` en suite legada | Los 3 fallos conocidos de D-06 | Normal hasta WP-04. Si el recuento cambia, investiga |

**Regla**: nunca convertir un `failed` en `xfail` para poner la suite verde. Un `xfail`
solo es legítimo si existe un defecto registrado en `DEFECTS.md` que lo explique y un
paquete de trabajo que lo vaya a cerrar.

---

## 8. Integración continua

CI (cuando exista, WP-19) se limita a `--level mock`: los runners de GitHub Actions no
tienen GPU ni pueden instalar Sionna de forma razonable. Los niveles `sionna` y `gpu` son
responsabilidad de quien desarrolla, en local, antes de abrir el PR.

---

## 9. Antes de abrir un PR

- [ ] `python scripts/verify.py --level gpu` verde
- [ ] Cero `xpass`
- [ ] `git status --short` sin ficheros prohibidos (ver [`CONVENTIONS.md §6`](CONVENTIONS.md))
- [ ] Defectos afectados actualizados en [`../DEFECTS.md`](../DEFECTS.md)
- [ ] Documentación afectada actualizada
- [ ] Si tocaste física: comprobación visual en el navegador, no solo tests
