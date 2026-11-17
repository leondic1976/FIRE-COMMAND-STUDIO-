import json
import struct
import io
import zipfile
import pytest
from apps.api.domain import check_condition
from apps.api.safety import MAX_ASSET_BYTES


@pytest.mark.parametrize('document',[None,[],{'asset':[]},{'asset':{'version':'2.0'},'nodes':1},{'asset':{'version':'2.0'},'accessors':[None]},{'asset':{'version':'2.0'},'images':{}},{'asset':{'version':'2.0'},'buffers':[{'uri':'data:application/octet-stream;base64,AAAA'}]}])
def test_glb_schema_fuzz_returns_controlled_rejection(client,document):
    data=json.dumps(document).encode();data+=b' '*((-len(data))%4)
    glb=struct.pack('<4sII',b'glTF',2,20+len(data))+struct.pack('<II',len(data),0x4E4F534A)+data
    assert client.post('/api/v1/assets/validate',files={'file':('fuzz.glb',glb)}).status_code==422


@pytest.mark.parametrize('node',[{'feature_id':'H01','field':[],'operator':'eq','value':1},{'feature_id':{},'field':'water','operator':'eq','value':1},{'feature_id':'H01','field':'smoke','operator':'gte','value':float('nan')},{'op':'AND','conditions':[None]},{'op':'OR','conditions':[]},{'op':'AND','conditions':'eval(code)'}])
def test_bad_condition_shapes_are_data_not_code(node):
    assert not check_condition(node)


def test_chunked_request_is_bounded(client):
    def chunks():
        for _ in range(17):yield b'x'*1024*1024
    response=client.post('/api/v1/auth/demo',content=chunks(),headers={'Content-Type':'application/json'})
    assert response.status_code==413


def test_malformed_xlsx_archive_returns_controlled_rejection(client):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('xl/worksheets/sheet1.xml','<worksheet/>')
    assert client.post('/api/v1/imports/roster',files={'file':('broken.xlsx',data.getvalue())}).status_code==422
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr('xl/workbook.xml','<workbook/>')
        archive.writestr('_rels/.rels','<Relationships/>')
    assert client.post('/api/v1/imports/roster',files={'file':('invalid-workbook.xlsx',data.getvalue())}).status_code==422


def test_utf16_xml_entity_in_xlsx_is_rejected(client):
    import openpyxl
    workbook=openpyxl.Workbook();workbook.active['A1']='SAFE'
    original=io.BytesIO();workbook.save(original);workbook.close()
    modified=io.BytesIO()
    with zipfile.ZipFile(original) as source,zipfile.ZipFile(modified,'w') as target:
        for name in source.namelist():
            data=source.read(name)
            if name=='xl/worksheets/sheet1.xml':
                text=data.decode('utf-8').replace('<t>SAFE</t>','<t>&synthetic;</t>')
                text='<!DOCTYPE worksheet [<!ENTITY synthetic "SYNTHETIC_ONLY">]>'+text
                data=text.encode('utf-16')
            target.writestr(name,data)
    assert client.post('/api/v1/imports/roster',files={'file':('entities.xlsx',modified.getvalue())}).status_code==422
