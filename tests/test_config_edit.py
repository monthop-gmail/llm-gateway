"""ทดสอบตัวเขียน config — โมดูลนี้เคยทำ config พังมาแล้วโดยไม่มีอะไรฟ้อง

บั๊กเดิม: ตัวเขียนรุ่น regex สมมติว่าฟิลด์ที่จะแทนที่อยู่ติดกับ `tags:` เสมอ
พอสคริปต์อีกตัวแทรกฟิลด์คั่น มันหาของเดิมไม่เจอแล้วเขียนเพิ่มอีกชุด
ผลคือ status ซ้ำทั้ง 115 โมเดล และ YAML เลือกอันท้ายซึ่งเป็นค่าเก่า
การวัดทั้งรอบจึงไม่มีผล — ไม่มี error ไม่มี warning ไม่มีอะไรบอกเลย

test ชุดนี้จึงเน้นเรื่อง "เขียนซ้ำแล้วต้องไม่มี key ซ้ำ" เป็นหลัก
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from config_edit import set_fields

SAMPLE = """model_list:
  # คอมเมนต์อธิบายว่าทำไมถึงเลือกโมเดลนี้ — ห้ามหาย
  - model_name: a/one
    litellm_params:
      model: prov/one
    model_info:
      mode: "chat"
      tags: ["general"]
      status: "ok"

  - model_name: a/two
    litellm_params:
      model: prov/two
    model_info:
      mode: "chat"
      tags: ["fast"]

litellm_settings:
  fallbacks:
    - a/one: [a/two]
"""


def info(text: str, name: str) -> dict:
    cfg = yaml.safe_load(text)
    return next(m["model_info"] for m in cfg["model_list"] if m["model_name"] == name)


def keys_in_block(text: str, name: str) -> list[str]:
    """คีย์ตามที่ปรากฏจริงในไฟล์ — yaml.safe_load จะยุบของซ้ำให้ จับซ้ำไม่ได้"""
    lines = text.split("\n")
    start = next(i for i, x in enumerate(lines) if x.strip() == f"- model_name: {name}")
    out, seen_mi = [], False
    for line in lines[start + 1:]:
        if line.lstrip().startswith("- model_name:") or not line.strip():
            break
        if line.strip() == "model_info:":
            seen_mi = True
            continue
        if seen_mi and line.startswith("      ") and ":" in line:
            out.append(line.strip().split(":")[0])
    return out


def test_เพิ่มฟิลด์ใหม่():
    out, ok = set_fields(SAMPLE, "a/two", {"status": "ok"})
    assert ok
    assert info(out, "a/two")["status"] == "ok"


def test_ทับฟิลด์เดิมไม่สร้างของซ้ำ():
    out, _ = set_fields(SAMPLE, "a/one", {"status": "dead"})
    assert info(out, "a/one")["status"] == "dead"
    assert keys_in_block(out, "a/one").count("status") == 1


def test_เขียนซ้ำสิบรอบยังเหลือคีย์เดียว():
    """นี่คือเคสที่บั๊กเดิมพัง — สคริปต์วัดผลรันซ้ำทุกวัน"""
    out = SAMPLE
    for i in range(10):
        out, _ = set_fields(out, "a/one", {"status": f"v{i}", "status_checked_at": "t"})
    assert keys_in_block(out, "a/one").count("status") == 1
    assert keys_in_block(out, "a/one").count("status_checked_at") == 1
    assert info(out, "a/one")["status"] == "v9"


def test_มีฟิลด์อื่นแทรกคั่นก็ยังทับถูกตัว():
    """สาเหตุตรง ๆ ของบั๊กเดิม: ฟิลด์เป้าหมายไม่ได้อยู่ติดกับ tags: แล้ว"""
    out, _ = set_fields(SAMPLE, "a/one", {"verified_max_prompt": 1000})
    out, _ = set_fields(out, "a/one", {"status": "rate_limited"})
    assert keys_in_block(out, "a/one").count("status") == 1
    assert info(out, "a/one")["verified_max_prompt"] == 1000


def test_ค่า_None_คือลบทิ้ง():
    out, _ = set_fields(SAMPLE, "a/one", {"status": None})
    assert "status" not in info(out, "a/one")
    assert "status" not in keys_in_block(out, "a/one")


def test_ลบฟิลด์ที่ไม่มีอยู่แล้วไม่พัง():
    out, ok = set_fields(SAMPLE, "a/two", {"ไม่เคยมี": None})
    assert ok
    assert info(out, "a/two")["mode"] == "chat"


def test_ไม่เจอโมเดลต้องบอกว่าไม่สำเร็จ():
    out, ok = set_fields(SAMPLE, "ไม่มีจริง/x", {"status": "ok"})
    assert not ok
    assert out == SAMPLE


def test_ไม่แตะโมเดลอื่น():
    out, _ = set_fields(SAMPLE, "a/one", {"status": "dead"})
    assert info(out, "a/two") == {"mode": "chat", "tags": ["fast"]}


def test_คอมเมนต์ต้องไม่หาย():
    """เหตุผลทั้งหมดที่ไม่ใช้ yaml.dump อยู่ตรงนี้"""
    out, _ = set_fields(SAMPLE, "a/one", {"status": "dead"})
    assert "ห้ามหาย" in out


def test_ส่วนที่ไม่เกี่ยวต้องอยู่ครบ():
    out, _ = set_fields(SAMPLE, "a/one", {"status": "dead"})
    assert yaml.safe_load(out)["litellm_settings"]["fallbacks"] == [{"a/one": ["a/two"]}]


@pytest.mark.parametrize(
    "value,expect",
    [
        (13883, "verified_max_prompt: 13883"),          # ตัวเลขห้ามมีอัญประกาศ
        (True, "verified_max_prompt: true"),            # ไม่ใช่ True แบบ Python
        ("ok", 'verified_max_prompt: "ok"'),
    ],
)
def test_รูปแบบค่าแต่ละชนิด(value, expect):
    out, _ = set_fields(SAMPLE, "a/one", {"verified_max_prompt": value})
    assert expect in out


def test_ค่าที่เป็นลิสต์ต้องออกมาเป็นลิสต์จริง():
    """เคยพลาด: ส่ง tags เป็นลิสต์แล้วได้ string หน้าตาเหมือนลิสต์กลับมา

    ร้ายตรงที่ consumer ที่ทำ set(tags) จะไม่ error แต่ได้ตัวอักษรทีละตัว
    """
    out, _ = set_fields(SAMPLE, "a/one", {"tags": ["deprecated", "slow"]})
    got = info(out, "a/one")["tags"]
    assert isinstance(got, list), f"ได้ {type(got).__name__} แทนที่จะเป็น list"
    assert got == ["deprecated", "slow"]


def test_ลิสต์ว่าง():
    out, _ = set_fields(SAMPLE, "a/one", {"tags": []})
    assert info(out, "a/one")["tags"] == []


def test_ข้อความมีอัญประกาศคู่ต้องไม่ทำ_yaml_พัง():
    """ข้อความ error จาก provider มี " ปนมาเป็นปกติ"""
    msg = 'error: {"detail": "gone"} เมื่อ 2026-08-26'
    out, _ = set_fields(SAMPLE, "a/one", {"status_detail": msg})
    assert yaml.safe_load(out) is not None          # ต้อง parse ผ่าน
    assert "gone" in info(out, "a/one")["status_detail"]


