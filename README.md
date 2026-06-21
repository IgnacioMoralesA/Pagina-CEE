# CEE Conecta

Proyecto de CEE Conecta inicializado con una fabrica agentica SDD local,
deterministica, auditable y trazable.

Esta primera etapa no implementa el backend ni el frontend del producto. Solo
provee la fabrica minima que genera artefactos de especificacion y evidencia.

## Comandos iniciales

```bash
python -m factory.cli init-project --project project
python -m factory.cli run --project project --objective "Crear plataforma CEE Conecta"
python -m factory.cli verify --project project
pytest -q tests
```

## Estado

- Fabrica local en `factory/`.
- Artefactos por ejecucion en `project/runs/RUN-.../`.
- Producto reservado en `app/` para etapas posteriores.

