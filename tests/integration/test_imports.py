import io
import openpyxl


HEADERS=['person_id','display_name','role_id','effective_from','effective_to','shift_id','backups']
ROW=['person-import','가상 가져오기 요원','safety_officer','2026-11-16T09:00:00+09:00','2026-11-16T18:00:00+09:00','A','']


def test_csv_and_xlsx_import_are_validated_previews_not_silent_updates(client):
    csv=(','.join(HEADERS)+'\n'+','.join(ROW)).encode('utf-8-sig')
    book=openpyxl.Workbook();book.active.append(HEADERS);book.active.append(ROW)
    binary=io.BytesIO();book.save(binary);book.close()
    for name,data in [('roster.csv',csv),('roster.xlsx',binary.getvalue())]:
        r=client.post('/api/v1/imports/roster',files={'file':(name,data)})
        assert r.status_code==200,r.text
        assert r.json()['errors']==[] and len(r.json()['assignments'])==1
        assert r.json()['persons'][0]['display_name']=='가상 가져오기 요원'
        assert r.json()['saved'] is False
    assert len(client.get('/api/v1/exercises/exercise-demo').json()['exercise']['persons'])==10


def test_empty_or_over_dimensioned_roster_is_rejected(client):
    assert client.post('/api/v1/imports/roster',files={'file':('empty.csv',','.join(HEADERS).encode())}).status_code==422
    book=openpyxl.Workbook();book.active['A100000']='unexpected dimension'
    binary=io.BytesIO();book.save(binary);book.close()
    assert client.post('/api/v1/imports/roster',files={'file':('huge-dimension.xlsx',binary.getvalue())}).status_code==422
    long_field=('person_id,display_name,role_id,effective_from,effective_to,shift_id\n'+('x'*200000)).encode()
    assert client.post('/api/v1/imports/roster',files={'file':('oversized-field.csv',long_field)}).status_code==422
