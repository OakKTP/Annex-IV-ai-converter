import streamlit as st
import pandas as pd
import json
import tempfile
import io
import time
import os
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai

# --- 1. กำหนดโครงสร้างข้อมูล (Schema) ---
class CatchCertificateRow(BaseModel):
    catch_certificate_number: str = Field(description="เลข CC เช่น CATCH.CC.FR.2026.0000763 หรือ SCN...")
    catch_description_code: str = Field(description="ดึงเฉพาะตัวเลขรหัส CN Code เช่น 0303.42")
    catch_processed_kg: float = Field(description="น้ำหนัก Catch Processed(kg) เฉพาะตัวเลข")
    processed_fishery_product_kg: float = Field(description="น้ำหนัก Processed Fishery Product(kg) เฉพาะตัวเลข")

class TransportContainer(BaseModel):
    container_number: str = Field(description="เลขตู้คอนเทนเนอร์ เช่น TGBU5323505")
    seal_number: str = Field(description="เลขซีล เช่น ML-SC0045826")

class AnnexIVDocument(BaseModel):
    document_number: str = Field(description="เลข DOCUMENT NUMBER สำคัญมาก ต้องตรงตามเอกสารเป๊ะๆ เช่น SFA/EU/IUU/REG/12627")
    processed_product_cn_code: str = Field(description="รหัส CN Code เช่น 16041438")
    catch_certificates: List[CatchCertificateRow]
    processing_plant_name: str = Field(description="ชื่อโรงงาน เช่น INDIAN OCEAN TUNA LTD")
    processing_plant_approval: str = Field(description="Approval number เช่น FC01")
    exporter_name: str = Field(description="ชื่อผู้ส่งออก เช่น MW BRANDS SEYCHELLES LTD")
    responsible_person_name: str = Field(description="ชื่อผู้รับผิดชอบโรงงาน เช่น Jamikara Techasaratoole")
    responsible_person_date: str = Field(description="วันที่เซ็น เช่น 09 JUL 2026")
    authority_name: str = Field(description="ชื่อหน่วยงานรัฐ เช่น SEYCHELLES FISHERIES AUTHORITY")
    authority_official_name: str = Field(description="ชื่อเจ้าหน้าที่รัฐ เช่น Lisa Memei")
    authority_date: str = Field(description="วันที่รัฐรับรอง เช่น 09.07.26")
    transport_country: str = Field(description="Country of Exportation เช่น SEYCHELLES")
    transport_port: str = Field(description="Port/Airport/Other Place of Departure เช่น VICTORIA")
    transport_vessel: str = Field(description="ชื่อเรือขนส่ง")
    transport_document_ref: str = Field(description="Flight Number/Airway Bill Number")
    transport_containers: List[TransportContainer]

# --- 2. ออกแบบหน้าตาเว็บไซต์ (UI) ---
st.set_page_config(page_title="TRACES AI Converter", page_icon="🐟")
st.title("🐟 TRACES - Annex IV AI (Gemini 1.5 Flash)")
st.markdown("ดึงข้อมูลจากไฟล์ PDF สแกน ด้วยโควต้า 1,500 ไฟล์/วัน (รองรับไฟล์หนาหลายหน้า)")

api_key = st.text_input("🔑 ใส่ Gemini API Key ของคุณ:", type="password")
uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 เริ่มสกัดข้อมูล") and uploaded_file and api_key:
    with st.spinner("AI กำลังสแกนไฟล์และดึงข้อมูล... (อาจใช้เวลาสักครู่)"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            client = genai.Client(api_key=api_key)
            uploaded_to_gemini = client.files.upload(file=tmp_file_path)
            
            # หน่วงเวลาให้เซิร์ฟเวอร์ Google โหลดไฟล์ PDF เล็กน้อย
            time.sleep(2)
            
            prompt = """
            คุณคือผู้เชี่ยวชาญด้านเอกสารศุลกากรยุโรป (EU TRACES) หน้าที่ของคุณคือดึงข้อมูลจากเอกสาร ANNEX IV (Processing Statement) ที่แนบมา
            ข้อควรระวัง: 
            1. Document Number คือเลขเอกสารด้านบนสุด (เช่น SFA/EU/IUU/REG/12627) ต้องเป๊ะห้ามผิด
            2. สกัดตาราง Catch Certificate ให้ครบทุกแถว ห้ามมีเครื่องหมายคอมม่า (,) ในตัวเลข
            3. ถ้าข้อมูลไหนไม่มีในเอกสาร ให้เว้นว่าง ("") ไว้
            """
            
            max_retries = 3 
            success = False
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        st.warning(f"⏳ ทีมงานกดถี่เกิน 15 ครั้ง/นาที... ระบบกำลังรอ 15 วินาทีเพื่อรีเซ็ตโควต้า (ครั้งที่ {attempt + 1}/{max_retries})")
                        time.sleep(15)
                        
                    response = client.models.generate_content(
                        model='gemini-1.5-flash', # โมเดลของแท้ โควต้า 1,500 ไฟล์/วัน
                        contents=[uploaded_to_gemini, prompt],
                        config={'response_mime_type': 'application/json', 'response_schema': AnnexIVDocument}
                    )
                    success = True
                    break 
                    
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        if attempt == max_retries - 1:
                            st.error("❌ คิวแน่นเกินไป รบกวนรอสัก 1 นาทีแล้วกดปุ่มสกัดข้อมูลใหม่ครับ")
                            st.stop()
                    else:
                        st.error(f"เกิดข้อผิดพลาดอื่น: {e}")
                        st.stop()
            
            if success:
                # --- 3. แปลงข้อมูล JSON เป็น Excel ---
                data = json.loads(response.text)
                rows = []
                for cc in data.get('catch_certificates', []):
                    container_no = ""
                    seal_no = ""
                    if data.get('transport_containers') and len(data['transport_containers']) > 0:
                        container_no = data['transport_containers'][0].get('container_number', "")
                        seal_no = data['transport_containers'][0].get('seal_number', "")
                    
                    row = {
                        "Document_Number": data.get('document_number', ''),
                        "Processed_Product_CN_Code": data.get('processed_product_cn_code', ''),
                        "CC_Number": cc.get('catch_certificate_number', ''),
                        "Catch_Description_Code": cc.get('catch_description_code', ''),
                        "Catch_Processed_KG": cc.get('catch_processed_kg', 0.0),
                        "Processed_Product_KG": cc.get('processed_fishery_product_kg', 0.0),
                        "Processing_Plant_Name": data.get('processing_plant_name', ''),
                        "Processing_Plant_Approval": data.get('processing_plant_approval', ''),
                        "Exporter_Name": data.get('exporter_name', ''),
                        "Responsible_Person_Name": data.get('responsible_person_name', ''),
                        "Responsible_Person_Date": data.get('responsible_person_date', ''),
                        "Authority_Name": data.get('authority_name', ''),
                        "Authority_Official_Name": data.get('authority_official_name', ''),
                        "Authority_Date": data.get('authority_date', ''),
                        "Transport_Country": data.get('transport_country', ''),
                        "Transport_Port": data.get('transport_port', ''),
                        "Transport_Vessel": data.get('transport_vessel', ''), 
                        "Transport_Document_Ref": data.get('transport_document_ref', ''),
                        "Container_Number": container_no,
                        "Seal_Number": seal_no,
                        "FilePath_For_Upload": f"C:\\TRACES_Docs\\{cc.get('catch_certificate_number', '')}.pdf"
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
