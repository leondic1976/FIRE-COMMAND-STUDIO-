"""Render every synthetic AAR page and check key evidence text and page boxes."""
import json
import re
from pathlib import Path
import pymupdf


def check():
    source=Path('output/pdf/synthetic-aar-verification.pdf')
    folder=Path('artifacts/browser/aar-pages-final')
    folder.mkdir(parents=True,exist_ok=True)
    with pymupdf.open(source) as document:
        text=''.join(page.get_text() for page in document)
        required=['사후강평','발행 시점','대체근무','개선과제','평가관 승인','GUI 합성 교대 절차 검증','대체·인계 단계 변경']
        compact=lambda value:re.sub(r'\s+','',value)
        missing=[value for value in required if compact(value) not in compact(text)]
        if missing:raise ValueError(f'Missing printed evidence: {missing}')
        clipped=[]
        for index,page in enumerate(document):
            for block in page.get_text('blocks'):
                if block[0]<-1 or block[1]<-1 or block[2]>page.rect.width+1 or block[3]>page.rect.height+1:
                    clipped.append(index+1)
            page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(folder/f'aar-{index+1:02}.png'))
        if clipped:raise ValueError(f'Text exceeds page boxes: {clipped}')
        result={'synthetic_only':True,'pages':len(document),'renderer':'PyMuPDF '+pymupdf.__version__,
                'required_text_present':True,'text_outside_page_boxes':clipped,'visual_review_required':True,
                'pdf_bytes':source.stat().st_size}
    Path('artifacts/browser/pdf-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':check()
