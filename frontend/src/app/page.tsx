'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { Foto } from '@/lib/types'
import { Upload, Download, RefreshCw, Image as ImageIcon, CheckCircle, Clock, AlertCircle, Loader2, Zap } from 'lucide-react'
import { v4 as uuidv4 } from 'uuid'

const WORKER_URL = 'https://foto-carnet-app.onrender.com/process'
const SEGUNDOS_POR_FOTO = 20

export default function Home() {
  const [fotos, setFotos] = useState<Foto[]>([])
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [grupo, setGrupo] = useState('')
  const [procesandoAuto, setProcesandoAuto] = useState(false)
  const [ultimoProceso, setUltimoProceso] = useState<string | null>(null)
  const [segundosRestantes, setSegundosRestantes] = useState(0)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const countdownRef = useRef<NodeJS.Timeout | null>(null)

  const pendientes = fotos.filter(f => f.estado === 'pendiente' || f.estado === 'procesando').length
  const listas = fotos.filter(f => f.estado === 'lista').length
  const errores = fotos.filter(f => f.estado === 'error').length

  const formatTiempo = (segundos: number) => {
    if (segundos <= 0) return '0s'
    const m = Math.floor(segundos / 60)
    const s = segundos % 60
    return m > 0 ? `${m}m ${s.toString().padStart(2, '0')}s` : `${s}s`
  }

  const cargarFotos = useCallback(async () => {
    const { data, error } = await supabase
      .from('fotos')
      .select('*')
      .order('created_at', { ascending: false })

    if (!error && data) {
      setFotos(data as Foto[])
    }
    setLoading(false)
  }, [])

  const dispararProceso = useCallback(async () => {
    try {
      setProcesandoAuto(true)
      const res = await fetch(WORKER_URL, { method: 'GET' })
      const data = await res.json()
      setUltimoProceso(new Date().toLocaleTimeString())
      console.log('Worker:', data)
      await cargarFotos()
    } catch (err) {
      console.error('Error worker:', err)
    } finally {
      setProcesandoAuto(false)
    }
  }, [cargarFotos])

  // Cargar fotos al inicio y refrescar cada 8s
  useEffect(() => {
    cargarFotos()
    const refresh = setInterval(cargarFotos, 8000)
    return () => clearInterval(refresh)
  }, [cargarFotos])

  // Cuenta regresiva en tiempo real
  useEffect(() => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current)
      countdownRef.current = null
    }

    if (pendientes > 0) {
      // Inicializar con el estimado
      setSegundosRestantes(pendientes * SEGUNDOS_POR_FOTO)

      countdownRef.current = setInterval(() => {
        setSegundosRestantes(prev => (prev > 0 ? prev - 1 : 0))
      }, 1000)
    } else {
      setSegundosRestantes(0)
    }

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [pendientes])

  // Auto-llamar al worker cada 30 segundos si hay pendientes
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    if (pendientes > 0) {
      dispararProceso()
      intervalRef.current = setInterval(dispararProceso, 30000)
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [pendientes, dispararProceso])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)

    for (const file of Array.from(files)) {
      try {
        const ext = file.name.split('.').pop()
        const fileName = `${uuidv4()}.${ext}`
        const path = grupo ? `${grupo}/${fileName}` : fileName

        const { error: uploadError } = await supabase.storage
          .from('originales')
          .upload(path, file)

        if (uploadError) throw uploadError

        const { error: dbError } = await supabase.from('fotos').insert({
          nombre_original: file.name,
          ruta_original: path,
          estado: 'pendiente',
          grupo: grupo || null,
        })

        if (dbError) throw dbError
      } catch (err) {
        console.error('Error subiendo', file.name, err)
      }
    }

    setUploading(false)
    e.target.value = ''
    await cargarFotos()
  }

  const getEstadoIcon = (estado: string) => {
    switch (estado) {
      case 'lista':
        return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'procesando':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-400" />
      default:
        return <Clock className="w-5 h-5 text-yellow-400" />
    }
  }

  const getEstadoText = (estado: string) => {
    switch (estado) {
      case 'lista': return 'Lista'
      case 'procesando': return 'Procesando...'
      case 'error': return 'Error'
      default: return 'Pendiente'
    }
  }

  const getPublicUrl = (path: string | null) => {
    if (!path) return null
    const { data } = supabase.storage.from('procesadas').getPublicUrl(path)
    return data.publicUrl
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-indigo-950">
      <div className="max-w-5xl mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
            Foto Carnet App
          </h1>
          <p className="text-gray-400">
            Sube tus fotos → Se procesan automáticamente → Descarga en WebP
          </p>
        </div>

        {/* Panel de progreso con cuenta regresiva real */}
        {pendientes > 0 && (
          <div className="bg-indigo-950/60 border border-indigo-700/50 rounded-2xl p-5 mb-6">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-600/30 rounded-xl">
                  {procesandoAuto ? (
                    <Loader2 className="w-5 h-5 text-indigo-300 animate-spin" />
                  ) : (
                    <Zap className="w-5 h-5 text-indigo-300" />
                  )}
                </div>
                <div>
                  <p className="font-medium text-indigo-200">Procesamiento automático activo</p>
                  <p className="text-sm text-indigo-300/70">
                    {procesandoAuto ? 'Procesando foto ahora...' : 'Esperando siguiente lote...'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold text-white tabular-nums tracking-tight">
                  {formatTiempo(segundosRestantes)}
                </p>
                <p className="text-xs text-indigo-300/70">tiempo estimado restante</p>
              </div>
            </div>

            {/* Barra de progreso */}
            <div className="mt-4 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-1000 ease-linear"
                style={{
                  width: `${Math.max(0, 100 - (segundosRestantes / (pendientes * SEGUNDOS_POR_FOTO || 1)) * 100)}%`
                }}
              />
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              <div className="bg-gray-900/50 rounded-xl py-2">
                <p className="text-lg font-semibold text-yellow-400">{pendientes}</p>
                <p className="text-xs text-gray-400">Pendientes</p>
              </div>
              <div className="bg-gray-900/50 rounded-xl py-2">
                <p className="text-lg font-semibold text-green-400">{listas}</p>
                <p className="text-xs text-gray-400">Listas</p>
              </div>
              <div className="bg-gray-900/50 rounded-xl py-2">
                <p className="text-lg font-semibold text-red-400">{errores}</p>
                <p className="text-xs text-gray-400">Errores</p>
              </div>
            </div>

            {ultimoProceso && (
              <p className="text-xs text-indigo-400/60 mt-3 text-center">
                Última llamada al worker: {ultimoProceso}
              </p>
            )}
          </div>
        )}

        {/* Upload */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-2xl p-6 mb-8 shadow-xl">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1">Grupo / Carpeta (opcional)</label>
              <input
                type="text"
                value={grupo}
                onChange={(e) => setGrupo(e.target.value)}
                placeholder="Ej: 9° Grado, Grupo A..."
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <label className="cursor-pointer">
              <div className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium transition ${
                uploading 
                  ? 'bg-gray-700 text-gray-400 cursor-not-allowed' 
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white'
              }`}>
                {uploading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Subiendo...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    Subir fotos
                  </>
                )}
              </div>
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={handleUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>

            <button
              onClick={cargarFotos}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 transition"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Lista */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <ImageIcon className="w-5 h-5 text-indigo-400" />
              Fotos ({fotos.length})
            </h2>
          </div>

          {loading && fotos.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" />
              Cargando...
            </div>
          ) : fotos.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No hay fotos todavía</p>
              <p className="text-sm mt-1">Sube algunas para empezar</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {fotos.map((foto) => (
                <div key={foto.id} className="px-6 py-4 flex items-center gap-4 hover:bg-gray-800/50 transition">
                  <div className="flex-shrink-0">
                    {getEstadoIcon(foto.estado)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{foto.nombre_original}</p>
                    <div className="flex items-center gap-3 text-sm text-gray-400 mt-0.5">
                      <span>{getEstadoText(foto.estado)}</span>
                      {foto.grupo && (
                        <span className="px-2 py-0.5 bg-gray-800 rounded-md text-xs">{foto.grupo}</span>
                      )}
                    </div>
                  </div>
                  {foto.estado === 'lista' && foto.ruta_procesada && (
                    <a
                      href={getPublicUrl(foto.ruta_procesada) || '#'}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600/20 text-green-400 hover:bg-green-600/30 transition text-sm font-medium"
                    >
                      <Download className="w-4 h-4" />
                      WebP
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-center text-gray-600 text-sm mt-8">
          Procesamiento automático · 1 foto por lote · Contador en tiempo real · Formato WebP
        </p>
      </div>
    </main>
  )
}
