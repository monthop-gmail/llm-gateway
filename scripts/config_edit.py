"""แก้ฟิลด์ใน model_info ของ litellm/config.yaml โดยไม่ทำลายคอมเมนต์

ทำไมไม่ใช้ yaml.dump: config มีคอมเมนต์ภาษาไทยอธิบายเหตุผลอยู่เต็มไฟล์
โหลดแล้ว dump กลับจะหายหมด จึงต้องแก้ทีละบรรทัด

ทำไมไม่ใช้ regex: เคยใช้แล้วพังจริง — regex เดิมสมมติว่าฟิลด์ที่จะแทนที่
อยู่ติดกับ `tags:` เสมอ พอสคริปต์อีกตัวแทรกฟิลด์คั่นตรงกลาง regex ก็หาไม่เจอ
แล้วเขียนซ้ำเข้าไปอีกชุด ผลคือ config มี status ซ้ำทั้ง 115 โมเดล และ YAML
เลือกอันท้ายสุดซึ่งเป็นค่าเก่า — ค่าที่เพิ่งวัดจึงไม่มีผลโดยไม่มีใครรู้

วิธีที่ใช้: หาขอบเขตของบล็อก model_info จาก indent แล้วลบ key เดิม
ทุกตำแหน่งในบล็อกนั้นก่อน ค่อยเขียนใหม่ต่อท้าย
"""
from __future__ import annotations

import re


def _quote(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = re.sub(r"\s+", " ", str(v)).replace('"', "'")
    return '"' + s + '"'


def set_fields(text: str, model: str, fields: dict) -> tuple[str, bool]:
    """เขียน fields ลงใน model_info ของ model — คืน (ข้อความใหม่, แก้ได้ไหม)

    ค่า None แปลว่า "ลบ key นี้ทิ้ง"
    """
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines)
                  if l.strip() == f"- model_name: {model}"), None)
    if start is None:
        return text, False

    # หา model_info: ของโมเดลนี้ (ต้องอยู่ก่อนโมเดลถัดไป)
    mi = None
    for i in range(start + 1, len(lines)):
        if lines[i].lstrip().startswith("- model_name:"):
            break
        if lines[i].strip() == "model_info:":
            mi = i
            break
    if mi is None:
        return text, False

    indent = len(lines[mi]) - len(lines[mi].lstrip()) + 2
    pad = " " * indent

    # ท้ายบล็อก = บรรทัดแรกที่ indent น้อยกว่า และไม่ใช่บรรทัดว่าง
    end = mi + 1
    while end < len(lines):
        l = lines[end]
        if not l.strip():
            break
        if len(l) - len(l.lstrip()) < indent:
            break
        end += 1

    body = lines[mi + 1:end]
    keys = set(fields)
    body = [l for l in body
            if (m := re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*):", l)) is None
            or m.group(1) not in keys]
    for k, v in fields.items():
        if v is not None:
            body.append(f"{pad}{k}: {_quote(v)}")

    return "\n".join(lines[:mi + 1] + body + lines[end:]), True
