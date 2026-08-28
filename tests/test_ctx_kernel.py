"""Kiểm tra các bất biến của Context Card Kernel.

Mỗi test ánh xạ tới một bất biến trong docs/ctx_kernel.md §12.
Bất biến nào không có test ở đây thì coi như chưa được cưỡng chế.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.schemas.ctx_schema import (
    FORBIDDEN_CELLS,
    PROJECTION_BY_SOURCE,
    QUERY_STRING_CELL,
    WRITE_PERMISSIONS,
    Anchor,
    AssertOp,
    CardUpdate,
    Confidence,
    ContextCard,
    ConvSpan,
    Dimension,
    Fact,
    FactSource,
    Polarity,
    Projection,
    WorldSpan,
    valid_cells,
)

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "domains" / "hrm.yaml"
ANCHOR_KEYS = {a.value for a in Anchor}


def make_fact(anchor, dim, **kw) -> Fact:
    kw.setdefault("key", "k")
    kw.setdefault("value", "v")
    kw.setdefault("source", FactSource.USER_STATED)
    kw.setdefault("t_conv", ConvSpan(from_turn=1))
    if kw["source"] is FactSource.USER_STATED:
        kw.setdefault("evidence", "trích nguyên văn")
    return Fact(anchor=anchor, dim=dim, **kw)


# --------------------------------------------------------------------------
# I1 — fact chỉ nằm trong ô hợp lệ
# --------------------------------------------------------------------------


def test_grid_has_exactly_three_forbidden_cells():
    assert len(FORBIDDEN_CELLS) == 3
    assert len(Anchor) * len(Dimension) - len(FORBIDDEN_CELLS) == 17


@pytest.mark.parametrize("anchor,dim", sorted(FORBIDDEN_CELLS, key=str))
def test_forbidden_cell_is_rejected(anchor, dim):
    with pytest.raises(ValueError, match="ô bị cấm"):
        make_fact(anchor, dim)


def test_every_valid_cell_is_writable_by_someone():
    """Ô hợp lệ mà không nguồn nào ghi được là ô chết — lỗi thiết kế."""
    writable = set().union(*WRITE_PERMISSIONS.values())
    for anchor in Anchor:
        for cell in valid_cells(anchor):
            assert cell in writable, f"ô chết: {cell}"


# --------------------------------------------------------------------------
# I2 — chỉ target.topic đi vào chuỗi query (nguyên tắc N3)
# --------------------------------------------------------------------------


def test_query_string_cell_is_target_topic():
    assert QUERY_STRING_CELL == (Anchor.TARGET, Dimension.TOPIC)


def test_only_target_topic_goes_to_query_string():
    card = ContextCard(session_id="s")
    for anchor in Anchor:
        for anchor_, dim in valid_cells(anchor):
            card.facts.append(
                make_fact(
                    anchor_,
                    dim,
                    source=FactSource.USER_STATED
                    if (anchor_, dim) in WRITE_PERMISSIONS[FactSource.USER_STATED]
                    else FactSource.VERDICT,
                )
            )
    picked = card.query_string_facts()
    assert picked, "phải có ít nhất một fact vào chuỗi query"
    assert all(f.cell == QUERY_STRING_CELL for f in picked)


# --------------------------------------------------------------------------
# I3 / I4 — phân tầng nguồn tin
# --------------------------------------------------------------------------


def test_no_prose_source_exists():
    """Văn xuôi do model sinh không có đường vào card, kể cả gián tiếp."""
    assert "prose" not in {s.value for s in FactSource}


@pytest.mark.parametrize(
    "anchor", [Anchor.ASKER, Anchor.TARGET, Anchor.SOURCE]
)
def test_verdict_cannot_write_outside_dialogue(anchor):
    dim = next(d for _, d in valid_cells(anchor))
    with pytest.raises(ValueError, match="không được ghi vào"):
        make_fact(anchor, dim, source=FactSource.VERDICT)


def test_verdict_writes_dialogue_fine():
    f = make_fact(Anchor.DIALOGUE, Dimension.TOPIC, source=FactSource.VERDICT)
    assert f.cell in WRITE_PERMISSIONS[FactSource.VERDICT]


def test_verdict_projects_to_boost_only():
    """Verdict là model tự chấm mình -> không bao giờ sinh filter cứng."""
    assert PROJECTION_BY_SOURCE[FactSource.VERDICT] is Projection.BOOST
    grounded = {
        FactSource.SESSION,
        FactSource.EXTERNAL_SYSTEM,
        FactSource.USER_STATED,
        FactSource.RETRIEVED,
        FactSource.SQL_RESULT,
    }
    assert all(PROJECTION_BY_SOURCE[s] is Projection.HARD_FILTER for s in grounded)


def test_retrieved_cannot_write_asker():
    with pytest.raises(ValueError, match="không được ghi vào"):
        make_fact(Anchor.ASKER, Dimension.SPACE, source=FactSource.RETRIEVED)


def test_retrieved_may_write_target_topic_only():
    make_fact(Anchor.TARGET, Dimension.TOPIC, source=FactSource.RETRIEVED)
    with pytest.raises(ValueError):
        make_fact(Anchor.TARGET, Dimension.SPACE, source=FactSource.RETRIEVED)


def test_user_stated_requires_verbatim_evidence():
    with pytest.raises(ValueError, match="evidence"):
        Fact(
            anchor=Anchor.ASKER,
            dim=Dimension.SPACE,
            key="dept",
            value="X",
            source=FactSource.USER_STATED,
            t_conv=ConvSpan(from_turn=1),
        )


# --------------------------------------------------------------------------
# I5 — không có op xoá
# --------------------------------------------------------------------------


def test_no_delete_op_exists():
    ops = CardUpdate.model_json_schema(mode="validation")
    assert "delete" not in str(ops).lower().replace("deleted", "")


def test_close_is_the_only_way_to_end_a_fact():
    span = ConvSpan(from_turn=2)
    assert span.active is True
    closed = ConvSpan(from_turn=2, to_turn=9)
    assert closed.active is False


def test_conv_span_rejects_reversed_interval():
    with pytest.raises(ValueError):
        ConvSpan(from_turn=9, to_turn=2)


# --------------------------------------------------------------------------
# §3 — bốn trục thời gian tách biệt
# --------------------------------------------------------------------------


def test_two_time_axes_are_independent():
    """Biết ở lượt 9 rằng fact đúng từ tháng 7 — hai trục khác nhau."""
    f = make_fact(
        Anchor.ASKER,
        Dimension.SPACE,
        key="dept",
        value="Sản phẩm",
        t_conv=ConvSpan(from_turn=9),
        t_world=WorldSpan(**{"from": "2026-07-01"}),
        evidence="tôi chuyển sang phòng Sản phẩm",
    )
    assert f.t_conv.from_turn == 9
    assert f.t_world.from_ == "2026-07-01"


def test_world_span_accepts_partial_dates():
    for v in ("2026", "2026-03", "2026-03-01"):
        assert WorldSpan(**{"from": v}).from_ == v


# --------------------------------------------------------------------------
# §5 — polarity dùng được trên mọi ô, không chỉ chủ đề
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "anchor,dim",
    [
        (Anchor.TARGET, Dimension.TOPIC),
        (Anchor.SOURCE, Dimension.TIME),
        (Anchor.SOURCE, Dimension.SPACE),
        (Anchor.TARGET, Dimension.ATTRIBUTE),
    ],
)
def test_exclude_works_on_any_cell(anchor, dim):
    f = make_fact(anchor, dim, polarity=Polarity.EXCLUDE)
    assert f.polarity is Polarity.EXCLUDE


# --------------------------------------------------------------------------
# §6 — vòng đời suy ra từ neo
# --------------------------------------------------------------------------


def test_persistence_follows_anchor():
    assert make_fact(Anchor.ASKER, Dimension.SPACE).is_persistent
    assert make_fact(
        Anchor.DIALOGUE, Dimension.TOPIC, source=FactSource.VERDICT
    ).is_persistent
    assert not make_fact(
        Anchor.SOURCE, Dimension.IDENTITY, source=FactSource.RETRIEVED
    ).is_persistent


def test_user_stated_survives_topic_change():
    """Ngoại lệ có chủ ý: điều người dùng tự khai không bị bỏ tự động."""
    f = make_fact(Anchor.TARGET, Dimension.TOPIC, source=FactSource.USER_STATED)
    assert f.is_persistent


# --------------------------------------------------------------------------
# §11 — ops
# --------------------------------------------------------------------------


def test_card_update_parses_discriminated_ops():
    upd = CardUpdate.model_validate(
        {
            "ops": [
                {
                    "op": "assert",
                    "anchor": "asker",
                    "dim": "space",
                    "key": "dept",
                    "value": "Sản phẩm",
                    "source": "user_stated",
                    "t_world": {"from": "2026-07-01"},
                    "evidence": "tôi chuyển sang phòng Sản phẩm",
                },
                {"op": "close", "id": "asker.space.dept#0", "to_turn": 9},
                {
                    "op": "exclude",
                    "anchor": "target",
                    "dim": "topic",
                    "key": "subject",
                    "value": "nghỉ ốm",
                    "source": "user_stated",
                    "evidence": "không tính nghỉ ốm nhé",
                },
                {
                    "op": "open_gap",
                    "value": "chuyển phép tồn khi dưới 12 tháng",
                    "gap": "Mục 4.3 chỉ nêu trường hợp đủ 12 tháng",
                    "lead": "Phụ lục 2",
                },
                {"op": "resolve_gap", "id": "dialogue.topic#0"},
            ]
        }
    )
    assert len(upd.ops) == 5
    assert isinstance(upd.ops[0], AssertOp)


def test_fact_id_is_stable_and_addressable():
    card = ContextCard(session_id="s")
    f = make_fact(Anchor.ASKER, Dimension.SPACE, key="dept", seq=0)
    card.facts.append(f)
    assert f.id == "asker.space.dept#0"
    assert card.by_id("asker.space.dept#0") is f
    assert card.next_seq(Anchor.ASKER, Dimension.SPACE, "dept") == 1


def test_update_card_projection_hides_closed_facts():
    """I7: prompt của update_card không bao giờ thấy fact đã đóng khoảng."""
    card = ContextCard(session_id="s")
    card.facts.append(
        make_fact(Anchor.ASKER, Dimension.SPACE, key="dept", seq=0,
                  t_conv=ConvSpan(from_turn=2, to_turn=9))
    )
    card.facts.append(
        make_fact(Anchor.ASKER, Dimension.SPACE, key="dept", seq=1,
                  t_conv=ConvSpan(from_turn=9))
    )
    assert len(card.facts) == 2
    assert [f.seq for f in card.active()] == [1]


# --------------------------------------------------------------------------
# I6 — tên trường domain chỉ sống trong manifest
# --------------------------------------------------------------------------

DOMAIN_TERMS = [
    "nhan_vien", "phong_ban", "cap_bac", "loai_hop_dong",
    "nghi_phep", "ngay_vao_lam", "ma_nv", "vai_tro",
    "dept", "tenure", "seniority",
]


def test_no_domain_field_name_leaks_into_code():
    offenders = []
    for py in (REPO / "app").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for term in DOMAIN_TERMS:
            if re.search(rf"\b{term}\b", text):
                offenders.append(f"{py.relative_to(REPO)}: {term}")
    assert not offenders, "tên trường domain rò rỉ vào code: " + "; ".join(offenders)


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def test_manifest_parses():
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert m["domain"] == "hrm"
    assert set(m["consumers"]) == {"rag", "sql"}
    assert m["derive"] == ["D1", "D2", "D3"]


def test_manifest_uses_only_valid_cells():
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    for anchor_key in ANCHOR_KEYS & set(m):
        anchor = Anchor(anchor_key)
        for dim_key in m[anchor_key]:
            cell = (anchor, Dimension(dim_key))
            assert cell not in FORBIDDEN_CELLS, f"manifest dùng ô cấm: {cell}"


def test_manifest_declares_exactly_one_query_string_cell():
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    flagged = []
    for anchor_key in ANCHOR_KEYS & set(m):
        for dim_key, slots in m[anchor_key].items():
            for slot_name, spec in (slots or {}).items():
                if isinstance(spec, dict) and spec.get("to_query_string"):
                    flagged.append((anchor_key, dim_key, slot_name))
    assert len(flagged) == 1, f"phải có đúng một ô, thấy {flagged}"
    assert (flagged[0][0], flagged[0][1]) == (
        QUERY_STRING_CELL[0].value,
        QUERY_STRING_CELL[1].value,
    )


def test_manifest_slot_sources_respect_write_permissions():
    m = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    for anchor_key in ANCHOR_KEYS & set(m):
        anchor = Anchor(anchor_key)
        for dim_key, slots in m[anchor_key].items():
            cell = (anchor, Dimension(dim_key))
            for slot_name, spec in (slots or {}).items():
                declared = (spec or {}).get("source")
                if declared is None:
                    continue
                src = FactSource(declared)
                assert cell in WRITE_PERMISSIONS[src], (
                    f"{anchor_key}.{dim_key}.{slot_name} khai source={declared} "
                    f"nhưng nguồn đó không được ghi vào ô này"
                )


# --------------------------------------------------------------------------
# §14 — lưới phủ được card HR cũ
# --------------------------------------------------------------------------

LEGACY_MAPPING = {
    "chu_the.la_ai": (Anchor.ASKER, Dimension.IDENTITY),
    "chu_the.cap_bac": (Anchor.ASKER, Dimension.ATTRIBUTE),
    "chu_the.danh_tinh": (Anchor.ASKER, Dimension.IDENTITY),
    "pham_vi.phong_ban": (Anchor.ASKER, Dimension.SPACE),
    "pham_vi.loai_hop_dong": (Anchor.ASKER, Dimension.ATTRIBUTE),
    "pham_vi.tham_nien": (Anchor.ASKER, Dimension.TIME),
    "thong_tin.chu_de": (Anchor.TARGET, Dimension.TOPIC),
    "thong_tin.hanh_dong": (Anchor.TARGET, Dimension.TOPIC),
    "thong_tin.tai_lieu": (Anchor.SOURCE, Dimension.IDENTITY),
    "thong_tin.muc": (Anchor.SOURCE, Dimension.IDENTITY),
    "t_noi_dung": (Anchor.TARGET, Dimension.TIME),
    "rang_buoc_phu_dinh": (Anchor.TARGET, Dimension.TOPIC),
    "chua_tra_loi": (Anchor.DIALOGUE, Dimension.TOPIC),
}


def test_legacy_card_maps_onto_grid_without_gaps():
    for field, cell in LEGACY_MAPPING.items():
        assert cell not in FORBIDDEN_CELLS, f"{field} rơi vào ô cấm"
        assert cell[1] in Dimension


def test_grid_exposes_cells_the_legacy_card_lacked():
    """Giá trị của trừu tượng nằm ở đây: nó chỉ ra chỗ thiếu."""
    covered = set(LEGACY_MAPPING.values())
    assert (Anchor.SOURCE, Dimension.TIME) not in covered
    assert (Anchor.SOURCE, Dimension.SPACE) not in covered
