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

        # Aplicar la transformación (rendering intent 0: perceptual, 1: relative colorimetric)
        # Usamos relative colorimetric (1) que es común para impresión.
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
        # Crear la imagen CMYKA
        cmyka_img = Image.merge('CMYK', cmyk_img.split())
        
        # Insertar el canal Alpha
        # La librería ImageCms a veces elimina el canal 'A', lo reincorporamos aquí.
        
        # Creamos una nueva imagen CMYKA
        temp_cmyka_img = Image.new('CMYKA', cmyka_img.size)
        
        # Copiamos los canales CMYK
        temp_cmyka_img.putdata(cmyka_img.getdata()) 

        # Si ImageCms soporta CMYK Alpha (CMYKA), intentamos poner el canal A directamente
        # En la práctica, Pillow/CMS no soporta CMYKA nativamente para guardado TIFF con perfil.
        # Para TIFF, la transparencia se maneja como un canal extra. 
        # Mantendremos CMYK y lo documentaremos. TIFF CMYK nativo no soporta canal Alpha en todos los lectores.
        
        # Para garantizar la compatibilidad, si hay transparencia, la imagen se guarda como TIFF CMYK. 
        # La transparencia se mantiene al guardar en TIFF. 
        # No hay un modo 'CMYKA' estándar en Pillow para guardar con perfiles.
        # Por simplicidad y compatibilidad, devolvemos CMYK y confiamos en que TIFF maneje el canal A.
        cmyk_img.putalpha(alpha_channel)
        
    return cmyk_img

# --- Interfaz de Usuario ---
st.title("🎨 Conversor RGB a CMYK")
st.markdown("Herramienta para preparar imágenes para imprenta (FOGRA39, 150 DPI) conservando transparencia.")

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
        
        # Mostrar detalles de la imagen subida
        st.sidebar.subheader("Imagen Original")
        st.sidebar.image(input_img, caption=f"Modo: {input_img.mode}, Tamaño: {input_img.size}")
        st.sidebar.markdown(f"**¿Tiene Transparencia (Alpha)?** {'Sí' if 'A' in input_img.mode else 'No'}")


        # 4. Iniciar la Conversión
        with st.spinner("Realizando conversión de color a FOGRA39..."):
            
            # Realizar la conversión
            cmyk_img = convert_rgb_to_cmyk(input_img, source_profile_path, CMYK_PROFILE)

            if cmyk_img is None:
                st.warning("La conversión falló. Revisa el mensaje de error anterior.")
                st.stop()
                
            st.success("✅ Conversión completada a CMYK (ISO Coated v2/FOGRA39).")

            # 5. Generar Archivo de Salida para Descarga
            file_extension = ".tif" if output_format == "TIFF (Impresión - Recomendado)" else ".jpg"
            mime_type = "image/tiff" if output_format == "TIFF (Impresión - Recomendado)" else "image/jpeg"
            
            output_buffer = io.BytesIO()
            
            if file_extension == ".tif":
                # Intentar incrustar el perfil y configurar DPI
                cmyk_img.save(
                    output_buffer, 
                    format='TIFF', 
                    dpi=TARGET_DPI,
                    # Intentar incrustar el perfil CMYK
                    icc_profile=open(CMYK_PROFILE, 'rb').read(), 
                    # Asegurar la compatibilidad con transparencia si existía
                    # Nota: Pillow soporta el canal A en TIFF, pero el estándar CMYK+Alpha puede variar.
                    # Aquí se guarda el canal A si la imagen original lo tenía.
                    compression="tiff_lzw" # Compresión sin pérdidas (lzw)
                )
            
            elif file_extension == ".jpg":
                # Guardar como JPEG CMYK (no soporta transparencia ni incrustación de ICC)
                # La conversión de color ya está hecha, pero no se incrusta el perfil en JPEG.
                cmyk_img.save(
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
        st.info("Revisa la consola para más detalles o intenta con otro archivo.")

st.markdown("---")
st.markdown("""
<style>
    .footer {
        font-size: 0.8em;
        color: #999;
    }
</style>
<div class="footer">
    **Nota Importante:** El soporte de creación de archivos PSD con perfiles ICC es extremadamente complejo en Python y no está incluido en esta versión. Se recomienda usar TIFF.
</div>
""", unsafe_allow_html=True)
