"""Isolated loopback SDK-failure QA; synthetic public key, never real provider.

Build to runtime/map-qa/dist with the explicit synthetic QA environment first.
Browser tests abort or fulfil every external request locally.
This fixture is not an institution approval or deployment entry point.
"""
import os
from pathlib import Path
import uvicorn
from apps.api import application


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    fixture=root/'runtime'/'map-qa'
    if not (fixture/'dist'/'index.html').is_file():raise SystemExit('Build the isolated synthetic map fixture first')
    os.environ['ALLOWED_ORIGINS']='http://127.0.0.1:8012'
    os.environ['COOKIE_SECURE']='false'
    os.environ['VITE_KAKAO_MAPS_APPROVED']='true' # QA branch coverage only.
    os.environ['VITE_KAKAO_JAVASCRIPT_KEY']='0'*32 # Fictional, not a credential.
    application.ROOT=fixture
    app=application.create_app('sqlite:///'+(fixture/'map-qa.db').as_posix(),True)
    uvicorn.run(app,host='127.0.0.1',port=8012,access_log=False)
