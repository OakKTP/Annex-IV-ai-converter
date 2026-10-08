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
st.markdown
