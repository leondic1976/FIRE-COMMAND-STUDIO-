"""Bounded Windows offline worker process; no shell or interactive window.

The caller must use an approved, network-isolated conversion host. Job objects
enforce process count, memory, CPU and lifetime; they are not a network firewall.
"""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


class WorkerError(RuntimeError):pass


def private_work_directory(path:Path):
    """Set an exact protected DACL for the current user before writing IFC data."""
    if os.name!='nt':raise WorkerError('Windows 전용 변환 작업 디렉터리입니다.')
    system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
    try:result=subprocess.run([str(system/'whoami.exe'),'/user','/fo','csv','/nh'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError,subprocess.TimeoutExpired):raise WorkerError('작업 디렉터리 소유자 확인 실패') from None
    match=re.search(rb'S-1-(?:[0-9]+-)*[0-9]+',result.stdout)
    if result.returncode or not match:raise WorkerError('작업 디렉터리 소유자 SID를 확인할 수 없습니다.')
    sid=match[0].decode('ascii');advapi=ctypes.WinDLL('advapi32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[W.LPCWSTR,W.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(W.DWORD)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=W.BOOL
    advapi.SetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,ctypes.c_void_p];advapi.SetFileSecurityW.restype=W.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    descriptor=ctypes.c_void_p()
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(f'D:P(A;OICI;FA;;;{sid})',1,ctypes.byref(descriptor),None):
        raise WorkerError('작업 디렉터리 권한 계약 오류')
    try:
        if not advapi.SetFileSecurityW(str(path),0x80000004,descriptor):raise WorkerError('비공개 작업 디렉터리 권한 적용 실패')
    finally:kernel.LocalFree(descriptor)


class _Limits(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',W.DWORD),
              ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('active_processes',W.DWORD),
              ('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class _IO(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ['read_operations','write_operations','other_operations','read_bytes','write_bytes','other_bytes']]


class _Extended(ctypes.Structure):
    _fields_=[('basic',_Limits),('io',_IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]


class _Thread(ctypes.Structure):
    _fields_=[('size',W.DWORD),('usage',W.DWORD),('id',W.DWORD),('owner',W.DWORD),('priority',W.LONG),('delta',W.LONG),('flags',W.DWORD)]


class _Job:
    def __init__(self,seconds,memory_bytes):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        signatures={
            'CreateJobObjectW':([ctypes.c_void_p,W.LPCWSTR],W.HANDLE),
            'SetInformationJobObject':([W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD],W.BOOL),
            'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),
            'CloseHandle':([W.HANDLE],W.BOOL),
            'CreateToolhelp32Snapshot':([W.DWORD,W.DWORD],W.HANDLE),
            'Thread32First':([W.HANDLE,ctypes.POINTER(_Thread)],W.BOOL),
            'Thread32Next':([W.HANDLE,ctypes.POINTER(_Thread)],W.BOOL),
            'OpenThread':([W.DWORD,W.BOOL,W.DWORD],W.HANDLE),
            'ResumeThread':([W.HANDLE],W.DWORD),
        }
        for name,(args,result) in signatures.items():
            method=getattr(self.kernel,name);method.argtypes=args;method.restype=result
        self.handle=self.kernel.CreateJobObjectW(None,None)
        if not self.handle:raise WorkerError('격리 작업 객체를 만들 수 없습니다.')
        limits=_Extended();limits.basic.flags=0x2000|0x100|0x200|0x8|0x2
        limits.basic.active_processes=1;limits.basic.process_time=int(seconds*10_000_000)
        limits.process_memory=memory_bytes;limits.job_memory=memory_bytes
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise WorkerError('변환 프로세스 제한을 적용할 수 없습니다.')

    def start(self,process):
        if not self.kernel.AssignProcessToJobObject(self.handle,W.HANDLE(int(process._handle))):
            raise WorkerError('변환 프로세스의 격리 배정에 실패했습니다.')
        snapshot=self.kernel.CreateToolhelp32Snapshot(0x4,0)
        if snapshot in (None,ctypes.c_void_p(-1).value):raise WorkerError('변환 스레드 조회 실패')
        resumed=False
        try:
            entry=_Thread();entry.size=ctypes.sizeof(entry);more=self.kernel.Thread32First(snapshot,ctypes.byref(entry))
            while more:
                if entry.owner==process.pid:
                    thread=self.kernel.OpenThread(0x0002,False,entry.id)
                    if not thread:raise WorkerError('변환 스레드 접근 실패')
                    try:
                        if self.kernel.ResumeThread(thread)==0xFFFFFFFF:raise WorkerError('변환 스레드 시작 실패')
                        resumed=True
                    finally:self.kernel.CloseHandle(thread)
                more=self.kernel.Thread32Next(snapshot,ctypes.byref(entry))
        finally:self.kernel.CloseHandle(snapshot)
        if not resumed:raise WorkerError('변환 프로세스를 시작하지 못했습니다.')

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


def run_bounded(arguments,cwd:Path,seconds=60,memory_bytes=1024*1024*1024,output:Path|None=None,max_output=15*1024*1024):
    if os.name!='nt':raise WorkerError('이 변환 작업기는 Windows Job 환경용입니다. 승인된 별도 오프라인 작업기를 사용하세요.')
    if not 0.05<=seconds<=120 or not 32*1024*1024<=memory_bytes<=2*1024*1024*1024:raise WorkerError('변환 제한 설정 오류')
    # Fixed caller-supplied executable and arguments. Untrusted IFC bytes are
    # only read from the isolated input file; never included in the command.
    system_root=os.environ.get('SystemRoot',r'C:\Windows')
    environment={'SystemRoot':system_root,'WINDIR':system_root,'PATH':str(Path(system_root)/'System32'),
                 'TEMP':str(cwd),'TMP':str(cwd)}
    job=_Job(seconds,memory_bytes);process=None
    try:
        with tempfile.TemporaryFile() as log:
            process=subprocess.Popen(arguments,cwd=cwd,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW|0x00000004) # Win32 CREATE_SUSPENDED (not exported by subprocess)
            job.start(process);start=time.monotonic()
            while process.poll() is None:
                if time.monotonic()-start>seconds:raise WorkerError('오프라인 변환 제한시간을 초과했습니다.')
                if os.fstat(log.fileno()).st_size>65536:raise WorkerError('변환 진단 출력 제한을 초과했습니다.')
                if output and output.exists() and output.stat().st_size>max_output:raise WorkerError('변환 파일 크기 제한을 초과했습니다.')
                time.sleep(.02)
            if process.returncode!=0:raise WorkerError('오프라인 변환 도구가 오류로 종료했습니다. 입력/도구 버전을 확인하세요.')
            if os.fstat(log.fileno()).st_size>65536:raise WorkerError('변환 진단 출력 제한을 초과했습니다.')
            if output and (not output.is_file() or output.is_symlink() or output.stat().st_size>max_output):raise WorkerError('변환 결과가 없거나 크기·경로 제한을 초과했습니다.')
            log.seek(0);return log.read(65536)
    except OSError:raise WorkerError('변환 프로세스를 실행할 수 없습니다.') from None
    finally:
        job.close() # Kill-on-close includes a suspended or timed-out process.
        if process:
            if process.poll() is None:process.kill()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:pass
