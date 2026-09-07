"""One cached editable PPTX and previews rendered from its exact bytes. No AI calls."""
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from pptx_compatibility import COMPATIBILITY_VERSION


def font_environment_key(directory=Path('/usr/local/share/fonts/report-fonts')):
    files = [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(directory.glob('*'))
             if p.is_file() and p.suffix.lower() in ('.ttf', '.ttc', '.otf')]
    return hashlib.sha256(json.dumps(files).encode()).hexdigest()


# Deployment restarts the backend after installing fonts and rebuilding fontconfig caches.
FONT_ENVIRONMENT = font_environment_key()


def _digest_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def artifact_key(report_type, report, storage_root):
    from non_oil_report_presentation import TEMPLATE_FILE
    source = (report.get('presentation') or {}).get('ppt_path') if report_type == 'non_oil' else None
    source_path = Path(storage_root) / source if source else TEMPLATE_FILE
    if not source_path.is_file():
        source_path = TEMPLATE_FILE
    source_hash = _digest_file(source_path) if report_type == 'non_oil' and source_path.is_file() else ''
    value = [COMPATIBILITY_VERSION, FONT_ENVIRONMENT, report_type, report, source_hash]
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def _read_artifact(directory, verify_pages=True):
    try:
        manifest = json.loads((directory / 'manifest.json').read_text())
        count = int(manifest['slide_count'])
        if manifest['version'] != COMPATIBILITY_VERSION or manifest.get('fonts') != FONT_ENVIRONMENT or count < 1:
            return None
        if not (directory / 'report.pptx').is_file():
            return None
        if verify_pages and not all((directory / f'slide-{index:02d}.jpg').is_file() for index in range(1,count + 1)):
            return None
        return manifest
    except (OSError,ValueError,KeyError,TypeError):
        return None


def build_artifact(report_type, report, storage_root):
    from non_oil_report_presentation import (build_non_oil_template_presentation,
        copy_existing_non_oil_presentation, _render_presentation_preview)
    from report_presentation import build_inspection_report_presentation
    key = artifact_key(report_type,report,storage_root)
    root = Path(storage_root) / 'report_presentations'
    root.mkdir(parents=True,exist_ok=True)
    directory = root / ('compatible-' + key)
    # Cross-process lock also covers simultaneous preview and download requests.
    with open(root / ('.compatible-' + key + '.lock'),'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        manifest = _read_artifact(directory)
        if manifest:
            os.utime(directory,None)
            return directory,manifest
        # Bound expensive LibreOffice work across Gunicorn processes and report types.
        with open(root / '.renderer.lock', 'a') as renderer_lock, tempfile.TemporaryDirectory(prefix='.ppt-build-',dir=root) as temp:
            fcntl.flock(renderer_lock, fcntl.LOCK_EX)
            staging = Path(temp)
            pptx = staging / 'report.pptx'
            if report_type == 'non_oil':
                result = copy_existing_non_oil_presentation(report,pptx,storage_root)
                if not result:
                    result = build_non_oil_template_presentation(report,staging,pptx,storage_root)
            else:
                result = build_inspection_report_presentation(report_type,report,storage_root,pptx)
            if not result.get('slide_files'):
                result['slide_files'] = _render_presentation_preview(pptx,staging)
            from pptx import Presentation
            if len(result['slide_files']) != len(Presentation(pptx).slides):
                raise RuntimeError('PPT预览页数与导出文件不一致，请重新准备。')
            manifest = {'version':COMPATIBILITY_VERSION,'artifact_key':key, 'fonts':FONT_ENVIRONMENT,
                        'slide_count':len(result['slide_files']),'sha256':_digest_file(pptx)}
            (staging / 'manifest.json').write_text(json.dumps(manifest))
            if directory.exists():
                shutil.rmtree(directory)
            os.replace(staging,directory)
        return directory,manifest


def attach_export(directory, manifest, destination):
    destination = Path(destination)
    shutil.copyfile(directory / 'report.pptx',destination)
    destination.with_suffix('.preview.json').write_text(json.dumps(manifest))


def export_preview_manifest(path, storage_root):
    if not path:
        return None
    try:
        manifest = json.loads(Path(path).with_suffix('.preview.json').read_text())
        key = manifest.get('artifact_key','')
        if not re.fullmatch('[a-f0-9]{64}',key) or manifest.get('version') != COMPATIBILITY_VERSION:
            return None
        directory = Path(storage_root) / 'report_presentations' / ('compatible-' + key)
        actual = _read_artifact(directory, verify_pages=False)
        return manifest if actual == manifest else None
    except (ValueError,OSError,TypeError):
        return None


def preview_slide_path(path, storage_root, page):
    manifest = export_preview_manifest(path,storage_root)
    if not manifest or not 1 <= page <= manifest['slide_count']:
        return None
    image = Path(storage_root) / 'report_presentations' / ('compatible-' + manifest['artifact_key']) / f'slide-{page:02d}.jpg'
    return image if image.is_file() else None


def cleanup_artifacts(storage_root, retention_days=30):
    """Only remove inactive derived previews, never saved source reports."""
    root = Path(storage_root) / 'report_presentations'
    cutoff = time.time() - retention_days * 86400
    for directory in root.glob('compatible-*'):
        if not re.fullmatch('compatible-[a-f0-9]{64}', directory.name):
            continue
        try:
            with open(root / ('.' + directory.name + '.lock'), 'a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                if directory.is_dir() and directory.stat().st_mtime < cutoff:
                    shutil.rmtree(directory)
        except OSError:
            continue
