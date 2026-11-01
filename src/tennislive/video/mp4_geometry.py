"""Read native photo-sequence geometry before ffprobe is installed.

Only an unambiguous video sample entry is accepted. The full render still
uses ffprobe and the decoder; this header reader keeps early dry-runs light.
"""
from pathlib import Path
import struct


def photo_movie_size(path: Path) -> tuple[int, int]:
    with path.open('rb') as stream:
        end = path.stat().st_size

        def atoms(start, stop):
            while start < stop:
                stream.seek(start)
                head = stream.read(8)
                if len(head) != 8:
                    raise ValueError('truncated MP4 atom')
                size, kind = struct.unpack('>I4s', head)
                header = 8
                if size == 1:
                    extra = stream.read(8)
                    if len(extra) != 8:
                        raise ValueError('truncated extended MP4 atom')
                    size = struct.unpack('>Q', extra)[0]
                    header = 16
                elif size == 0:
                    size = stop - start
                if size < header or start + size > stop:
                    raise ValueError('invalid MP4 atom bounds')
                yield kind, start + header, start + size
                start += size

        def child(start, stop, name):
            matches = [(a, b) for k, a, b in atoms(start, stop) if k == name]
            if len(matches) != 1:
                raise ValueError(f'MP4 requires one {name!r} atom')
            return matches[0]

        moov = child(0, end, b'moov')
        sizes = []
        for kind, a, b in atoms(*moov):
            if kind != b'trak':
                continue
            mdia = child(a, b, b'mdia')
            hdlr, hdlr_end = child(*mdia, b'hdlr')
            if hdlr_end - hdlr < 12:
                raise ValueError('truncated MP4 handler')
            stream.seek(hdlr + 8)
            if stream.read(4) != b'vide':
                continue
            minf = child(*mdia, b'minf')
            stbl = child(*minf, b'stbl')
            stsd, stsd_end = child(*stbl, b'stsd')
            stream.seek(stsd)
            if stream.read(8) != b'\0\0\0\0\0\0\0\1':
                raise ValueError('ambiguous MP4 sample descriptions')
            entries = list(atoms(stsd + 8, stsd_end))
            if len(entries) != 1 or entries[0][0] not in (b'avc1', b'avc3', b'hvc1', b'hev1', b'mp4v'):
                raise ValueError('unsupported photo-movie sample entry')
            _, sample, sample_end = entries[0]
            if sample_end - sample < 28:
                raise ValueError('truncated visual sample entry')
            stream.seek(sample + 24)
            sizes.append(struct.unpack('>HH', stream.read(4)))
        if len(sizes) != 1 or min(sizes[0]) <= 0:
            raise ValueError('photo movie requires one video track with valid dimensions')
        return sizes[0]
