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
st.title("🐟 TRACES - Annex IV AI (Groq Vision)")
st.markdown("อัปโหลดไฟล์ PDF (สแกน) เพื่อแปลงเป็นไฟล์ Excel อย่างรวดเร็วด้วย Groq")

api_key = st.text_input("🔑 ใส่ Groq API Key ของคุณ (ขึ้นต้นด้วย gsk_...):", type="password")
uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 เริ่มสกัดข้อมูล") and uploaded_file and api_key:
    with st.spinner("⚡ กำลังแปลงไฟล์และส่งให้ Groq AI อ่าน (ระบบกำลังทยอยอ่านทีละส่วน)..."):
        try:
            # 1. แปลง PDF เป็นรูปภาพ
            pdf_bytes = uploaded_file.getvalue()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            base64_images = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img_byte_arr = pix.tobytes("jpeg")
                b64_img = base64.b64encode(img_byte_arr).decode('utf-8')
                base64_images.append(b64_img)
            
            client = Groq(api_key=api_key)
            
            prompt_text = """
            คุณคือผู้เชี่ยวชาญด้านเอกสารศุลกากรยุโรป (EU TRACES)
            อ่านข้อมูลจากรูปภาพเอกสาร ANNEX IV (Processing Statement) และดึงข้อมูลออกมาในรูปแบบ JSON เท่านั้น
            โครงสร้าง JSON ตามนี้ (ถ้าหน้าไหนไม่มีข้อมูลส่วนไหน ให้ใส่ค่าว่าง ""):
            {
              "document_number": "",
              "processed_product_cn_code": "",
              "catch_certificates": [{"catch_certificate_number": "", "catch_description_code": "", "catch_processed_kg": 0.0, "processed_fishery_product_kg": 0.0}],
              "processing_plant_name": "", "processing_plant_approval": "", "exporter_name": "", "responsible_person_name": "", "responsible_person_date": "",
              "authority_name": "", "authority_official_name": "", "authority_date": "", "transport_country": "", "transport_port": "", "transport_vessel": "", "transport_document_ref": "",
              "transport_containers": [{"container_number": "", "seal_number": ""}]
            }
            """
            
            all_extracted_cc = []
            main_document_data = {}
            
            # 2. หั่นรูปภาพส่งทีละ 3 รูป เพื่อแก้ปัญหาจำกัดโควต้าภาพของ Groq
            chunk_size = 3
            total_chunks = (len(base64_images) + chunk_size - 1) // chunk_size
            
            progress_bar = st.progress(0)
            
            for i in range(0, len(base64_images), chunk_size):
                chunk = base64_images[i:i + chunk_size]
                current_chunk = (i // chunk_size) + 1
                
                content_payload = [{"type": "text", "text": prompt_text}]
                for b64 in chunk:
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                    })

                response = client.chat.completions.create(
                    model="qwen/qwen3.8-27b", 
                    messages=[{"role": "user", "content": content_payload}],
                    temperature=0.0
                )
                
                raw_response = response.choices[0].message.content
                clean_json_str = raw_response.replace('```json', '').replace('```', '').strip()
                
                try:
                    data = json.loads(clean_json_str)
                    
                    # เก็บข้อมูลหลักจากก้อนแรกที่มีข้อมูล
                    if not main_document_data and data.get("document_number"):
                        main_document_data = data
                        
                    # เก็บสะสมตาราง CC ทั้งหมด
                    if data.get('catch_certificates'):
                        all_extracted_cc.extend(data['catch_certificates'])
                except:
                    pass
                
                progress_bar.progress(current_chunk / total_chunks)
                
                # พัก 2 วินาทีกันเซิร์ฟเวอร์เตะ
                if current_chunk < total_chunks:
                    time.sleep(2)

            # 3. รวมข้อมูลทั้งหมดลง Excel
            if not main_document_data:
                main_document_data = {} # กันเหนียวกรณีอ่านข้อมูลหลักไม่เจอเลย

            rows = []
            containers = main_document_data.get('transport_containers', [])
            container_no = containers[0].get('container_number', '') if containers else ""
            seal_no = containers[0].get('seal_number', '') if containers else ""
            
            # กรองตารางที่อ่านได้เป็นค่าว่างทิ้ง
            valid_ccs = [cc for cc in all_extracted_cc if cc.get('catch_certificate_number')]
            
            for cc in valid_ccs:
                row = {
                    "Document_Number": main_document_data.get('document_number', ''),
                    "Processed_Product_CN_Code": main_document_data.get('processed_product_cn_code', ''),
                    "CC_Number": cc.get('catch_certificate_number', ''),
                    "Catch_Description_Code": cc.get('catch_description_code', ''),
                    "Catch_Processed_KG": cc.get('catch_processed_kg', 0.0),
                    "Processed_
