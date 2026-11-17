"""Standalone Windows entrypoint; frozen builds include Python and web assets."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
import webbrowser

from apps.desktop import VERSION
from apps.desktop.runtime import AlreadyRunning, DesktopService, data_directory, load_settings, running_instance, stop_instance


def control_window(service):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('FIRE-COMMAND STUDIO')
    root.geometry('510x365')
    root.resizable(False, False)
    root.configure(background='#101724')
    tk.Label(root, text='FIRE-COMMAND STUDIO', background='#101724', foreground='#f0b47c', font=('맑은 고딕', 17, 'bold')).pack(pady=(24, 7))
    tk.Label(root, text='한 대의 운영 PC · 대형 화면 토론훈련', background='#101724', foreground='#e5edf6', font=('맑은 고딕', 11)).pack()
    tk.Label(root, text='이 PC에 기록을 저장합니다. 실제 출동망과 연결되지 않습니다.', background='#101724', foreground='#a9bbce', font=('맑은 고딕', 9)).pack(pady=11)
    ttk.Button(root, text='훈련 스튜디오 열기', command=lambda:webbrowser.open(service.url)).pack(fill='x', padx=65, pady=4)
    ttk.Button(root, text='기록·백업 폴더 열기', command=lambda:os.startfile(service.directory)).pack(fill='x', padx=65, pady=4)

    def backup():
        from datetime import datetime
        selected = filedialog.asksaveasfilename(parent=root, title='전체 훈련 백업 저장', initialdir=service.directory / 'backups', initialfile='studio-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.db', defaultextension='.db', filetypes=[('스튜디오 백업','*.db')])
        if not selected:
            return
        try:
            service.create_backup(selected)
            messagebox.showinfo('백업 저장', '백업과 무결성 확인용 manifest 파일을 함께 저장했습니다. 두 파일을 함께 보관하세요.', parent=root)
        except Exception:
            messagebox.showerror('백업 저장', '백업을 저장하지 못했습니다. 새 파일 이름과 저장 공간을 확인하세요.', parent=root)

    def restore():
        selected = filedialog.askopenfilename(parent=root, title='전체 훈련 백업 복원', initialdir=service.directory / 'backups', filetypes=[('스튜디오 백업','*.db')])
        if not selected or not messagebox.askyesno('백업 복원', '현재 훈련을 멈추고 선택한 시점으로 복원할까요? 현재 기록은 자동 백업으로 먼저 보존합니다.', parent=root):
            return
        try:
            service.restore_backup(selected)
            messagebox.showinfo('복원 완료', '선택한 백업을 복원했습니다. 스튜디오를 다시 열어 확인하세요.', parent=root)
            webbrowser.open(service.url)
        except Exception:
            messagebox.showerror('백업 복원', '복원을 완료하지 못했습니다. 백업·manifest의 무결성과 저장 폴더를 확인하세요. 기존 기록과 자동 백업은 보존합니다.', parent=root)

    ttk.Button(root, text='전체 훈련 백업 저장', command=backup).pack(fill='x', padx=65, pady=4)
    ttk.Button(root, text='백업에서 복원', command=restore).pack(fill='x', padx=65, pady=4)

    def close():
        if not messagebox.askyesno('스튜디오 종료', '실행 창을 종료할까요? 훈련을 멈추고 기록 정리를 마친 뒤 종료합니다.', parent=root):
            return
        try:
            service.stop()
        except RuntimeError:
            messagebox.showerror('종료 확인', '기록 정리가 끝나지 않았습니다. 잠시 후 다시 시도하세요.', parent=root)
            return
        root.destroy()

    ttk.Button(root, text='스튜디오 종료', command=close).pack(fill='x', padx=65, pady=4)
    root.protocol('WM_DELETE_WINDOW', close)

    def watch():
        if service.thread is None or not service.thread.is_alive():
            root.destroy()
        else:
            root.after(500, watch)
    root.after(500, watch)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='FIRE-COMMAND STUDIO Windows local application')
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--headless', action='store_true', help='서비스 검증용: 제어 창을 띄우지 않음')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--shutdown', action='store_true', help='같은 저장소의 실행본을 안전 종료')
    parser.add_argument('--backup-to', type=Path, help='전체 SQLite 백업과 manifest 저장')
    parser.add_argument('--restore-from', type=Path, help='검증된 백업 복원; 기존 실행 창을 먼저 종료')
    parser.add_argument('--self-check', action='store_true', help='설치 라이브러리의 합성 형식 처리 확인; AV 검사가 아님')
    parser.add_argument('--convert-ifc', type=Path, help='승인된 오프라인 IFC 변환; HTTP 서비스를 시작하지 않음')
    parser.add_argument('--output', type=Path, help='IFC 변환의 새 GLB 출력 경로')
    args = parser.parse_args()
    directory = data_directory(args.data_dir)
    if args.convert_ifc:
        if args.output is None:
            parser.error('--convert-ifc에는 --output 새파일.glb가 필요합니다.')
        load_settings(directory)
        import asyncio
        from scripts.convert_ifc import main as convert
        asyncio.run(convert(args.convert_ifc, args.output))
        return 0
    if args.shutdown:
        return 0 if stop_instance(directory) else 1
    service = DesktopService(directory, args.port)
    if args.backup_to:
        service.create_backup(args.backup_to)
        return 0
    if args.self_check:
        import io
        import platform
        from PIL import Image
        import openpyxl
        from apps.api.asset_validation import normalize_photo
        from apps.api.safety import validate_xlsx
        with Image.new('RGB', (8, 8), '#ff9944') as image:
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
        normalized, manifest = normalize_photo(image_bytes.getvalue())
        assert manifest.width == 8 and manifest.height == 8 and normalized.startswith(b'\x89PNG')
        workbook = openpyxl.Workbook()
        workbook.active.append(['synthetic', 'fixture'])
        archive = io.BytesIO()
        workbook.save(archive)
        workbook.close()
        validate_xlsx(archive.getvalue())
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'installation-check.json').write_text(json.dumps({'python':platform.python_version(),'png_normalization':True,'xlsx_structure':True,'synthetic_only':True,'av_scan_performed':False,'institutional_approval':False}, indent=2), encoding='utf-8')
        return 0
    try:
        service.start()
    except AlreadyRunning:
        if args.restore_from:
            return 3  # Never report a requested restore as completed by a peer.
        previous = running_instance(directory)
        if previous and not args.no_browser:
            webbrowser.open(previous['url'])
        return 0 if previous else 2
    try:
        if args.restore_from:
            service.restore_backup(args.restore_from)
            return 0
        if not args.no_browser:
            webbrowser.open(service.url)
        if args.headless:
            if sys.stdout is not None:
                print(json.dumps({'application':'fire-command-studio','version':VERSION,'url':service.url}), flush=True)
            def stop(*_):
                service.server.should_exit = True
            for sig in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(sig, stop)
            while service.thread.is_alive():
                time.sleep(.2)
        else:
            control_window(service)
    finally:
        service.stop()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        # Only error type/module and code locations; never request data/secrets.
        error = {'kind':type(exc).__name__, 'frames':[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(exc.__traceback__)]}
        if isinstance(exc, ImportError):
            error['module'] = exc.name
        try:
            selected = next((sys.argv[i+1] for i,arg in enumerate(sys.argv[:-1]) if arg == '--data-dir'), None)
            folder = data_directory(selected)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'last-startup-error.json').write_text(json.dumps(error, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
        if '--headless' not in sys.argv:
            import tkinter.messagebox
            tkinter.messagebox.showerror('FIRE-COMMAND STUDIO', '스튜디오를 실행하지 못했습니다. 설치 파일과 데이터 폴더 접근 권한을 확인해 주세요.')
        raise SystemExit(1) from None
