"""Bounded ZIP inspection and structural DOCX parsing; no archive is extracted."""

import io
import re
import stat
import unicodedata
import zipfile
import zlib
from pathlib import PurePosixPath
from typing import Any

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from .content_contracts import SceneContent
from .content_service import normalize, source_candidates
from .errors import DomainError
from .models import identifier
from .zip_names import readable_zip_name

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def checked_archive(data, *, expanded_limit=500 * 1024 * 1024, file_limit=1000):
    """Validate all paths and sizes before reading any members; return a caller-owned archive."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        members = archive.infolist()
        if len(members) > file_limit or sum(i.file_size for i in members) > expanded_limit:
            raise DomainError(422, "archive_limit", "压缩包展开后超过当前限制，请拆分资料包")
        seen = set()
        for item in members:
            name = readable_zip_name(item.orig_filename, utf8=bool(item.flag_bits & 0x800))
            path = PurePosixPath(name)
            parts = name.rstrip("/").split("/")
            identity = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (
                not name
                or "\x00" in name
                or "\\" in name
                or path.is_absolute()
                or re.match(r"^[A-Za-z]:", name)
                or any(p in {"", ".", ".."} for p in parts)
                or identity in seen
                or len(name) > 512
                or len(parts) > 8
                or mode not in {0, stat.S_IFREG, stat.S_IFDIR}
                or item.flag_bits & 1
            ):
                raise DomainError(
                    422, "archive_unsafe", "压缩包包含不安全路径、链接或重复文件，请修正后上传"
                )
            if item.file_size > 1024 * 1024 and item.file_size > max(item.compress_size, 1) * 200:
                raise DomainError(422, "archive_limit", "压缩包解压比例异常，请拆分或重新打包")
            seen.add(identity)
        return archive
    except (zipfile.BadZipFile, OSError, ValueError):
        raise DomainError(422, "archive_invalid", "压缩包无法读取，请重新打包") from None


def member_bytes(archive, name, limit):
    """Read at most the declared parser budget and validate CRC through ZipFile."""
    try:
        info = archive.getinfo(name)
        if info.file_size > limit:
            raise DomainError(422, "archive_limit", "文件展开后超过读取限制，请拆分资料")
        with archive.open(info) as stream:
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise DomainError(422, "archive_limit", "文件超过读取限制")
            return data
    except (KeyError, zipfile.BadZipFile, RuntimeError, EOFError, OSError, zlib.error):
        raise DomainError(422, "docx_invalid", "DOCX无法读取，请检查文件后重试") from None


def xml_document(data):
    """Reject DTD/entity expansion rather than handing document content to an external resolver."""
    try:
        return ET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise DomainError(422, "docx_invalid", "DOCX结构无法读取，请使用填写示例") from None


def paragraph_text(element):
    """Preserve run order and explicit tabs/breaks without translating or rewriting text."""
    result = []
    for node in element.iter():
        if node.tag == W + "t":
            result.append(node.text or "")
        elif node.tag == W + "tab":
            result.append("\t")
        elif node.tag in {W + "br", W + "cr"}:
            result.append("\n")
    return "".join(result)


def heading_styles(archive):
    """Recognize real outline-level-one headings, including localized Word style names."""
    ids = {"Heading1", "heading1"}
    if "word/styles.xml" not in archive.namelist():
        return ids
    root = xml_document(member_bytes(archive, "word/styles.xml", 2 * 1024 * 1024))
    for style in root.findall(W + "style"):
        level = style.find("./" + W + "pPr/" + W + "outlineLvl")
        if level is not None and level.get(W + "val") == "0":
            ids.add(style.get(W + "styleId", ""))
    return ids


def parse_docx_section(name, elements):
    """Parse exactly one explicit H1 section; malformed neighbors cannot discard this card."""
    current: dict[str, Any] = {"name": name, "dialogue": [], "vocabulary": [], "chunks": []}
    section = ""
    source_hints = []
    for element in elements:
        if element.tag == W + "p":
            text = paragraph_text(element).strip()
            if text in {"场景对话", "重点词汇", "语块", "语块（选填）", "语块(选填)"}:
                section = "语块" if text.startswith("语块") else text
            elif text:
                raise DomainError(
                    422, "docx_structure", "卡片正文请使用固定小标题和表格，不按任意段落猜测配对"
                )
        elif element.tag == W + "tbl":
            if current is None or not section:
                raise DomainError(422, "docx_structure", "请先填写一级卡片标题和对应小标题")
            rows = []
            for row in element.findall(W + "tr"):
                cells = [
                    "\n".join(paragraph_text(p) for p in cell.findall(W + "p")).strip()
                    for cell in row.findall(W + "tc")
                ]
                rows.append(cells)
            if not rows:
                continue
            headers = [re.sub(r"[（(].*", "", x).strip() for x in rows[0]]
            required = {
                "场景对话": ["人物", "英文", "中文"],
                "重点词汇": ["词汇", "本句释义"],
                "语块": ["英文", "中文释义"],
            }[section]
            if headers[: len(required)] != required:
                raise DomainError(
                    422,
                    "docx_structure",
                    "表格列名不符合填写示例，请核对人物、中英文或本句释义",
                )
            for row in rows[1:]:
                if not any(row):
                    continue
                if len(row) != len(headers):
                    raise DomainError(422, "docx_structure", "表格存在合并单元格，请按示例拆分")
                values = dict(zip(headers, row, strict=True))
                if section == "场景对话":
                    current["dialogue"].append(
                        {
                            "id": identifier(),
                            "speaker": values["人物"],
                            "english": values["英文"],
                            "chinese": values["中文"],
                        }
                    )
                elif section == "重点词汇":
                    word: dict[str, Any] = {
                        "id": identifier(),
                        "english": values["词汇"],
                        "meaning": values["本句释义"],
                        "phonetic": values.get("音标", ""),
                    }
                    current["vocabulary"].append(word)
                    source_hints.append((current, word, values.get("对应英文原句", "")))
                else:
                    current["chunks"].append(
                        {
                            "id": identifier(),
                            "english": values["英文"],
                            "chinese": values["中文释义"],
                        }
                    )
    for content, word, hint in source_hints:
        if hint:
            lines = [line for line in content["dialogue"] if line["english"] == hint]
            candidates = source_candidates(lines, word["english"])
            if len(candidates) == 1:
                word["source"] = candidates[0]
    try:
        return normalize(SceneContent.model_validate(current))
    except ValueError:
        raise DomainError(
            422, "docx_structure", "资料字段过长或数量超过限制，请拆分后重试"
        ) from None


def parse_docx_items(data, *, card_limit=50):
    """Retain one result per explicit H1, while rejecting corrupt archives/XML as a whole."""
    try:
        archive = checked_archive(data, expanded_limit=30 * 1024 * 1024, file_limit=300)
    except DomainError as error:
        raise DomainError(422, "docx_invalid", "DOCX无法读取，请使用填写示例") from error
    with archive:
        root = xml_document(member_bytes(archive, "word/document.xml", 8 * 1024 * 1024))
        styles = heading_styles(archive)
        body = root.find(W + "body")
        if body is None:
            raise DomainError(422, "docx_invalid", "DOCX缺少正文")
        sections: list[tuple[str, list]] = []
        for element in body:
            is_heading = False
            text = ""
            if element.tag == W + "p":
                text = paragraph_text(element).strip()
                style = element.find("./" + W + "pPr/" + W + "pStyle")
                level = element.find("./" + W + "pPr/" + W + "outlineLvl")
                is_heading = (style is not None and style.get(W + "val") in styles) or (
                    level is not None and level.get(W + "val") == "0"
                )
            if is_heading and text:
                if len(sections) >= card_limit:
                    raise DomainError(
                        422, "import_card_limit", "本批卡片数量超过当前限制，请拆分资料"
                    )
                sections.append((text, []))
            elif sections:
                sections[-1][1].append(element)
            elif element.tag == W + "tbl":
                raise DomainError(422, "docx_structure", "请先填写一级卡片标题和对应小标题")
        if not sections:
            raise DomainError(422, "docx_structure", "未找到合法的一级卡片标题，请使用填写示例")
        results = []
        for index, (name, elements) in enumerate(sections):
            try:
                content = parse_docx_section(name, elements)
                results.append({"content": content, "readable": True, "issues": []})
            except DomainError as error:
                # Show only a bounded title for an unreadable card; retain the original source file.
                results.append(
                    {
                        "content": normalize(SceneContent(name=name[:160])),
                        "readable": False,
                        "issues": [
                            {
                                "field": "source",
                                "code": error.code,
                                "message": f"第{index + 1}张卡片：{error.message}",
                            }
                        ],
                    }
                )
        return results


def parse_docx(data, *, card_limit=50):
    """Strict single-folder parser; batch DOCX callers consume per-card results instead."""
    items = parse_docx_items(data, card_limit=card_limit)
    for item in items:
        if not item["readable"]:
            issue = item["issues"][0]
            raise DomainError(422, issue["code"], issue["message"])
    return [item["content"] for item in items]
