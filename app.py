import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import os

st.set_page_config(page_title="TRACES Annex IV Extractor", page_icon="🐟")
st.title("🐟 TRACES - Annex IV Extractor (Offline Mode)")
st.markdown("ดึงข้อมูลจากไฟล์ PDF ทันที (รองรับเฉพาะไฟล์ PDF ดิจิทัล ไม่รองรับไฟล์สแกนรูปภาพ)")

uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 สกัดข้อมูล") and uploaded_file:
    with st.spinner("กำลังสกัดข้อมูลจากตาราง..."):
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                # 1. เช็กก่อนว่าเป็นไฟล์สแกน (ไม่มี Text) หรือไม่
                text_all = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_all += text
                
                if not text_all.strip():
                    st.error("❌ ไฟล์นี้เป็นไฟล์สแกนรูปภาพ โปรแกรมโหมดนี้รองรับเฉพาะ 'PDF ดิจิทัล' เท่านั้นครับ")
                    st.stop()
                
                # 2. ค้นหา Document Number 
                doc_num = ""
                doc_match = re.search(r"DOCUMENT\s*NUMBER\s*[:\s]*([A-Za-z0-9/\-]+)", text_all, re.IGNORECASE)
                if doc_match:
                    doc_num = doc_match.group(1).strip()
                
                all_cc_rows = []
                
                # 3. ดึงตารางจากทุกหน้า
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        # กรองเอาเฉพาะแถวที่มีข้อมูล
                        cleaned_table = [row for row in table if any(cell for cell in row)]
                        if not cleaned_table:
                            continue
                            
                        # เช็กหัวตารางคร่าวๆ ว่าใช่ตาราง CC ไหม
                        header_row = " ".join([str(cell).lower() for cell in cleaned_table[0] if cell])
                        if "catch certificate" in header_row or "number" in header_row or "kg" in header_row:
                            # ข้ามแถวหัวตาราง ไปเอาข้อมูล
                            for row in cleaned_table[1:]:
                                clean_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                                
                                # หาเลข CC
                                cc_num = ""
                                for cell in clean_row:
                                    if "CATCH" in cell.upper() or len(cell) > 10:
                                        cc_num = cell
                                        break
                                
                                # หาตัวเลขน้ำหนัก
                                weights = []
                                for cell in clean_row:
                                     num_match = re.search(r"\d+[\.,]\d+", cell)
                                     if num_match:
                                         num_str = num_match.group().replace(',', '.')
                                         try:
                                             weights.append(float(num_str))
                                         except:
                                             pass
                                
                                catch_kg = weights[0] if len(weights) > 0 else 0.0
                                processed_kg = weights[1] if len(weights) > 1 else 0.0
                                
                                if cc_num:
                                     all_cc_rows.append({
                                         "Document_Number": doc_num,
                                         "CC_Number": cc_num,
                                         "Catch_Processed_KG": catch_kg,
                                         "Processed_Product_KG": processed_kg,
                                         "FilePath_For_Upload": f"C:\\TRACES_Docs\\{cc_num}.pdf"
                                     })

            if not all_cc_rows:
                st.warning("⚠️ สกัด Text ได้ แต่ไม่พบรูปแบบตาราง Catch Certificate ที่ตรงเงื่อนไข")
            else:
                df = pd.DataFrame(all_cc_rows)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                excel_data = output.getvalue()
                
                original_filename = os.path.splitext(uploaded_file.name)[0]
                export_filename = f"{original_filename}.xlsx"
                
                st.success(f"✅ สกัดข้อมูลสำเร็จ! พบ {len(all_cc_rows)} รายการ")
                st.download_button(
                    label=f"📥 คลิกเพื่อดาวน์โหลดไฟล์ Excel",
                    data=excel_data,
                    file_name=export_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
