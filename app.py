import streamlit as st
import pandas as pd
import json
import io
import os
import base64
import fitz  # PyMuPDF สำหรับแปลง PDF เป็นรูป
from groq import Groq

# --- 1. ออกแบบหน้าตาเว็บไซต์ (UI) ---
st.set_page_config(page_title="TRACES AI Converter", page_icon="🐟")
st.title("🐟 TRACES - Annex IV AI (Groq Vision)")
st.markdown("อัปโหลดไฟล์ PDF (สแกน) เพื่อแปลงเป็นไฟล์ Excel อย่างรวดเร็วด้วย Groq")

api_key = st.text_input("🔑 ใส่ Groq API Key ของคุณ (ขึ้นต้นด้วย gsk_...):", type="password")
uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 เริ่มสกัดข้อมูล") and uploaded_file and api_key:
    with st.spinner("⚡ กำลังแปลงไฟล์และส่งให้ Groq AI อ่าน..."):
        try:
            # --- สเต็ป 1: แปลง PDF แต่ละหน้าเป็นรูปภาพ Base64 ---
            pdf_bytes = uploaded_file.getvalue()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            base64_images = []
            for page in doc:
                pix = page.get_pixmap(dpi=150) # ความละเอียดกำลังดี ไม่หนักเกินไป
                img_byte_arr = pix.tobytes("jpeg")
                b64_img = base64.b64encode(img_byte_arr).decode('utf-8')
                base64_images.append(b64_img)
            
            # --- สเต็ป 2: เตรียมคำสั่งและส่งรูปให้ Groq ---
            client = Groq(api_key=api_key)
            
            prompt_text = """
            คุณคือผู้เชี่ยวชาญด้านเอกสารศุลกากรยุโรป (EU TRACES)
            อ่านข้อมูลจากรูปภาพเอกสาร ANNEX IV (Processing Statement) และดึงข้อมูลออกมาในรูปแบบ JSON เท่านั้น
            ห้ามพิมพ์ข้อความอธิบายใดๆ ทั้งสิ้น ให้ตอบกลับมาเป็น JSON โครงสร้างตามนี้เป๊ะๆ:
            {
              "document_number": "",
              "processed_product_cn_code": "",
              "catch_certificates": [
                {
                  "catch_certificate_number": "",
                  "catch_description_code": "",
                  "catch_processed_kg": 0.0,
                  "processed_fishery_product_kg": 0.0
                }
              ],
              "processing_plant_name": "",
              "processing_plant_approval": "",
              "exporter_name": "",
              "responsible_person_name": "",
              "responsible_person_date": "",
              "authority_name": "",
              "authority_official_name": "",
              "authority_date": "",
              "transport_country": "",
              "transport_port": "",
              "transport_vessel": "",
              "transport_document_ref": "",
              "transport_containers": [
                {"container_number": "", "seal_number": ""}
              ]
            }
            ข้อควรระวัง: สกัดตาราง Catch Certificate ให้ครบทุกแถว, ตัวเลขน้ำหนักให้ตัดเครื่องหมายคอมม่าออก
            """
            
            # จัดรูปแบบข้อความและรูปภาพตามที่ Groq API ต้องการ
            content_payload = [{"type": "text", "text": prompt_text}]
            for b64 in base64_images:
                content_payload.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

            response = client.chat.completions.create(
                model="llama-3.2-90b-vision-preview", # โมเดลสายตาตัวท็อปของ Groq
                messages=[{"role": "user", "content": content_payload}],
                temperature=0.0
            )
            
            # --- สเต็ป 3: ทำความสะอาดและแปลง JSON เป็น Excel ---
            raw_response = response.choices[0].message.content
            # ทำความสะอาดกรณี AI แถม Markdown มาให้
            clean_json_str = raw_response.replace('```json', '').replace('```', '').strip()
            
            data = json.loads(clean_json_str)
            rows = []
            
            # ดึงตู้คอนเทนเนอร์แรก (ถ้ามี)
            containers = data.get('transport_containers', [])
            container_no = containers[0].get('container_number', '') if containers else ""
            seal_no = containers[0].get('seal_number', '') if containers else ""
            
            for cc in data.get('catch_certificates', []):
                row = {
                    "Document_Number": data.get('document_number'),
                    "Processed_Product_CN_Code": data.get('processed_product_cn_code'),
                    "CC_Number": cc.get('catch_certificate_number'),
                    "Catch_Description_Code": cc.get('catch_description_code'),
                    "Catch_Processed_KG": cc.get('catch_processed_kg'),
                    "Processed_Product_KG": cc.get('processed_fishery_product_kg'),
                    "Processing_Plant_Name": data.get('processing_plant_name'),
                    "Processing_Plant_Approval": data.get('processing_plant_approval'),
                    "Exporter_Name": data.get('exporter_name'),
                    "Responsible_Person_Name": data.get('responsible_person_name'),
                    "Responsible_Person_Date": data.get('responsible_person_date'),
                    "Authority_Name": data.get('authority_name'),
                    "Authority_Official_Name": data.get('authority_official_name'),
                    "Authority_Date": data.get('authority_date'),
                    "Transport_Country": data.get('transport_country'),
                    "Transport_Port": data.get('transport_port'),
                    "Transport_Vessel": data.get('transport_vessel'), 
                    "Transport_Document_Ref": data.get('transport_document_ref'),
                    "Container_Number": container_no,
                    "Seal_Number": seal_no,
                    "FilePath_For_Upload": f"C:\\TRACES_Docs\\{cc.get('catch_certificate_number')}.pdf"
                }
                rows.append(row)
            
            df = pd.DataFrame(rows)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            excel_data = output.getvalue()
            
            original_filename = os.path.splitext(uploaded_file.name)[0]
            export_filename = f"{original_filename}.xlsx"
            
            st.success("✅ สกัดข้อมูลสำเร็จเรียบร้อย!")
            st.download_button(
                label=f"📥 คลิกเพื่อดาวน์โหลดไฟล์: {export_filename}",
                data=excel_data,
                file_name=export_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
            # แสดงข้อมูลดิบที่ AI ตอบกลับมาเผื่อใช้ตรวจสอบเวลามีปัญหา
            with st.expander("ดูข้อความตอบกลับดิบจาก AI"):
                try:
                    st.write(raw_response)
                except:
                    pass
