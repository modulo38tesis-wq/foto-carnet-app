import os
import io
import time
import traceback
from flask import Flask, jsonify, request
from supabase import create_client, Client
from rembg import remove, new_session
from PIL import Image
import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURACIÓN ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

MEDIDA_FINAL = (1500, 2000)
FACTOR_ZOOM_CABEZA = 0.35
MAX_DIMENSION = 1200
MAX_ESCALA = 2.0
WEBP_QUALITY = 95

# Cargar modelos una sola vez (se mantiene en memoria mientras el servicio esté despierto)
print("🔄 Cargando modelos de IA...")
session_rembg = new_session("u2net_human_seg")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
proto_path = os.path.join(BASE_DIR, "deploy.prototxt.txt")
model_path = os.path.join(BASE_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
net = cv2.dnn.readNetFromCaffe(proto_path, model_path)
print("✅ Modelos cargados correctamente")

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def limitar_tamano(img_pil, max_dim=MAX_DIMENSION):
    ancho, alto = img_pil.size
    if max(ancho, alto) <= max_dim:
        return img_pil
    ratio = max_dim / max(ancho, alto)
    return img_pil.resize((int(ancho * ratio), int(alto * ratio)), Image.LANCZOS)

def limpieza_pro_humana(img_pil):
    img_np = np.array(img_pil)
    if img_np.shape[2] != 4:
        return img_pil
    r, g, b, a = cv2.split(img_np)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(a, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        mask_final = np.zeros_like(mask)
        c = max(cnts, key=cv2.contourArea)
        cv2.drawContours(mask_final, [c], -1, 255, -1)
        mask_final = cv2.GaussianBlur(mask_final, (3, 3), 0)
        a = cv2.bitwise_and(a, mask_final)
    return Image.fromarray(cv2.merge([r, g, b, a]))

def procesar_una_foto(img_bytes: bytes) -> bytes:
    """Procesa una imagen y devuelve los bytes en WebP"""
    img_ori = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img_ori = limitar_tamano(img_ori)

    # Remoción de fondo
    img_sf = remove(
        img_ori,
        session=session_rembg,
        alpha_matting=False,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=15,
        alpha_matting_erode_size=0
    )
    img_sf = limpieza_pro_humana(img_sf)

    # Detección facial
    cv_img = cv2.cvtColor(np.array(img_ori.convert("RGB")), cv2.COLOR_RGB2BGR)
    h_o, w_o = cv_img.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(cv_img, (300, 300)), 1.0, (300, 300), (104, 177, 123))
    net.setInput(blob)
    det = net.forward()

    nx, ny, h_cara = None, None, None
    for i in range(det.shape[2]):
        if det[0, 0, i, 2] > 0.5:
            box = det[0, 0, i, 3:7] * np.array([w_o, h_o, w_o, h_o])
            x1, y1, x2, y2 = box.astype("int")
            h_cara = y2 - y1
            nx = x1 + (x2 - x1) / 2
            ny = y1 + (h_cara * 0.55)
            break

    lienzo = Image.new("RGBA", MEDIDA_FINAL, (255, 255, 255, 255))

    if nx is not None and h_cara:
        escala = (MEDIDA_FINAL[1] * FACTOR_ZOOM_CABEZA) / h_cara
        escala = min(escala, MAX_ESCALA)
        img_res = img_sf.resize(
            (int(img_sf.width * escala), int(img_sf.height * escala)),
            Image.LANCZOS
        )
        px = int(750 - (nx * escala))
        py = int(850 - (ny * escala))
        lienzo.paste(img_res, (px, py), img_res)

    # Convertir a WebP
    buffer = io.BytesIO()
    lienzo.convert("RGB").save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()

def procesar_pendientes():
    """Busca fotos pendientes y las procesa"""
    sb = get_supabase()
    
    # Obtener fotos pendientes
    res = sb.table("fotos").select("*").eq("estado", "pendiente").limit(5).execute()
    pendientes = res.data or []

    if not pendientes:
        return {"procesadas": 0, "mensaje": "No hay fotos pendientes"}

    resultados = []

    for foto in pendientes:
        foto_id = foto["id"]
        ruta_original = foto["ruta_original"]
        nombre = foto["nombre_original"]

        try:
            # Marcar como procesando
            sb.table("fotos").update({"estado": "procesando"}).eq("id", foto_id).execute()

            # Descargar de Storage
            data = sb.storage.from_("originales").download(ruta_original)

            # Procesar
            webp_bytes = procesar_una_foto(data)

            # Nombre de salida
            nombre_base = os.path.splitext(os.path.basename(ruta_original))[0]
            ruta_procesada = f"{nombre_base}.webp"
            if foto.get("grupo"):
                ruta_procesada = f"{foto['grupo']}/{ruta_procesada}"

            # Subir a procesadas
            sb.storage.from_("procesadas").upload(
                ruta_procesada,
                webp_bytes,
                {"content-type": "image/webp", "upsert": "true"}
            )

            # Actualizar registro
            sb.table("fotos").update({
                "estado": "lista",
                "ruta_procesada": ruta_procesada,
                "updated_at": "now()"
            }).eq("id", foto_id).execute()

            resultados.append({"id": foto_id, "nombre": nombre, "estado": "lista"})
            print(f"✅ Procesada: {nombre}")

        except Exception as e:
            print(f"❌ Error en {nombre}: {e}")
            traceback.print_exc()
            sb.table("fotos").update({"estado": "error"}).eq("id", foto_id).execute()
            resultados.append({"id": foto_id, "nombre": nombre, "estado": "error", "error": str(e)})

    return {"procesadas": len(resultados), "detalle": resultados}

# --- RUTAS ---

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Foto Carnet Worker está vivo 🚀",
        "version": "2.0.0",
        "endpoints": {
            "/health": "Health check",
            "/process": "Procesar fotos pendientes (POST o GET)"
        }
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

@app.route("/process", methods=["GET", "POST"])
def process():
    """Endpoint para procesar las fotos pendientes"""
    try:
        resultado = procesar_pendientes()
        return jsonify({"success": True, **resultado})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
