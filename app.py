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
# Streamlit se ejecuta desde la raíz del proyecto, por lo que las rutas deben ser relativas.
SRGB_PROFILE = "profiles/sRGB_IEC61966-2-1.icc"
ADOBE_RGB_PROFILE = "profiles/AdobeRGB1998.icc"
CMYK_PROFILE = "profiles/ISOcoated_v2_eci.icc"
TARGET_DPI = (150, 150) # Resolución fija de 150 DPI

# Verificar si los archivos ICC existen al inicio
if not all(os.path.exists(p) for p in [SRGB_PROFILE, ADOBE_RGB_PROFILE, CMYK_PROFILE]):
    st.error("🚨 Error: No se encontraron todos los perfiles ICC.")
    st.info("Asegúrate de que la carpeta 'profiles' y los archivos ICC están en la raíz de tu proyecto de GitHub, tal como se especificó en la guía.")
    st.stop()

# --- Cargar datos del perfil CMYK una sola vez para incrustación ---
# Esto hace más robusta la incrustación del perfil.
CMYK_PROFILE_BYTES = None
try:
    with open(CMYK_PROFILE, 'rb') as f:
        CMYK_PROFILE_BYTES = f.read()
except Exception as e:
    st.error(f"🚨 Error al leer el perfil CMYK para la incrustación: {e}")
    st.stop()


def convert_rgb_to_cmyk(img: Image.Image, source_profile_path: str, cmyk_profile_path: str) -> Image.Image:
    """Convierte una imagen RGB a CMYK conservando la transparencia si es posible."""
    
    # 1. Preparar la Imagen y el Canal Alpha
    is_transparent = img.mode == 'RGBA'
    
    if is_transparent:
        # Separar el canal RGB del canal Alpha
        rgb_img = img.convert('RGB')
        alpha_channel = img.getchannel('A')
    else:
        rgb_img = img.convert('RGB')
        alpha_channel = None

    # 2. Conversión de Color (RGB -> CMYK)
    try:
        # Cargar los perfiles ICC
        source_profile = ImageCms.getOpenProfile(source_profile_path)
        cmyk_profile = ImageCms.getOpenProfile(cmyk_profile_path)

        # Aplicar la transformación (rendering intent 1: relative colorimetric, común para impresión)
        cmyk_img = ImageCms.profileToProfile(
            rgb_img, 
            source_profile, 
            cmyk_profile, 
            renderingIntent=1, 
            outputMode='CMYK'
        )
    except Exception as e:
        st.error(f"Error durante la conversión de color (profileToProfile): {e}")
        return None

    # 3. Recomponer con el Canal Alpha (Si existía)
    if is_transparent and cmyk_img.mode == 'CMYK':
        # Reincorporamos el canal Alpha al CMYK
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
        # Cargar imagen
        input_img = Image.open(uploaded_file)
        
        # --- CHEQUEO DE MODO DE IMAGEN PARA ESTANDARIZACIÓN ---
        
        # 1. Si la imagen NO es RGB o RGBA (los modos que podemos convertir)
        if input_img.mode not in ['RGB', 'RGBA']:
            
            # Caso A: La imagen ya está en CMYK. No hacemos conversión de perfil.
            if input_img.mode == 'CMYK':
                st.warning("⚠️ Atención: La imagen que subiste ya está en modo CMYK. Se omitirá la conversión de perfiles. Se procederá con la resolución y el formato de salida elegidos.")
                # Clonamos la imagen original CMYK para usarla directamente
                cmyk_img = input_img.copy() 
            
            # Caso B: Otros modos (Grises, Paleta, etc.). Intentamos forzar a RGB/RGBA.
            else:
                try:
                    # Si tiene canal Alpha, la convertimos a RGBA
                    if 'A' in input_img.mode or input_img.mode == 'LA': 
                        input_img = input_img.convert('RGBA')
                    # Si no, la convertimos a RGB
                    else:
                        input_img = input_img.convert('RGB')
                    st.info(f"ℹ️ Modo de imagen original estandarizado a {input_img.mode} para la conversión.")
                except Exception as ex:
                    st.error(f"❌ Error crítico: No se puede estandarizar el modo de imagen '{input_img.mode}'. Intenta subir una imagen RGB o PNG estándar. Detalle: {ex}")
                    st.stop()
        
        # Mostrar detalles de la imagen subida (después de la estandarización)
        st.sidebar.subheader("Imagen Original")
        st.sidebar.image(input_img, caption=f"Modo: {input_img.mode}, Tamaño: {input_img.size}")
        st.sidebar.markdown(f"**¿Tiene Transparencia (Alpha)?** {'Sí' if 'A' in input_img.mode else 'No'}")


        # 4. Iniciar la Conversión
        with st.spinner("Realizando conversión de color a FOGRA39..."):
            
            # Ejecutar la conversión solo si no es CMYK de origen
            if input_img.mode in ['RGB', 'RGBA']:
                cmyk_img = convert_rgb_to_cmyk(input_img, source_profile_path, CMYK_PROFILE)
            
            # Si cmyk_img no se definió porque hubo un fallo en convert_rgb_to_cmyk
            if 'cmyk_img' not in locals() or cmyk_img is None:
                st.warning("La conversión falló. Revisa el mensaje de error anterior.")
                st.stop()
                
            st.success("✅ Conversión completada a CMYK (ISO Coated v2/FOGRA39).")

            # 5. Generar Archivo de Salida para Descarga
            file_extension = ".tif" if output_format == "TIFF (Impresión - Recomendado)" else ".jpg"
            mime_type = "image/tiff" if output_format == "TIFF (Impresión - Recomendado)" else "image/jpeg"
            
            output_buffer = io.BytesIO()
            
            if file_extension == ".tif":
                # Guardado TIFF: incrustar perfil y DPI
                # Usamos los bytes cargados al inicio (CMYK_PROFILE_BYTES)
                cmyk_img.save(
                    output_buffer, 
                    format='TIFF', 
                    dpi=TARGET_DPI,
                    icc_profile=CMYK_PROFILE_BYTES, 
                    compression="tiff_lzw"
                )
            
            elif file_extension == ".jpg":
                # Guardar como JPEG CMYK. Aseguramos que sea modo CMYK para el JPG.
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
        # Este mensaje final solo se mostrará si falla la carga o el guardado
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
    **Nota Importante:** El soporte para TIFF CMYK con transparencia (CMYKA) puede variar en software de terceros. Se recomienda verificar el archivo final en un programa de diseño profesional (como Adobe Photoshop).
</div>
""", unsafe_allow_html=True)
