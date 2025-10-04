import streamlit as st
from PIL import Image, ImageCms
import io

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Conversor RGB a CMYK Pro",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="auto",
)

# --- Rutas a los Perfiles de Color (ICC) ---
# Asegúrate de que estos archivos estén en una carpeta 'profiles'
srgb_profile_path = 'profiles/sRGB_IEC61966-2-1.icc'
adobe_rgb_profile_path = 'profiles/AdobeRGB1998.icc'
cmyk_profile_path = 'profiles/ISOcoated_v2_eci.icc' # FOGRA39

# --- Función Principal de Conversión ---
def convert_image_to_cmyk(image_bytes, input_profile, output_format):
    """
    Convierte una imagen de RGB a CMYK usando perfiles de color ICC,
    conservando la transparencia y estableciendo los DPI.
    """
    try:
        # Abrir la imagen desde los bytes en memoria
        img = Image.open(io.BytesIO(image_bytes))

        # 1. Conservar la transparencia (canal alfa)
        has_alpha = 'A' in img.getbands()
        alpha_channel = None
        if has_alpha:
            alpha_channel = img.getchannel('A')
            # Para la conversión de perfil, trabajamos solo con los canales RGB
            img = img.convert('RGB')

        # 2. Asignar el perfil de color de entrada correcto
        input_profile_path = srgb_profile_path if input_profile == 'sRGB' else adobe_rgb_profile_path

        # 3. Realizar la conversión de color profesional con ImageCms
        # El Intent 0 (Perceptual) es ideal para fotografías y busca mantener la apariencia visual.
        img_cmyk = ImageCms.profileToProfile(
            img,
            input_profile_path,
            cmyk_profile_path,
            renderingIntent=0,
            outputMode='CMYK'
        )

        # 4. Si la imagen original tenía transparencia, la reincorporamos
        if has_alpha and alpha_channel:
            img_cmyk.putalpha(alpha_channel)

        # 5. Guardar la imagen en un buffer en memoria con el formato y DPI correctos
        output_buffer = io.BytesIO()
        if output_format == 'TIFF':
            # La compresión LZW es sin pérdidas y muy compatible
            img_cmyk.save(output_buffer, format='TIFF', dpi=(150, 150), compression='tiff_lzw')
            file_extension = 'tiff'
        elif output_format == 'PSD':
            # Pillow usa la librería 'psd-tools' para guardar, asegúrate de tenerla
            img_cmyk.save(output_buffer, format='PSD', dpi=(150, 150))
            file_extension = 'psd'
        
        output_buffer.seek(0)
        return output_buffer, file_extension

    except FileNotFoundError as e:
        st.error(f"Error: No se encontró un perfil de color. Asegúrate de que los archivos .icc estén en la carpeta 'profiles'. Detalle: {e}")
        return None, None
    except Exception as e:
        st.error(f"Ocurrió un error inesperado durante la conversión: {e}")
        return None, None


# --- Interfaz de Usuario de Streamlit ---

st.title("🎨 Conversor Profesional RGB a CMYK")
st.markdown("""
Esta herramienta convierte tus imágenes RGB al espacio de color **CMYK FOGRA39**,
preparándolas para imprenta profesional. Conserva la **transparencia** y ajusta la
resolución a **150 DPI**.
""")

st.info("**Instrucciones:**\n"
        "1. Sube tu archivo de imagen (PNG, JPG, etc.).\n"
        "2. Selecciona el perfil de color RGB original de tu imagen.\n"
        "3. Elige el formato de salida (TIFF es recomendado para calidad y compatibilidad).\n"
        "4. Haz clic en 'Convertir' y descarga tu archivo listo para imprimir.")

uploaded_file = st.file_uploader(
    "Sube tu imagen aquí",
    type=['png', 'jpg', 'jpeg', 'webp']
)

if uploaded_file is not None:
    # Mostrar la imagen original
    st.image(uploaded_file, caption="Imagen Original (RGB)", use_column_width=True)

    # Opciones de conversión
    col1, col2 = st.columns(2)
    with col1:
        input_profile_option = st.selectbox(
            "Perfil RGB de Origen:",
            ('sRGB', 'AdobeRGB'),
            help="sRGB es el estándar para la web. AdobeRGB tiene una gama de colores más amplia, común en fotografía profesional."
        )
    with col2:
        output_format_option = st.selectbox(
            "Formato de Salida:",
            ('TIFF', 'PSD'),
            help="TIFF es el estándar de oro para la impresión por su calidad y compresión sin pérdidas. PSD conserva la estructura para Adobe Photoshop."
        )

    # Botón para iniciar la conversión
    if st.button("✨ Convertir a CMYK", use_container_width=True):
        with st.spinner("Procesando... La conversión de color puede tardar unos segundos..."):
            image_bytes = uploaded_file.getvalue()
            
            converted_image_buffer, file_ext = convert_image_to_cmyk(
                image_bytes,
                input_profile_option,
                output_format_option
            )

            if converted_image_buffer:
                st.success("¡Conversión exitosa!")
                
                # Generar el nombre del archivo de salida
                original_filename = uploaded_file.name.rsplit('.', 1)[0]
                download_filename = f"{original_filename}_CMYK_FOGRA39.{file_ext}"

                st.download_button(
                    label=f"📥 Descargar {download_filename}",
                    data=converted_image_buffer,
                    file_name=download_filename,
                    mime=f'image/{file_ext}',
                    use_container_width=True
                )
else:
    st.warning("Esperando a que subas una imagen.")

st.markdown("---")
st.markdown("Desarrollado con ❤️ por IA para flujos de trabajo de impresión.")
