import streamlit as st
from PIL import Image, ImageCms
import io
import os
import tempfile
import numpy as np

# --- Configuración de la Página de Streamlit ---
st.set_page_config(
    page_title="Conversor RGB a CMYK (Impresión Profesional)",
    layout="centered",
    initial_sidebar_state="auto"
)

# --- Constantes y Rutas de Perfiles ICC ---
SRGB_PROFILE = "profiles/sRGB_IEC61966-2-1.icc"
ADOBE_RGB_PROFILE = "profiles/AdobeRGB1998.icc"
# Usamos el nombre del archivo de alta compatibilidad FOGRA39_v3.icc
CMYK_PROFILE = "profiles/FOGRA39_v3.icc"
TARGET_DPI = (150, 150) # Resolución fija de 150 DPI

# --- Cargar Perfiles ICC al Inicio y Obtener Bytes CMYK Válidos ---
CMYK_PROFILE_BYTES = None
try:
    if not all(os.path.exists(p) for p in [SRGB_PROFILE, ADOBE_RGB_PROFILE, CMYK_PROFILE]):
        raise FileNotFoundError("No se encontraron todos los perfiles ICC necesarios.")
        
    # 1. Cargar el perfil CMYK como objeto ImageCms
    cmyk_profile_obj = ImageCms.getOpenProfile(CMYK_PROFILE)
    
    # 2. Obtener la representación binaria COMPATIBLE usando .tobytes()
    # Esta es la parte crítica que resuelve el error de validación de Photoshop.
    CMYK_PROFILE_BYTES = cmyk_profile_obj.tobytes()

except FileNotFoundError:
    st.error("🚨 Error: No se encontraron los archivos ICC.")
    st.info(f"Asegúrate de que los archivos ICC están en la carpeta 'profiles'. Se espera: 'sRGB_IEC61966-2-1.icc', 'AdobeRGB1998.icc' y 'FOGRA39_v3.icc'.")
    st.stop()
except Exception as e:
    st.error(f"🚨 Error al inicializar los perfiles ICC: {e}")
    st.info("Esto podría indicar un archivo ICC corrupto. Intenta descargar nuevamente FOGRA39_v3.")
    st.stop()


def convert_rgb_to_cmyk(img: Image.Image, source_profile_path: str, cmyk_profile_obj) -> Image.Image:
    """Convierte una imagen RGB a CMYK conservando la transparencia si es posible."""
    
    # 1. Preparar la Imagen y el Canal Alpha
    is_transparent = img.mode == 'RGBA'
    
    if is_transparent:
        rgb_img = img.convert('RGB')
        alpha_channel = img.getchannel('A')
    else:
        rgb_img = img.convert('RGB')
        alpha_channel = None

    # 2. Conversión de Color (RGB -> CMYK)
    try:
        # Cargamos el perfil RGB de origen
        source_profile = ImageCms.getOpenProfile(source_profile_path)
        
        # Aplicar la transformación (rendering intent 1: relative colorimetric, común para impresión)
        # Usamos el objeto cmyk_profile_obj que ya fue cargado al inicio
        cmyk_img = ImageCms.profileToProfile(
            rgb_img, 
            source_profile, 
            cmyk_profile_obj, 
            renderingIntent=1, 
            outputMode='CMYK'
        )
    except Exception as e:
        st.error(f"Error durante la conversión de color (profileToProfile): {e}")
        return None

    # 3. Recomponer con el Canal Alpha (Si existía)
    if is_transparent and cmyk_img.mode == 'CMYK':
        # Reincorporamos el canal Alpha al CMYK (creando CMYKA)
        cmyk_img.putalpha(alpha_channel)
        
    return cmyk_img

# --- Interfaz de Usuario ---
st.title("🎨 Conversor RGB a CMYK")
st.markdown("Herramienta para preparar imágenes para imprenta (**FOGRA39**, **150 DPI**) conservando transparencia.")

# --- Seleccionar Perfil de Origen ---
source_profile_choice = st.selectbox(
    "1. Selecciona el perfil RGB de la imagen original:",
    ("sRGB (Estándar Web)", "Adobe RGB 1998 (Espacio Grande)")
)

if source_profile_choice == "sRGB (Estándar Web)":
    source_profile_path = SRGB_PROFILE
else:
    source_profile_path = ADOBE_RGB_PROFILE

# --- Cargar Archivo ---
uploaded_file = st.file_uploader(
    "2. Sube tu imagen (JPG, PNG o TIFF)", 
    type=['jpg', 'jpeg', 'png', 'tif', 'tiff']
)

