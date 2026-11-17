import io
import json
import struct

import pytest
from PIL import Image
from apps.api.asset_validation import AssetValidationError,normalize_photo,validate_model
from tests.asset_fixtures import glb,photo


def document(data=None):
    data=data or glb();size=struct.unpack_from('<I',data,12)[0]
    return json.loads(data[20:20+size]),data[28+size:]


def test_generated_three_floor_geometry_and_private_extras_stripped():
    doc,binary=document();doc['extras']={'private':'MUST_NOT_LEAVE_INTAKE'}
    canonical,manifest=validate_model(glb(doc,binary))
    assert manifest.bounds==[[-2,0,-2],[2,9,2]] and manifest.triangles==12
    assert [node.index for node in manifest.nodes]==[0,1,2]
    assert b'MUST_NOT_LEAVE_INTAKE' not in canonical and b'generator' not in canonical
    assert validate_model(canonical)[1]==manifest


def test_photo_strips_text_metadata_and_keeps_pixels():
    raw=photo();canonical,manifest=normalize_photo(raw)
    assert b'SYNTHETIC_PRIVATE' in raw and b'SYNTHETIC_PRIVATE' not in canonical
    with Image.open(io.BytesIO(canonical)) as image:
        assert image.size==(64,32) and not image.info and not image.getexif()
    assert manifest.texture_pixels==2048


@pytest.mark.parametrize('change',[
    lambda doc:doc['nodes'][0].update(children=[0]),
    lambda doc:doc['nodes'][0].update(children=[1]),
    lambda doc:doc['nodes'][0].update(translation=[float('nan'),0,0]),
    lambda doc:doc['nodes'][0].update(scale=[0,1,1]),
    lambda doc:doc['nodes'][0].update(rotation=[0,0,0,0]),
    lambda doc:doc['nodes'][0].update(mesh=999),
    lambda doc:doc['scenes'][0].update(nodes=[0]),
    lambda doc:doc['buffers'][0].update(byteLength=999999),
    lambda doc:doc['bufferViews'][0].update(byteOffset=9999),
    lambda doc:doc['accessors'][0].update(byteOffset=1),
    lambda doc:doc['accessors'][0].update(count=999999),
    lambda doc:doc['meshes'][0]['primitives'][0].update(mode=1),
    lambda doc:doc.update(extensionsUsed=['KHR_draco_mesh_compression']),
    lambda doc:doc['buffers'][0].update(uri='https://127.0.0.1/private'),
])
def test_malformed_geometry_is_rejected_before_loader(change):
    doc,binary=document();change(doc)
    with pytest.raises(AssetValidationError):validate_model(glb(doc,binary))


def test_binary_nonfinite_vertices_and_out_of_range_indices_rejected():
    doc,binary=document()
    with pytest.raises(AssetValidationError):validate_model(glb(doc,struct.pack('<f',float('inf'))+binary[4:]))
    with pytest.raises(AssetValidationError):validate_model(glb(doc,binary[:48]+struct.pack('<H',99)+binary[50:]))


def test_photo_rejects_wrong_format_and_truncated_compression():
    for bad in [b'<svg><script>bad</script></svg>',b'PK\x03\x04',photo()[:40]]:
        with pytest.raises(AssetValidationError):normalize_photo(bad)


def test_large_photo_pixel_header_rejected_without_decompression():
    image=Image.new('1',(4097,1));out=io.BytesIO();image.save(out,format='PNG')
    with pytest.raises(AssetValidationError):normalize_photo(out.getvalue())
