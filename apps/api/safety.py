"""Bounded file intake: no external URL fetching or external model dependencies."""
import io
import json
import struct
import zipfile
import zlib
from defusedxml.ElementTree import fromstring as safe_xml
from fastapi import HTTPException

MAX_ASSET_BYTES = 15 * 1024 * 1024


def validate_glb(data: bytes):
    if len(data) < 20 or len(data) > MAX_ASSET_BYTES:
        raise HTTPException(422, "GLB 크기가 허용 범위를 벗어납니다.")
    magic, version, size = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or size != len(data):
        raise HTTPException(422, "유효한 glTF 2.0 GLB 헤더가 아닙니다.")
    offset, document, first = 12, None, True
    while offset < size:
        if offset + 8 > size:
            raise HTTPException(422, "GLB 청크 헤더가 잘렸습니다.")
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if length % 4 or offset + length > size or kind not in (0x4E4F534A, 0x004E4942):
            raise HTTPException(422, "잘못된 GLB 청크 구조입니다.")
        if first and kind != 0x4E4F534A:
            raise HTTPException(422, "첫 GLB 청크는 JSON이어야 합니다.")
        if kind == 0x4E4F534A:
            if document is not None or length > 2 * 1024 * 1024:
                raise HTTPException(422, "GLB JSON 청크가 중복되거나 너무 큽니다.")
            try:
                document = json.loads(data[offset:offset+length])
            except (ValueError, UnicodeError, RecursionError):
                raise HTTPException(422, "GLB JSON 해석 실패")
        offset += length
        first = False
    if not isinstance(document, dict) or not isinstance(document.get("asset"), dict) or document["asset"].get("version") != "2.0":
        raise HTTPException(422, "glTF 2.0 문서가 아닙니다.")
    for name in ("nodes", "meshes", "buffers", "bufferViews", "accessors", "images", "textures", "scenes"):
        items = document.get(name, [])
        if not isinstance(items, list) or len(items) > 20000 or any(not isinstance(item, dict) for item in items):
            raise HTTPException(422, "GLB 배열 필드 구조가 올바르지 않습니다.")
    def inspect(value, depth=0):
        if depth > 40:
            raise HTTPException(422, "GLB 중첩 제한 초과")
        if isinstance(value, dict):
            for key, v in value.items():
                if key == "uri" or key == "extensionsRequired":
                    raise HTTPException(422, "외부/내장 URI와 미검증 확장은 허용하지 않습니다. 자산을 GLB 바이너리에 포함하세요.")
                inspect(v, depth+1)
        elif isinstance(value, list):
            if len(value) > 100000:
                raise HTTPException(422, "GLB 배열 제한 초과")
            for v in value:
                inspect(v, depth+1)
    inspect(document)
    if len(document.get("nodes", [])) > 20000:
        raise HTTPException(422, "GLB 객체 수 제한 초과")
    for accessor in document.get("accessors", []):
        if not isinstance(accessor.get("count"), int) or not 0 <= accessor["count"] <= 5_000_000:
            raise HTTPException(422, "GLB 정점 수 제한 초과")
    return {"nodes": len(document.get("nodes", [])), "meshes": len(document.get("meshes", [])), "bytes": len(data), "structural_check": "passed", "malware_scan": "not_run"}


def validate_xlsx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            required={'[Content_Types].xml','xl/workbook.xml','_rels/.rels'}
            if not required <= {i.filename for i in infos}:
                raise ValueError('XLSX 필수 매니페스트 누락')
            if len(infos) > 150 or sum(i.file_size for i in infos) > 8_000_000:
                raise ValueError("압축 해제 크기 초과")
            for info in infos:
                if ".." in info.filename or info.filename.startswith(("/", "\\")) or info.file_size > max(100000, info.compress_size * 100):
                    raise ValueError("위험 압축 구조")
                if "vbaProject" in info.filename or "externalLinks" in info.filename:
                    raise ValueError("매크로/외부 링크 금지")
                if info.filename.endswith((".xml", ".rels")):
                    content = archive.read(info)
                    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
                        raise ValueError("XML 엔티티 금지")
                    safe_xml(content,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except (ValueError, zipfile.BadZipFile, RuntimeError, SyntaxError, KeyError, OSError, struct.error, zlib.error):
        raise HTTPException(422, "허용되지 않는 XLSX 압축/XML 구조입니다.")
