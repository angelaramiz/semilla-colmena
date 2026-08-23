# 🌱 Semillero del Árbol Conservante

> **Acceso exclusivo del CONSERVANTE** (jerarquía más alta, dev/arquitecto).

Este `semillero/` guarda las **semillas de despliegue** de la colmena, listas para sembrar
en las máquinas remotas. El conservante las usa para producir los otros árboles:

```
semillero/
├── obreros/        ← semilla para ÁRBOLES HIJO (obreros, 24/7)
└── comandante/     ← semilla para el ÁRBOL COMANDANTE (directora de mercadotecnia)
```

Cada semilla contiene:
- `sembrar_<rol>.md` → guía exacta de pasos para esa máquina.
- `plantilla.env` → plantilla de entorno lista para copiar y rellenar.

> ⚠️ El conservante NO comparte el semillero con comandante/obreros: solo él produce y
> autoriza. Cada semilla que sale de aquí se siembra con `sembrar.sh` en la máquina destino.