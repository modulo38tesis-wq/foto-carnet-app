# Foto Carnet App

Aplicación web completa para procesar fotos tipo carnet (fondo blanco + centrado de cabeza + conversión a **WebP**).

## Stack 100% gratis

- **Frontend**: Next.js en Vercel
- **Backend / Storage / Auth**: Supabase
- **Worker de procesamiento**: Python en Render
- **Código**: GitHub

## Estructura

```
foto-carnet-app/
├── worker/               # Procesamiento de fotos (Render)
│   ├── app.py
│   ├── procesar_fotos.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── deploy.prototxt.txt
│   └── res10_300x300_ssd_iter_140000.caffemodel
├── frontend/             # Página web (Vercel) - próximamente
└── README.md
```

## Estado actual

- [x] Script de procesamiento con WebP
- [x] Estructura base del worker
- [ ] Conexión con Supabase
- [ ] Frontend
- [ ] Deploy en Render + Vercel
