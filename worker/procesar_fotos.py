import os
import cv2
import numpy as np
from rembg import remove, new_session
from PIL import Image

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Carpeta donde pones tus grupos de fotos (Ej: FOTOS_ORIGINALES/Grupo_A, Grupo_B)
CARPETA_ENTRADA_MAESTRA = os.path.join(BASE_DIR, "FOTOS_ORIGINALES")
# Carpeta donde se guardará todo respetando los nombres de las subcarpetas
CARPETA_SALIDA_MAESTRA = os.path.join(BASE_DIR, "FOTOS_FINALIZADAS")

# --- AJUSTES DE IMAGEN ---
MEDIDA_FINAL = (1500, 2000)
FACTOR_ZOOM_CABEZA = 0.35
MAX_DIMENSION = 1200
MAX_ESCALA = 2.0

# Calidad WebP (95 = excelente, 90 = muy buena y más liviana)
WEBP_QUALITY = 95

# Cargamos la sesión de IA especializada en humanos (Para recortes perfectos de ropa y pelo)
session = new_session("u2net_human_seg")

def limitar_tamano_imagen(img_pil, max_dim=MAX_DIMENSION):
    """Reduce la imagen si es demasiado grande para evitar uso excesivo de memoria."""
    ancho, alto = img_pil.size
    if max(ancho, alto) <= max_dim:
        return img_pil

    ratio = max_dim / max(ancho, alto)
    nuevo_ancho = int(ancho * ratio)
    nuevo_alto = int(alto * ratio)
    return img_pil.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

def limpieza_pro_humana(img_pil):
    """
    Rellena huecos en ropa y suaviza bordes para un acabado profesional.
    """
    img_np = np.array(img_pil)
    if img_np.shape[2] != 4:
        return img_pil
    
    r, g, b, a = cv2.split(img_np)
    
    # Rellenar huecos internos (Cierre morfológico para uniformes blancos)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(a, cv2.MORPH_CLOSE, kernel)
    
    # Limpiar ruidos externos y suavizar el contorno (Anti-aliasing)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        mask_final = np.zeros_like(mask)
        c = max(cnts, key=cv2.contourArea)
        cv2.drawContours(mask_final, [c], -1, 255, -1)
        mask_final = cv2.GaussianBlur(mask_final, (3, 3), 0)
        a = cv2.bitwise_and(a, mask_final)

    return Image.fromarray(cv2.merge([r, g, b, a]))

def encontrar_archivos_ia():
    proto, model = None, None
    for f in os.listdir(BASE_DIR):
        f_l = f.lower()
        if f_l.startswith("deploy") and (".proto" in f_l):
            proto = os.path.join(BASE_DIR, f)
        if f_l.endswith(".caffemodel"):
            model = os.path.join(BASE_DIR, f)
    return proto, model

def procesar_imagenes():
    proto_p, model_p = encontrar_archivos_ia()
    if not proto_p or not model_p:
        print("❌ Error: Faltan archivos de IA (deploy/caffemodel) en la carpeta del script.")
        return
    
    net = cv2.dnn.readNetFromCaffe(proto_p, model_p)

    if not os.path.exists(CARPETA_ENTRADA_MAESTRA):
        os.makedirs(CARPETA_ENTRADA_MAESTRA)
    if not os.path.exists(CARPETA_SALIDA_MAESTRA):
        os.makedirs(CARPETA_SALIDA_MAESTRA)

    # Listar subcarpetas dentro de la entrada maestra
    subcarpetas = [f for f in os.listdir(CARPETA_ENTRADA_MAESTRA) 
                   if os.path.isdir(os.path.join(CARPETA_ENTRADA_MAESTRA, f))]
    
    if not subcarpetas:
        print(f"📂 No hay subcarpetas en '{CARPETA_ENTRADA_MAESTRA}'. Pon tus grupos de fotos ahí.")
        return

    for carpeta in subcarpetas:
        ruta_in = os.path.join(CARPETA_ENTRADA_MAESTRA, carpeta)
        ruta_out = os.path.join(CARPETA_SALIDA_MAESTRA, f"{carpeta}_Procesadas")
        
        if not os.path.exists(ruta_out):
            os.makedirs(ruta_out)
        
        # Aceptamos más formatos de entrada
        archivos = [f for f in os.listdir(ruta_in) 
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'))]
        print(f"\n🚀 Procesando carpeta: {carpeta} | Zoom: {FACTOR_ZOOM_CABEZA} | Salida: WebP")

        for archivo in archivos:
            try:
                img_ori = Image.open(os.path.join(ruta_in, archivo)).convert("RGBA")
                img_ori = limitar_tamano_imagen(img_ori)
                print(f"      [DEBUG] {archivo} tamaño reducido a: {img_ori.size}")
                
                # --- REMOCIÓN DE FONDO AVANZADA ---
                img_sf = remove(
                    img_ori,
                    session=session,
                    alpha_matting=False,
                    alpha_matting_foreground_threshold=240,
                    alpha_matting_background_threshold=15,
                    alpha_matting_erode_size=0
                )
                
                img_sf = limpieza_pro_humana(img_sf)

                # Detección Facial para el centrado
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
                
                if nx is not None:
                    escala = (MEDIDA_FINAL[1] * FACTOR_ZOOM_CABEZA) / h_cara
                    escala = min(escala, MAX_ESCALA)
                    img_res = img_sf.resize(
                        (int(img_sf.width * escala), int(img_sf.height * escala)), 
                        Image.LANCZOS
                    )
                    
                    # --- POSICIÓN ELEVADA PARA CARNET ---
                    px = int(750 - (nx * escala))
                    py = int(850 - (ny * escala))
                    
                    lienzo.paste(img_res, (px, py), img_res)
                    status = "Zoom OK"
                else:
                    status = "Sin rostro detectado"

                # --- GUARDAR EN WEBP (más ligero y excelente calidad) ---
                nombre_f = os.path.splitext(archivo)[0] + ".webp"
                # Convertimos a RGB porque el fondo es blanco sólido (archivo más liviano)
                lienzo_rgb = lienzo.convert("RGB")
                lienzo_rgb.save(
                    os.path.join(ruta_out, nombre_f),
                    "WEBP",
                    quality=WEBP_QUALITY,
                    method=6  # Mejor compresión
                )
                print(f"   ✅ {archivo} → {nombre_f} | {status}")

            except Exception as e:
                print(f"   ❌ Error en {archivo}: {e}")

    print(f"\n✨ ¡TERMINADO! Fotos en WebP listas en: {CARPETA_SALIDA_MAESTRA}")

if __name__ == "__main__":
    procesar_imagenes()
