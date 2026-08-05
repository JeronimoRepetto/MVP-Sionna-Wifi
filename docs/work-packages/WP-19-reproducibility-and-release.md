# WP-19 — Reproducibilidad, CI y publicación

| | |
|---|---|
| **Fase** | F7 · Validación y publicación |
| **Estado** | `ESBOZO` — se detalla al activar F7 |
| **Defectos que cierra** | D-19 (definitivamente), D-36 |
| **Depende de** | Todas las fases anteriores |
| **Nivel de verificación** | `mock` (CI) + `gpu` (local) |
| **Requiere intervención del usuario** | **sí — decisiones de licencia y publicación** |

## Objetivo

Que una persona ajena al proyecto pueda clonar, seguir `AGENTS.md` y reproducir los
resultados sin preguntar nada.

## Alcance

### Integración continua

GitHub Actions limitado a `--level mock`: los runners no tienen GPU ni pueden instalar Sionna
de forma razonable. Cubre config, biblioteca de poses, formato de datos, contratos y el build
del frontend. Los niveles `sionna` y `gpu` siguen siendo responsabilidad local, antes del PR.

Añadir también la comprobación de sincronización de contratos entre repos
(`scripts/check_contract_sync.py` de `WP-07`).

### Licencias — resolver definitivamente

| Asunto | Estado |
|---|---|
| Modelos SMPL `.pkl` | Correctamente excluidos. Documentado en el README |
| `frontend/public/human.obj` (D-19) | **Malla derivada de SMPL, versionada.** Debe resolverse **antes** de publicar, idealmente ya en `WP-06` |
| Dataset real | ¿Se publica? Contiene mediciones RF de personas en un domicilio. Hay consideraciones de privacidad, no solo de licencia |
| Dataset sintético | Derivado de SMPL. Su redistribución probablemente esté sujeta a la misma licencia |
| Modelo entrenado | Si se entrenó con datos derivados de SMPL, revisar qué implica |

La cadena SMPL toca el dataset sintético y el modelo entrenado, no solo la malla. Conviene
aclararla pronto: descubrirlo al final obligaría a rehacer trabajo.

### Model card

Datos de entrenamiento, particiones, métricas por partición, limitaciones conocidas, sesgos
(¿cuántos sujetos? ¿de qué morfologías?), y usos que **no** son apropiados. Un sistema que
detecta personas a través de paredes tiene implicaciones de privacidad que merecen decirse
explícitamente.

### Documentación final

- Sincronizar `README.md`, `HOW_IT_WORKS.md` e `INSTALL_WSL2_GPU.md` con el estado final.
- Verificar que `AGENTS.md` sigue siendo suficiente como único punto de entrada.
- Cerrar D-36 (bundle de 526 kB en un chunk) si se publica una demo web.

## Puerta de salida

```bash
# Reproducibilidad desde cero, en una máquina limpia
git clone <repo> && cd MVP-Sionna-Wifi
# Seguir AGENTS.md al pie de la letra, sin ayuda externa
python scripts/verify.py --level gpu
# Esperado: verde, sin necesidad de preguntar nada a nadie
```

```bash
# CI verde en cada PR
# Esperado: --level mock pasa en GitHub Actions
```

- [ ] Auditoría de licencias completa y documentada
- [ ] Model card publicada
- [ ] Un tercero reproduce el `verify --level gpu` sin asistencia

## Pendiente de detallar

- Qué se publica y qué no.
- Licencia del dataset, si se publica.
- Si el proyecto se une en un monorepo o los dos repos siguen separados.
- Si hay artículo o publicación asociada, y qué exige de reproducibilidad.