def test_ข้อความหลายบรรทัดถูกยุบเป็นบรรทัดเดียว():
    out, _ = set_fields(SAMPLE, "a/one", {"status_detail": "บรรทัดหนึ่ง\nบรรทัดสอง"})
    assert yaml.safe_load(out) is not None
    assert "\n" not in info(out, "a/one")["status_detail"]


def test_เขียนโมเดลสุดท้ายที่ติดท้ายไฟล์():
    """บล็อกสุดท้ายไม่มีบรรทัดว่างปิดท้าย — ขอบเขตต้องยังหาถูก"""
    text = SAMPLE.split("litellm_settings:")[0].rstrip() + "\n"
    out, ok = set_fields(text, "a/two", {"status": "ok"})
    assert ok
    assert info(out, "a/two")["status"] == "ok"
    assert keys_in_block(out, "a/two").count("status") == 1


def test_config_จริงยังอ่านได้หลังแก้():
    """กันเคสที่ test ผ่านกับตัวอย่างเล็ก ๆ แต่พังกับไฟล์จริง 2,600 บรรทัด"""
    real = Path(__file__).resolve().parent.parent / "litellm/config.yaml"
    if not real.exists():
        pytest.skip("ไม่มี config จริงในสภาพแวดล้อมนี้")
    text = real.read_text()
    before = yaml.safe_load(text)
    name = before["model_list"][0]["model_name"]
    out, ok = set_fields(text, name, {"status": "ok", "status_checked_at": "t"})
    assert ok
    after = yaml.safe_load(out)
    assert len(after["model_list"]) == len(before["model_list"])
    assert keys_in_block(out, name).count("status") == 1
