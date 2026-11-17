"""Fail-closed local clamd INSTREAM adapter. No executable or user URL input."""
import asyncio
import os
import struct
from .asset_contracts import ScanResult
from .domain import Contract,utcnow
from pydantic import Field


class ScannerSettings(Contract):
    approved: bool=False
    approval_reference: str=Field(default='',max_length=200)
    port: int=Field(default=3310,ge=1,le=65535)
    timeout_seconds: float=Field(default=20,ge=0.05,le=60)

    @classmethod
    def from_env(cls):
        try:port=int(os.getenv('CLAMD_PORT','3310'))
        except ValueError:port=3310
        if not 1<=port<=65535:port=3310
        return cls(approved=os.getenv('ASSET_SCAN_APPROVED')=='true',approval_reference=os.getenv('ASSET_SCAN_APPROVAL_REF',''),port=port)


class LocalClamScanner:
    def __init__(self,settings=None):self.settings=settings or ScannerSettings.from_env()

    def status(self):
        return {'id':'local-clamd','configured':self.settings.approved and bool(self.settings.approval_reference.strip()),
                'real_scanner_verified':False,'reason':'승인된 로컬 검사기가 없으면 격리 상태를 유지합니다.'}

    async def scan(self,data):
        def result(status,detail):return ScanResult(status=status,provider='local-clamd',at=utcnow(),detail=detail)
        if not self.status()['configured']:return result('NOT_CONFIGURED','기관 승인 로컬 검사기 미설정')
        writer=None
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                reader,writer=await asyncio.open_connection('127.0.0.1',self.settings.port,limit=4096)
                writer.write(b'zINSTREAM\0')
                for start in range(0,len(data),65536):
                    chunk=data[start:start+65536]
                    writer.write(struct.pack('!I',len(chunk))+chunk);await writer.drain()
                writer.write(b'\0\0\0\0');await writer.drain()
                response=await reader.readuntil(b'\0')
                if response==b'stream: OK\0':return result('CLEAN','로컬 검사 통과. 이용권·형상 검토는 별도입니다.')
                if response.startswith(b'stream: ') and response.endswith(b' FOUND\0'):return result('INFECTED','악성코드 검사에서 탐지됨')
                return result('ERROR','검사기 응답 오류. 자료 반영 차단')
        except (OSError,TimeoutError,asyncio.IncompleteReadError,asyncio.LimitOverrunError):
            return result('ERROR','검사기 연결·시간·프로토콜 오류. 자료 반영 차단')
        finally:
            if writer:
                writer.close()
                try:await asyncio.wait_for(writer.wait_closed(),timeout=1)
                except (OSError,TimeoutError):pass
