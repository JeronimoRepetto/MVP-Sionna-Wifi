# CLAUDE.md

Las instrucciones de este repositorio están en **[`AGENTS.md`](AGENTS.md)**. Léelo
completo antes de tocar nada.

Atajo a lo que más se olvida:

- Antes de modificar `backend/simulation.py` o `backend/scene_loader.py`, lee
  [`docs/agent/SIONNA_API_CONTRACT.md`](docs/agent/SIONNA_API_CONTRACT.md).
- El backend se arranca con `bash scripts/run_backend.sh`, nunca con
  `python backend/main.py` (si no, Sionna cae a CPU en silencio).
- Verificación: `python scripts/verify.py --level sionna`.
- Nunca toques `backend/models/smpl/` (licencia MPI-IS) ni ejecutes
  `blender/generate_room.py` sin leer WP-05.
