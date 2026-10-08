import streamlit as st
import pandas as pd
import json
import tempfile
import io
import time
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai

# --- 1. กำหนดโครงสร้างข้อมูล (Schema) ---
class CatchCertificateRow(BaseModel):
    catch_certificate_number: str = Field(description="เลข CC เช่น CATCH.CC.FR.2026.0000763")
    catch_description_code: str = Field(description="ดึงเฉพาะตัวเลขรหัส เช่น 0303.42")
    catch_processed_kg: float = Field(description="น้ำหนัก Catch Processed(kg) เฉพาะตัวเลข")
    processed_fishery_product_kg: float = Field(description="น้ำหนัก Processed Fishery Product(kg) เฉพาะตัวเลข")

class TransportContainer(BaseModel):
    container_number: str = Field(description="เลขตู้คอนเทนเนอร์ เช่น TGBU5323505")
    seal_number: str = Field(description="เลขซีล เช่น ML-SC0045826")

class AnnexIVDocument(BaseModel):
    document_number: str = Field(description="เลข DOCUMENT NUMBER เช่น SFA/EU/IUU/REG/12567")
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
    transport_vessel: str = Field(description="ชื่อเรือขนส่ง หักเอาเฉพาะชื่อ ไม่เอาธง เช่น SPIL NITA")
    transport_document_ref: str = Field(description="Flight Number/Airway Bill Number เช่น 272826747")
    transport_containers: List[TransportContainer]

# --- 2. ออกแบบหน้าตาเว็บไซต์ (UI) ---
st.set_page_config(page_title="TRACES AI Converter", page_icon="🐟")
st.title("🐟 TRACES - Annex IV AI Converter")
st.markdown("อัปโหลดไฟล์ PDF (Annex IV) เพื่อแปลงเป็นไฟล์ Excel สำหรับให้ทีมงานนำไปใช้กับ Automa")

api_key = st.text_input("🔑 ใส่ Gemini API Key ของคุณ:", type="password")
uploaded_file = st.file_uploader("📂 เลือกไฟล์ PDF (Annex IV)", type=["pdf"])

if st.button("🚀 เริ่มสกัดข้อมูล") and uploaded_file and api_key:
    with st.spinner("AI กำลังอ่านเอกสาร... (อาจใช้เวลา 30-60 วินาที โปรดรอสักครู่)"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            client = genai.Client(api_key=api_key)
            uploaded_to_gemini = client.files.upload(file=tmp_file_path)
            
            prompt = """คุณคือผู้เชี่ยวชาญด้านเอกสารศุลกากรยุโรป (EU TRACES) อ่านไฟล์เอกสาร ANNEX IV (Processing Statement) และสกัดข้อมูล
            ข้อควรระวัง: สกัดตาราง Catch Certificate ให้ครบทุกแถว และตัวเลขน้ำหนักห้ามมีเครื่องหมายคอมม่า (,)"""
            
            # --- ระบบสู้ 503 (Auto-Retry) ---
            max_retries = 5 
            success = False
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        st.warning(f"⏳ คิวเซิร์ฟเวอร์เต็ม... ระบบกำลังพยายามส่งข้อมูลใหม่ครั้งที่ {attempt + 1}/{max_retries} (รอ 5 วินาที)")
                        time.sleep(5)
                        
                    response = client.models.generate_content(
                        model='gemini-3.8-flash', # เปลี่ยนไปใช้รุ่น Pro ที่คิวน้อยกว่า
                        contents=[uploaded_to_gemini, prompt],
                        config={'response_mime_type': 'application/json', 'response_schema': AnnexIVDocument}
                    )
                    success = True
                    break 
                    
                except Exception as e:
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        if attempt == max_retries - 1:
                            st.error("❌ เซิร์ฟเวอร์ล่มชั่วคราว รบกวนทิ้งไว้ 5 นาทีแล้วกดปุ่มใหม่อีกครั้งครับ")
                            st.stop()
                    else:
                        st.error(f"เกิดข้อผิดพลาดอื่น: {e}")
                        st.stop()
            
            if success:
                # --- 3. แปลงข้อมูลเป็น Excel ---
                data = json.loads(response.text)
                rows = []
                for cc in data.get('catch_certificates', []):
                    container_no = data.get('transport_containers')[0].get('container_number') if data.get('transport_containers') else ""
                    seal_no = data.get('transport_containers')[0].get('seal_number') if data.get('transport_containers') else ""
                    
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
                        "Transport_Vessel": data.get('transport_transport_vessel', data.get('transport_vessel')), 
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
                
                st.success("✅ สกัดข้อมูลสำเร็จเรียบร้อย!")
                st.download_button(
                    label="📥 คลิกเพื่อดาวน์โหลดไฟล์ Excel",
                    data=excel_data,
                    file_name="Extracted_Annex_IV.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
