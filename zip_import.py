"""Bounded, offline folder-per-tube ZIP preparation; never extract archive paths."""
import json
import hashlib
import stat
from pathlib import PurePosixPath
from uuid import uuid4
import zipfile

MAX_ARCHIVE = 250 * 1024**2
MAX_TOTAL = 512 * 1024**2
MAX_PHOTO = 10 * 1024**2
EXTENSIONS = {'.jpg':'.jpg', '.jpeg':'.jpg', '.png':'.png', '.webp':'.webp',
              '.heic':'.jpg', '.heif':'.jpg'}


class ImportError(ValueError):
    pass


def plan_archive(archive):
    groups = {}
    seen = set()
    total = 0
    entries = archive.infolist()
    if len(entries) > 2000:
        raise ImportError('ZIP contains too many entries (maximum 2,000).')
    for entry in entries:
        name = entry.filename.replace('\\', '/')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts):
            raise ImportError('ZIP contains an unsafe file path.')
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ImportError('ZIP links are not supported.')
        if entry.is_dir() or any(p.startswith('.') or p == '__MACOSX' for p in path.parts):
            continue
        suffix = path.suffix.lower()
        if suffix not in EXTENSIONS:
            if suffix in {'.tif', '.tiff', '.gif', '.bmp', '.avif'}:
                raise ImportError('Unsupported photo format: '+suffix+'. Use JPG, PNG, WebP or HEIC.')
            continue  # Ignore non-photo notes and system metadata.
        if len(path.parts) < 2:
            raise ImportError('Put each tube’s photos inside its own folder before making the ZIP.')
        if name.casefold() in seen:
            raise ImportError('ZIP contains duplicate photo paths.')
        seen.add(name.casefold())
        if entry.flag_bits & 1:
            raise ImportError('Password-protected ZIPs are not supported.')
        if not 0 < entry.file_size <= MAX_PHOTO:
            raise ImportError('Each photo must be nonempty and at most 10 MB.')
        total += entry.file_size
        if total > MAX_TOTAL:
            raise ImportError('Uncompressed photos exceed the 512 MB batch limit.')
        folder = str(path.parent)
        groups.setdefault(folder, []).append(entry)
        if len(groups[folder]) > 8:
            raise ImportError('Each tube folder can contain at most 8 photos: '+folder)
        if len(groups) > 100:
            raise ImportError('Maximum 100 tube folders per ZIP.')
    if not groups:
        raise ImportError('No tube folders with supported photos were found.')
    return [(name, sorted(items, key=lambda e:e.filename.casefold())) for name,items in sorted(groups.items())]


def prepare_archive(file, staging, session_id, received, created_at):
    from PIL import Image, ImageOps
    file.seek(0, 2)
    if file.tell() > MAX_ARCHIVE:
        raise ImportError('Maximum ZIP size is 250 MB.')
    file.seek(0)
    prepared = []
    with zipfile.ZipFile(file) as archive:
        groups = plan_archive(archive)
        if any(PurePosixPath(e.filename).suffix.lower() in {'.heic', '.heif'} for _,items in groups for e in items):
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ModuleNotFoundError:
                raise ImportError('HEIC photos need pillow-heif installed in .venv-ocr. Convert to JPG or install HEIC support, then retry. No samples were queued.')
        for source_folder, entries in groups:
            record_id = uuid4().hex
            destination = staging/record_id
            destination.mkdir()
            images = []
            for number, entry in enumerate(entries, 1):
                suffix = PurePosixPath(entry.filename).suffix.lower()
                name = f'image_{number}{EXTENSIONS[suffix]}'
                target = destination/name
                raw = destination/'incoming-photo'
                with archive.open(entry) as source, raw.open('wb') as output:
                    size = 0
                    while chunk := source.read(64*1024):
                        size += len(chunk)
                        if size > MAX_PHOTO:
                            raise ImportError('Photo exceeds 10 MB.')
                        output.write(chunk)
                try:
                    with Image.open(raw) as image:
                        if image.width*image.height > 20_000_000:
                            raise ImportError('Photo exceeds 20 megapixels: '+entry.filename)
                        actual = image.format
                        detected_extension = {'JPEG':'.jpg', 'PNG':'.png', 'WEBP':'.webp'}.get(actual)
                        converted = detected_extension is None
                        if actual == 'TIFF' and getattr(image, 'n_frames', 1) > 1:
                            raise ImportError('Multi-page TIFF must be split into separate photos: '+entry.filename)
                        if converted and actual not in {'HEIF', 'HEIC', 'TIFF', 'BMP', 'MPO'}:
                            raise ImportError('Unsupported image contents ('+str(actual)+'): '+entry.filename)
                        name = f'image_{number}{detected_extension or ".jpg"}'
                        target = destination/name
                        if converted:
                            ImageOps.exif_transpose(image).convert('RGB').save(target, 'JPEG', quality=92)
                        else:
                            image.verify()
                    if not converted:
                        raw.rename(target)
                    else:
                        raw.unlink()
                except (OSError, Image.DecompressionBombError) as error:
                    raise ImportError('Cannot read photo: '+entry.filename) from error
                digest=hashlib.sha256()
                with target.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(64*1024),b''):
                        digest.update(chunk)
                images.append({'filename':name, 'size_bytes':target.stat().st_size, 'sha256':digest.hexdigest(),
                               'original_name':entry.filename, 'detected_format':actual})
            sample = {'record_id':record_id, 'session_id':session_id, 'created_at':created_at,
                      'date_received':received, 'source_folder':source_folder,
                      'images':images, 'image_count':len(images)}
            (destination/'sample.json').write_text(json.dumps(sample, indent=2), encoding='utf-8')
            prepared.append(sample)
    return prepared