output_format = st.selectbox(
    "3. Selecciona el formato de salida:",
    ("TIFF (Impresión - Recomendado)", "JPEG (Prueba/Web - CMYK)")
)


if uploaded_file is not None:
    try:
        input_img = Image.open(uploaded_file)
        
        # --- CHEQUEO DE MODO DE IMAGEN PARA ESTANDARIZACIÓN ---
        if input_img.mode not in ['RGB', 'RGBA']:
            
            if input_img.mode == 'CMYK':
                st.warning("⚠️ Atención: La imagen que subiste ya está en modo CMYK. Se procederá solo con la resolución y el formato.")
                cmyk_img = input_img.copy() 
            else:
                try:
                    if 'A' in input_img.mode or input_img.mode == 'LA': 
                        input_img = input_img.convert('RGBA')
                    else:
                        input_img = input_img.convert('RGB')
                    st.info(f"ℹ️ Modo de imagen original estandarizado a {input_img.mode} para la conversión.")
                except Exception as ex:
                    st.error(f"❌ Error crítico: No se puede estandarizar el modo de imagen '{input_img.mode}'. Detalle: {ex}")
                    st.stop()
        
        # Mostrar detalles de la imagen subida
        st.sidebar.subheader("Imagen Original")
        st.sidebar.image(input_img, caption=f"Modo: {input_img.mode}, Tamaño: {input_img.size}")
        st.sidebar.markdown(f"**¿Tiene Transparencia (Alpha)?** {'Sí' if 'A' in input_img.mode else 'No'}")


        # 4. Iniciar la Conversión
        with st.spinner("Realizando conversión de color a FOGRA39..."):
            
            # Ejecutar la conversión solo si no es CMYK de origen
            if input_img.mode in ['RGB', 'RGBA']:
                # Pasamos el objeto cmyk_profile_obj ya cargado
                cmyk_img = convert_rgb_to_cmyk(input_img, source_profile_path, cmyk_profile_obj) 
            
            if 'cmyk_img' not in locals() or cmyk_img is None:
                st.warning("La conversión falló. Revisa el mensaje de error.")
                st.stop()
                
            st.success("✅ Conversión completada a CMYK (FOGRA39 / ISO Coated v2).")

            # 5. Generar Archivo de Salida para Descarga
            file_extension = ".tif" if output_format == "TIFF (Impresión - Recomendado)" else ".jpg"
            mime_type = "image/tiff" if output_format == "TIFF (Impresión - Recomendado)" else "image/jpeg"
            
            output_buffer = io.BytesIO()
            
            if file_extension == ".tif":
                # Guardado TIFF: incrustar perfil y DPI
                # Utilizamos CMYK_PROFILE_BYTES generado con .tobytes()
                cmyk_img.save(
                    output_buffer, 
                    format='TIFF', 
                    dpi=TARGET_DPI,
                    icc_profile=CMYK_PROFILE_BYTES, 
                )
            
            elif file_extension == ".jpg":
                cmyk_img.convert('CMYK').save( 
                    output_buffer, 
                    format='JPEG', 
                    quality=95, 
                    optimize=True
                )

            output_buffer.seek(0)
            
            # --- Botón de Descarga ---
            st.markdown("---")
            st.subheader("Descarga de Archivo Final")
            st.download_button(
                label=f"⬇️ Descargar Archivo CMYK {file_extension.upper()}",
                data=output_buffer,
                file_name=f"imagen_cmyk{file_extension}",
                mime=mime_type
            )
            
            st.markdown(f"""
            **Características del archivo:**
            * **Modo de Color:** CMYK (FOGRA39 / ISO Coated v2)
            * **DPI:** 150x150
            * **Formato:** {file_extension.upper()}
            """)

    except Exception as e:
        st.error(f"Ocurrió un error inesperado durante la carga o conversión: {e}")
        st.info("Revisa si el archivo es un formato de imagen estándar (RGB/PNG/JPG/TIFF) y no está dañado.")

st.markdown("---")
st.markdown("""
<style>
    .footer {
        font-size: 0.8em;
        color: #999;
    }
</style>
<div class="footer">
    **Nota Importante:** El soporte para TIFF CMYK con transparencia (CMYKA) puede variar. Si Photoshop rechaza el perfil ICC, prueba a **asignar el perfil FOGRA39 manualmente** en Photoshop después de abrir el archivo, ya que el color CMYK ya es correcto.
</div>
""", unsafe_allow_html=True)
