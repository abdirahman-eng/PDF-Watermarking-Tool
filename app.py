import io
import re
import zipfile

import fitz
import pandas as pd
import streamlit as st


FONT_NAME = "helv"
FONT_SIZE = 20
WATERMARK_COLOR = (0.5, 0.5, 0.5)
FILL_OPACITY = 0.2


def sanitize_filename(value: object) -> str:
    """Return a filesystem-safe name for use in the ZIP archive."""
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip()
    safe_name = safe_name.rstrip(". ")
    return safe_name or "unnamed"


def apply_tiled_watermark(pdf_bytes: bytes, watermark_text: str) -> bytes:
    """Apply a dense, interlaced, 45-degree watermark to every PDF page."""
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_width = fitz.get_text_length(
        watermark_text, fontname=FONT_NAME, fontsize=FONT_SIZE
    )
    x_step = max(text_width + 80, 120)
    row_step = FONT_SIZE * 4
    rotation_matrix = fitz.Matrix(1, 1).prerotate(45)

    try:
        for page in document:
            page_rect = page.rect
            x_start = -page_rect.height - text_width
            x_end = page_rect.width + page_rect.height + text_width
            y_start = -page_rect.width - row_step
            y_end = page_rect.height + page_rect.width + row_step

            column_index = 0
            x = x_start
            while x <= x_end:
                y_offset = row_step / 2 if column_index % 2 else 0
                y = y_start + y_offset
                while y <= y_end:
                    page.insert_text(
                        (x, y),
                        watermark_text,
                        fontname=FONT_NAME,
                        fontsize=FONT_SIZE,
                        color=WATERMARK_COLOR,
                        morph=(fitz.Point(x, y), rotation_matrix),
                        fill_opacity=FILL_OPACITY,
                    )
                    y += row_step
                x += x_step
                column_index += 1

        output = io.BytesIO()
        document.save(output, garbage=4, deflate=True)
        return output.getvalue()
    finally:
        document.close()


def main() -> None:
    st.set_page_config(page_title="Batch PDF Watermarker", page_icon="📄")
    st.title("Batch PDF Watermarker")
    st.write("Upload a base PDF and an Excel file containing a `Name` column.")

    pdf_upload = st.file_uploader("Base PDF", type=["pdf"])
    excel_upload = st.file_uploader("Excel data", type=["xlsx"])

    if not pdf_upload or not excel_upload:
        st.info("Upload both files to begin.")
        return

    if not st.button("Create watermarked PDFs", type="primary"):
        return

    try:
        names_frame = pd.read_excel(io.BytesIO(excel_upload.getvalue()))
    except Exception as exc:
        st.error(f"Could not read the Excel file: {exc}")
        return

    if "Name" not in names_frame.columns:
        st.error("The Excel file must contain a 'Name' column.")
        return

    names = names_frame["Name"].dropna().tolist()
    if not names:
        st.error("The 'Name' column does not contain any values.")
        return

    base_pdf = pdf_upload.getvalue()
    progress = st.progress(0, text="Preparing PDFs...")
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for index, name in enumerate(names, start=1):
                safe_name = sanitize_filename(name)
                watermark_text = f"Licensed to: {safe_name}"
                watermarked_pdf = apply_tiled_watermark(base_pdf, watermark_text)
                archive.writestr(
                    f"{safe_name}_cheatsheet.pdf",
                    watermarked_pdf,
                )
                progress.progress(
                    index / len(names),
                    text=f"Processed {index} of {len(names)}",
                )
    except Exception as exc:
        st.error(f"Could not create the watermarked PDFs: {exc}")
        return

    st.success(f"Created {len(names)} watermarked PDF(s).")
    st.download_button(
        label="Download watermarked_pdfs.zip",
        data=zip_buffer.getvalue(),
        file_name="watermarked_pdfs.zip",
        mime="application/zip",
    )


if __name__ == "__main__":
    main()
