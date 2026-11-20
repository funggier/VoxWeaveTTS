# v4: ต้นแบบ Worker สำหรับโมเดล TTS จริง

ใน plugin/worker.py มีตัวอย่างการเชื่อมกับ MakHam, FastThaiG2P, Vachana, Kokoro, Melo, Supertonic และ Wayu โดยตัว Worker ไม่มีการ Import โมดูลภายใน VoxWeaveTTS Core

ผู้สร้างโมเดลจัดเตรียม plugin/adapter.json, assets/ ที่บรรจุน้ำหนักโมเดล และ runtime/wheels/ ที่บรรจุ Dependencies ทั้งหมด จากนั้นสร้าง .vwmodel v4 ด้วย scripts/build_vwmodel_v4.py

scripts/convert_all_models_to_v4.py เป็นตัวอย่างการแปลง Asset + Dependencies ที่มีอยู่เป็นแพ็กเกจ v4 แบบสตรีมและตรวจ SHA-256 จากต้นฉบับ การแปลงไม่ได้หมายความว่าได้รับอนุญาตให้แจกจ่ายโมเดลหรือ Wheel

โปรแกรม Core รู้จักเพียง Worker Protocol v1: synthesize รับข้อความและคืน PCM16 Mono + sample_rate โดยสร้าง Plugin เป็น Child Process ต่างหาก

โปรดใช้ตัวอย่างนี้เฉพาะเมื่อมีสิทธิ์ใช้และแจกจ่ายน้ำหนักโมเดล/Dependencies ของแพ็กเกจปลายทาง
