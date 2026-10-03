export type EstadoFoto = 'pendiente' | 'procesando' | 'lista' | 'error'

export interface Foto {
  id: string
  nombre_original: string
  ruta_original: string
  ruta_procesada: string | null
  estado: EstadoFoto
  grupo: string | null
  created_at: string
  updated_at: string
}
