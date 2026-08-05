# WP-NN — <título en una línea>

| | |
|---|---|
| **Fase** | F<n> · <nombre de la fase> |
| **Estado** | `PENDIENTE` / `EN CURSO` / `HECHO` / `BLOQUEADO` |
| **Defectos que cierra** | D-NN, D-NN |
| **Invariantes que pone en verde** | INV-NN, INV-NN |
| **Depende de** | WP-NN (o `—`) |
| **Nivel de verificación** | `mock` / `sionna` / `gpu` / `hardware` |
| **Requiere intervención del usuario** | sí / no (`sudo`, admin, hardware, decisión) |

## Objetivo

Un párrafo. Qué cambia y por qué importa. Si no puedes explicarlo en un párrafo, el paquete
es demasiado grande: pártelo.

## Contexto

Por qué existe este trabajo, con enlaces a los documentos que hay que leer **antes** de
empezar. Incluye la evidencia medida si la hay (números, salidas de comandos, no
descripciones vagas).

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `ruta/exacta.py` | descripción concreta |

**NO tocar**: lista explícita de lo que queda fuera, sobre todo si está cerca.

## Pasos

1. Accionable y verificable.
2. …

## Criterios de aceptación

Cada criterio es un **comando** con su **salida esperada**. Sin comando no es un criterio,
es un deseo.

```bash
<comando>
# Esperado: <salida concreta>
```

- [ ] …

## Fuera de alcance

Lo que alguien podría pensar que entra y no entra, y a qué paquete pertenece.

## Riesgos y trampas

Lo que se puede romper sin darse cuenta. Errores que ya se han cometido en esta zona del
código.

---

## Instrucciones para el redactor de fichas

- Los criterios de aceptación se escriben **antes** de implementar. Si no sabes cómo
  verificarlo, todavía no entiendes el problema.
- Referencia defectos por ID (`D-NN`), nunca por descripción: las descripciones derivan.
- Enlaza a `docs/agent/*` en lugar de repetir su contenido. Documentación duplicada se
  desincroniza.
- Si el paquete requiere `sudo`, admin, hardware o una decisión del usuario, márcalo en la
  cabecera. Un agente no debe ejecutarlo por su cuenta.
- Un paquete debería cerrarse en una sesión de trabajo. Si no cabe, pártelo.
