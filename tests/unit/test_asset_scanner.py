import asyncio
import struct
import pytest
from apps.api.asset_scanner import LocalClamScanner,ScannerSettings


async def test_unconfigured_scanner_never_implicitly_succeeds():
    result=await LocalClamScanner(ScannerSettings()).scan(b'synthetic')
    assert result.status=='NOT_CONFIGURED'


@pytest.mark.parametrize('response,status',[(b'stream: OK\0','CLEAN'),(b'stream: Synthetic-Test FOUND\0','INFECTED'),(b'INSTREAM size limit exceeded ERROR\0','ERROR'),(b'OK\0','ERROR')])
async def test_synthetic_clamd_protocol_exact_success_and_errors(response,status):
    received=[]
    async def peer(reader,writer):
        assert await reader.readexactly(10)==b'zINSTREAM\0'
        data=b''
        while True:
            size=struct.unpack('!I',await reader.readexactly(4))[0]
            if not size:break
            data+=await reader.readexactly(size)
        received.append(data);writer.write(response);await writer.drain();writer.close();await writer.wait_closed()
    server=await asyncio.start_server(peer,'127.0.0.1',0)
    try:
        scanner=LocalClamScanner(ScannerSettings(approved=True,approval_reference='Synthetic protocol peer, not a real AV scan',port=server.sockets[0].getsockname()[1]))
        assert (await scanner.scan(b'synthetic\0'*20000)).status==status
        assert received==[b'synthetic\0'*20000]
    finally:server.close();await server.wait_closed()


async def test_scanner_connection_failure_is_not_clean():
    server=await asyncio.start_server(lambda reader,writer:None,'127.0.0.1',0)
    port=server.sockets[0].getsockname()[1];server.close();await server.wait_closed()
    result=await LocalClamScanner(ScannerSettings(approved=True,approval_reference='Synthetic error test',port=port,timeout_seconds=.05)).scan(b'synthetic')
    assert result.status=='ERROR'
