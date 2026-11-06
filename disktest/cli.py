from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .engine import Settings, run_demo
from .report import verify_manifest, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="VEDT - güvenli yeniden geliştirme sürümü")
    sub = parser.add_subparsers(dest="command", required=True)
    for command, description in [("demo", "Güvenli Python dosya testi"), ("fio-demo", "Linux'ta gerçek fio dosya testi")]:
        demo = sub.add_parser(command, help=description)
        demo.add_argument("--size-mib", type=int, default=32)
        demo.add_argument("--mixed-operations", type=int, default=256)
        demo.add_argument("--timeout", type=float, default=120)
        demo.add_argument("--scenario", choices=["normal", "data-mismatch", "io-error", "timeout"], default="normal")
        demo.add_argument("--reports", type=Path, default=Path("reports"))
        demo.add_argument("--scratch-directory", type=Path,
                          help="Yeni geçici dosyanın oluşturulacağı klasör; mevcut dosya hedef alınmaz")
        demo.add_argument("--no-pdf", action="store_true")
        demo.add_argument("--quiet", action="store_true")
    verify = sub.add_parser("verify-report", help="Rapor dosyalarının SHA-256 özetlerini kontrol et")
    verify.add_argument("directory", type=Path)
    sub.add_parser("discover", help="Linux disk listesini salt okunur gösterir; test başlatmaz")
    smart = sub.add_parser("smart-info", help="SMART bilgilerini salt okunur gösterir")
    smart.add_argument("device", type=Path)
    raw = sub.add_parser('lab-raw-test', help='Yalnızca oluşturulmuş QEMU laboratuvar hedefinde yıkıcı test')
    raw.add_argument('--config', type=Path, required=True)
    raw.add_argument('--confirm-serial', required=True)
    raw.add_argument('--reports', type=Path, required=True)
    raw.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-report":
            errors = verify_manifest(args.directory)
            print("\n".join(errors) if errors else "Rapor dosyaları SHA-256 ile doğrulandı.")
            return 1 if errors else 0
        if args.command == "discover":
            from .discovery import discover
            print(json.dumps(discover(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "smart-info":
            from .smart import read_smart
            info = read_smart(args.device)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 1 if info["health"] == "FAIL" else 0 if info["health"] == "PASS" else 2
        if args.command == 'lab-raw-test':
            from .raw import load_settings, run_raw
            from .dashboard import Dashboard
            settings = load_settings(args.config)
            dashboard = Dashboard(settings.target)
            session = run_raw(settings, args.confirm_serial, args.reports,
                              (lambda _: None) if args.quiet else dashboard)
            directory = write_report(session, args.reports)
            dashboard.finish(session, directory)
            return {'WARNING': 0, 'FAIL': 1, 'INCOMPLETE': 2, 'CANCELLED': 130}[session['status']]
        settings = Settings(args.size_mib, args.mixed_operations, args.timeout, args.scenario)
        settings.validate()
        if not args.no_pdf:
            import reportlab  # Fail before I/O if dependency is missing.
        print("VEDT | DEMO | Yalnızca yeni geçici normal dosya")

        def event(row):
            if not args.quiet:
                percent = f"%{row['percent']:5.1f}" if row["percent"] is not None else "çalışıyor"
                speed = f"{row['mib_per_s']:.2f} MiB/sn" if row["mib_per_s"] is not None else "aşama sonunda"
                print(f"\r{row['stage']:<36} {percent} | {speed} | Sıcaklık: desteklenmiyor", end="", flush=True)

        if args.command == "fio-demo":
            from .fio import run_fio_demo
            session = run_fio_demo(settings, event, scratch=args.scratch_directory)
        else:
            session = run_demo(settings, event, scratch=args.scratch_directory)
        print(f"\nSonuç: {session['status']}")
        directory = write_report(session, args.reports, not args.no_pdf)
        print(f"Rapor: {directory.resolve()}")
        return {"WARNING": 0, "FAIL": 1, "INCOMPLETE": 2, "CANCELLED": 130}[session["status"]]
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f"Başlatılamadı: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
