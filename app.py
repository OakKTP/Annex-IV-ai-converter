import streamlit as st
import pandas as pd
import json
import io
import os
import base64
import time
import fitz  # PyMuPDF
from groq import Groq

st.set_page_config(page_title="TRACES AI Converter", page_icon="🐟")
st.title("🐟 TRACES - Annex IV AI (Groq - สแกนทีละหน้า)")
st.markdown("อัปโหลดไฟล์ PDF (สแกน) ระบบจะส่งให้ Groq อ่าน **ทีละ 1 หน้า** เพื่อป้องกันโควต้าคำตอบเต็ม")

api_key = st.text_input("🔑 ใส่ Groq API Key ของคุณ (ขึ้นต้นด้วย gsk_...):", type="password")
uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 เริ่มสกัดข้อมูล") and uploaded_file and api_key:
    with st.spinner("⚡ กำลังแปลงไฟล์และส่งให้ Groq อ่านทีละหน้า..."):
        try:
            pdf_bytes = uploaded_file.getvalue()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            client = Groq(api_key=api_key)
            all_extracted_cc = []
            main_document_data = {}
            
            progress_bar = st.progress(0)
            total_pages = len(doc)
            
            # --- ส่งให้ AI อ่านทีละ 1 หน้า ---
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150) # แปลงเป็นรูปภาพ
                b64_img = base64.b64encode(pix.tobytes("jpeg")).decode('utf-8')
                
                prompt_text = """
                คุณคือผู้เชี่ยวชาญด้านเอกสารศุลกากรยุโรป (EU TRACES)
                อ่านข้อมูลจากหน้าเอกสาร ANNEX IV นี้ และดึงข้อมูลออกมาในรูปแบบ JSON เท่านั้น
                ถ้าหน้านี้ไม่มีข้อมูลส่วนไหน ให้ใส่ค่าว่าง "" หรือ []
                {
                  "document_number": "",
                  "processed_product_cn_code": "",
                  "catch_certificates": [{"catch_certificate_number": "", "catch_description_code": "", "catch_processed_kg": 0.0, "processed_fishery_product_kg": 0.0}],
                  "processing_plant_name": "", "processing_plant_approval": "", "exporter_name": "",
                  "transport_vessel": "", "transport_document_ref": "",
                  "transport_containers": [{"container_number": "", "seal_number": ""}]
                }
                """
                
                content_payload = [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]

                response = client.chat.completions.create(
                    model="qwen/qwen3.8-27b", 
                    messages=[{"role": "user", "content": content_payload}],
                    temperature=0.0
                )
                
                raw_response = response.choices[0].message.content
                clean_json_str = raw_response.replace('```json', '').replace('```', '').strip()
                
                try:
                    data = json.loads(clean_json_str)
                    
                    # เก็บข้อมูลเอกสารส่วนบน (เช็กว่าถ้ามีข้อมูลให้เอามาเติม)
                    for key in ["document_number", "processed_product_cn_code", "processing_plant_name", "processing_plant_approval", "exporter_name", "transport_vessel", "transport_document_ref"]:
                        if data.get(key) and not main_document_data.get(key):
                            main_document_data[key] = data[key]
                            
                    if data.get("transport_containers") and not main_document_data.get("transport_containers"):
                        if data["transport_containers"][0].get("container_number"):
                            main_document_data["transport_containers"] = data["transport_containers"]
                            
                    # เก็บตาราง CC (เอามาต่อท้ายเรื่อยๆ)
                    if data.get('catch_certificates'):
                        all_extracted_cc.extend(data['catch_certificates'])
                except:
                    pass
                
                # อัปเดตแถบ Progress
                progress_bar.progress((page_num + 1) / total_pages)
                
                # พักเซิร์ฟเวอร์ 2 วินาที ป้องกันการโดนเตะข้อหาสแปม API
                if page_num < total_pages - 1:
                    time.sleep(2)

            # --- รวมข้อมูลทั้งหมดออกเป็น Excel ---
            rows = []
            containers = main_document_data.get('transport_containers', [])
            container_no = containers[0].get('container_number', '') if containers else ""
            seal_no = containers[0].get('seal_number', '') if containers else ""
            
            # กรองเฉพาะแถวที่ดึงเลข CC ได้จริงๆ
            valid_ccs = [cc for cc in all_extracted_cc if cc.get('catch_certificate_number')]
            
            for cc in valid_ccs:
                row = {
                    "Document_Number": main_document_data.get('document_number', ''),
                    "Processed_Product_CN_Code": main_document_data.get('processed_product_cn_code', ''),
                    "CC_Number": cc.get('catch_certificate_number', ''),
                    "Catch_Description_Code": cc.get('catch_description_code', ''),
                    "Catch_Processed_KG": cc.get('catch_processed_kg', 0.0),
                    "Processed_Product_KG": cc.get('processed_fishery_product_kg', 0.0),
                    "Processing_Plant_Name": main_document_data.get('processing_plant_name', ''),
                    "Processing_Plant_Approval": main_document_data.get('processing_plant_approval', ''),
                    "Exporter_Name": main_document_data.get('exporter_name', ''),
                    "Transport_Country": main_document_data.get('transport_country', ''),
                    "Transport_Vessel": main_document_data.get('transport_vessel', ''), 
                    "Transport_Document_Ref": main_document_data.get('transport_document_ref', ''),
                    "Container_Number": container_no,
                    "Seal_Number": seal_no,
                    "FilePath_For_Upload": f"C:\\TRACES_Docs\\{cc.get('catch_certificate_number', '')}.pdf"
                }
                rows.append(row)
            
            if not rows:
                st.warning("⚠️ ไม่สามารถสกัดตาราง Catch Certificate จากไฟล์นี้ได้")
            else:
                df = pd.DataFrame(rows)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                excel_data = output.getvalue()
                
                original_filename = os.path.splitext(uploaded_file.name)[0]
                export_filename = f"{original_filename}.xlsx"
                
                st.success(f"✅ สกัดข้อมูลสำเร็จ! พบ {len(valid_ccs)} รายการ")
                st.download_button(
                    label=f"📥 คลิกเพื่อดาวน์โหลดไฟล์: {export_filename}",
                    data=excel_data,
                    file_name=export_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
