# 의존성 기록

`package-lock.json`과 `requirements.txt`로 개발에 사용한 버전을 기록한다. CI와 로컬의 `python scripts/dependency_inventory.py`는 네트워크 없이 JavaScript 잠금파일 항목과 설치된 Python 직접 의존성의 버전·라이선스 선언을 `artifacts/dependency-inventory.json`에 기록한다. Python 핀과 설치 버전이 다르면 실패한다.

이 기록은 취약점 스캔이나 기관의 라이선스 승인을 대신하지 않는다. Python 전이 의존성 전체의 재배포 조건도 기관 배포 패키지를 확정할 때 확인해야 한다. CI에는 `npm audit --audit-level=high`와 `python scripts/audit_python_dependencies.py`를 연결했다. YAML 구문과 Python 조회의 로컬 실행은 확인했지만 원격 CI 실행 결과는 아직 없다.

현재 설치 메타데이터에서 FastAPI·Pydantic·SQLAlchemy·openpyxl은 MIT, uvicorn은 BSD-3-Clause, defusedxml은 PSFL, psycopg2-binary는 ‘LGPL with exceptions’로 선언한다. 원문 고지는 각 배포 패키지의 LICENSE/메타데이터를 보존한다. 외부 지도·실제 사진·도면/BIM 권리는 오픈소스 코드의 라이선스와 별도로 DATA_PROVENANCE의 승인 경로를 따른다.

프로젝트 자체의 공개 라이선스는 소유자가 정하지 않았으므로 임의로 부여하지 않았다. 원격 GitHub 게시와 외부 배포도 수행하지 않았다.

선택적 화면/인쇄 QA 도구는 `requirements-browser.txt`의 Playwright1.62.0(Apache-2.0 선언)과 PyMuPDF1.27.2.3(AGPL3.0 또는 Artifex 상용 라이선스 선언)이다. 설치 메타데이터를 확인했으며 제품 API/웹 런타임에는 포함하지 않는다. 이 QA 도구의 재배포 조건 확인과 기관 승인을 완료했다는 뜻은 아니다.

2026-11-17 자산 단계에서 Pillow13.0.0([MIT-CMU 선언](https://pypi.org/project/pillow/13.0.0/))을 사용한다. Python 직접/보안 고정 선언19개와 JavaScript 잠금155개를 inventory로 기록한다. 선택적 네이티브 변환기는 공식 IfcConvert0.8.5(win64)이며 [해당 버전 소스 고지](https://raw.githubusercontent.com/IfcOpenShell/IfcOpenShell/ifcconvert-0.8.5/src/ifcconvert/IfcConvert.cpp)는 LGPL-3.0-or-later다. 고정 ZIP/파일 해시·출처는 ASSET_PIPELINE에 기록했다. 바이너리는 무시된 runtime에만 설치했고 제품에 재배포하지 않았다. 재배포 시 [COPYING.LESSER](https://raw.githubusercontent.com/IfcOpenShell/IfcOpenShell/ifcconvert-0.8.5/COPYING.LESSER), [COPYING](https://raw.githubusercontent.com/IfcOpenShell/IfcOpenShell/ifcconvert-0.8.5/COPYING)와 포함 라이브러리 고지/소스 제공 조건을 기관이 확인해야 한다.

`python scripts/audit_python_dependencies.py`는 설치된 프로젝트 의존성의 extras 포함 폐쇄 집합을 구하고 공식 PyPI 버전별 취약점 메타데이터를 TLS 검증 상태로 조회한다. 외부에 패키지 이름/버전만 전송하며 파일·키·명부를 보내지 않는다. 2026-11-17 조회는37개·조회 실패0·알려진 권고 패키지0이었다. 업데이트 전 결과는 artifacts에 보존했다. 이 조회는 모든 취약점/공급망·라이선스 인증을 보장하지 않는다. 핀 갱신 후 pip check와 전체192회귀가 통과했다.

영상 개발은 FFmpeg 공식 다운로드 안내에 연결된 Gyan Windows9.0.2 고정 배포본의 ffmpeg/ffprobe를 사용한다. [배포자 고지](https://www.gyan.dev/ffmpeg/builds/)는 static 빌드 GPLv3다. 원본 ZIP·출처/소스 링크/전체 파일 해시를 runtime에 보존했고 제품에 재배포하지 않았다. 고정 SHA256·준비 명령·기관 승인과 합성 도구 시험의 구분은 MEDIA_TIMELINE을 따른다. 이 기록은 기관 재배포·실제 보안/권리 승인이 아니다.
