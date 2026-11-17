"""Asset intake contracts: scanner results never imply rights or geometric approval."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field,model_validator
from .domain import AssetMapping,Contract,Source
from .requests import Versioned


class ConversionClaim(Contract):
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    output_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    tool_manifest_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    converter_version: str = Field(min_length=1,max_length=150)


class AssetProvenance(Contract):
    label: str = Field(min_length=1,max_length=160)
    creator: str = Field(min_length=1,max_length=160)
    license_scope: str = Field(min_length=3,max_length=1000)
    location_note: str = Field(default='',max_length=500)
    source: Source
    conversion_claim: ConversionClaim | None = None

    @model_validator(mode='after')
    def url_valid(self):
        if self.source.url:
            url=urlsplit(self.source.url)
            if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('출처 URL은 인증정보/쿼리 없는 HTTPS 주소여야 합니다.')
        return self


class ScanResult(Contract):
    status: Literal['CLEAN','INFECTED','ERROR','NOT_CONFIGURED']
    provider: str = Field(max_length=100)
    at: str
    detail: str = Field(max_length=200)


class AssetAttach(Versioned):
    mapping: AssetMapping
    rights_confirmed: bool
    note: str = Field(min_length=3,max_length=1000)


class AssetDetach(Versioned):
    note: str = Field(min_length=3,max_length=1000)
