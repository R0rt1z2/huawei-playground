#!/usr/bin/env python3

import gzip
import json
import struct
from enum import Enum
from pathlib import Path
from typing import Union, List, Optional, Dict, Tuple
from struct import unpack, pack
from argparse import ArgumentParser

MAGIC = b'OEM_INFO'

class Operation(Enum):
    OINV_OP_MIN = 0
    OEMINFO_WRITE = 1
    OEMINFO_READ = 2
    OEMINFO_GETAGE = 3
    OEMINFO_GETINFO = 4
    OEMINFO_ERASE = 5

class ImageType(Enum):
    UNKNOWN = "unknown"
    GZIP_BMP = "gzip_bmp"
    RAW_BMP = "raw_bmp"
    GZIP_OTHER = "gzip_other"
    RAW_DATA = "raw_data"

class ImageInfo:
    def __init__(self, image_type: ImageType, filename: str = "",
                 width: int = 0, height: int = 0, bpp: int = 0,
                 gzip_offset: int = 0, original_size: int = 0,
                 compressed_size: int = 0):
        self.image_type = image_type
        self.filename = filename
        self.width = width
        self.height = height
        self.bpp = bpp
        self.gzip_offset = gzip_offset
        self.original_size = original_size
        self.compressed_size = compressed_size

    def to_dict(self) -> Dict:
        return {
            'image_type': self.image_type.value,
            'filename': self.filename,
            'width': self.width,
            'height': self.height,
            'bpp': self.bpp,
            'gzip_offset': self.gzip_offset,
            'original_size': self.original_size,
            'compressed_size': self.compressed_size
        }

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            ImageType(data['image_type']),
            data.get('filename', ''),
            data.get('width', 0),
            data.get('height', 0),
            data.get('bpp', 0),
            data.get('gzip_offset', 0),
            data.get('original_size', 0),
            data.get('compressed_size', 0)
        )

class OemInfoEntry:
    def __init__(self, header: bytes, version: int, id: int,
                 type: int, length: int, age: int, data: bytes, start: int):
        self.header = header
        self.version = version
        self.id = id
        self.type = type
        self.length = length
        self.age = age
        self.data = data
        self.start = start
        assert len(data) == length, "Data length mismatch."

    def __str__(self):
        return "%d-%d-%d-%d-0x%x" % (self.version, self.id,
                                    self.type, self.age, self.start)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0):
        (header, version, id, type,
         length, age) = unpack('<8sIIIII', data[offset:offset+28])
        return cls(header, version, id, type, length, age,
                   data[offset+0x200:offset+0x200+length], offset)

class ImageAnalyzer:
    @staticmethod
    def find_gzip_data(data: bytes) -> Optional[Tuple[int, str]]:
        gzip_signature = b'\x1f\x8b'

        for i in range(len(data) - 10):
            if data[i:i + 2] == gzip_signature:
                try:
                    if data[i + 2] != 0x08:
                        continue

                    flags = data[i + 3]
                    header_size = 10
                    offset = i + header_size

                    if flags & 0x04:
                        if offset + 2 > len(data):
                            continue
                        xlen = struct.unpack('<H', data[offset:offset + 2])[0]
                        offset += 2 + xlen

                    filename = ""
                    if flags & 0x08:
                        fname_start = offset
                        while offset < len(data) and data[offset] != 0:
                            offset += 1
                        if offset < len(data):
                            filename = data[fname_start:offset].decode('utf-8', errors='ignore')
                            offset += 1

                    return i, filename

                except (struct.error, UnicodeDecodeError):
                    continue

        return None

    @staticmethod
    def analyze_bmp_header(data: bytes) -> Optional[Tuple[int, int, int]]:
        if len(data) < 54 or data[:2] != b'BM':
            return None

        try:
            width = struct.unpack('<l', data[18:22])[0]
            height = struct.unpack('<l', data[22:26])[0]
            bpp = struct.unpack('<H', data[28:30])[0]
            return abs(width), abs(height), bpp
        except:
            return None

    @classmethod
    def analyze_entry_data(cls, data: bytes) -> ImageInfo:
        if len(data) < 10:
            return ImageInfo(ImageType.RAW_DATA)

        gzip_result = cls.find_gzip_data(data)
        if gzip_result:
            gzip_offset, filename = gzip_result

            try:
                gzip_data = data[gzip_offset:]
                decompressed = gzip.decompress(gzip_data)

                bmp_info = cls.analyze_bmp_header(decompressed)
                if bmp_info:
                    width, height, bpp = bmp_info
                    return ImageInfo(
                        ImageType.GZIP_BMP,
                        filename,
                        width, height, bpp,
                        gzip_offset,
                        len(decompressed),
                        len(gzip_data)
                    )
                else:
                    return ImageInfo(
                        ImageType.GZIP_OTHER,
                        filename,
                        gzip_offset=gzip_offset,
                        original_size=len(decompressed),
                        compressed_size=len(gzip_data)
                    )
            except:
                pass

        bmp_info = cls.analyze_bmp_header(data)
        if bmp_info:
            width, height, bpp = bmp_info
            return ImageInfo(
                ImageType.RAW_BMP,
                width=width, height=height, bpp=bpp,
                original_size=len(data)
            )

        return ImageInfo(ImageType.RAW_DATA, original_size=len(data))

class OemInfoImage:
    def __init__(self, image: Union[bytes, Path]):
        if isinstance(image, Path):
            with open(image, 'rb') as fp:
                self.image = bytearray(fp.read())
        else:
            self.image = image
        self.entries: List[OemInfoEntry] = []
        self.parse_entries()

    def parse_entries(self):
        offset = self.image.find(MAGIC)
        while offset != -1:
            self.entries.append(
                OemInfoEntry.from_bytes(self.image, offset))
            offset = self.image.find(MAGIC, offset + 1)

    def get_entry_by_id(self, id: int) -> Optional[OemInfoEntry]:
        for entry in self.entries:
            if entry.id == id:
                return entry
        return None

    def get_entries_by_ids(self, ids: List[int]) -> List[OemInfoEntry]:
        return [entry for entry in self.entries if entry.id in ids]

    def analyze_images(self) -> Dict[int, ImageInfo]:
        image_entries = {}

        for entry in self.entries:
            image_info = ImageAnalyzer.analyze_entry_data(entry.data)
            if image_info.image_type != ImageType.RAW_DATA or len(entry.data) > 1000:
                image_entries[entry.id] = image_info

        return image_entries

    def extract_images(self, output: Path, save_metadata: bool = True) -> Dict[int, ImageInfo]:
        output.mkdir(parents=True, exist_ok=True)

        image_entries = self.analyze_images()
        extracted_images = {}

        for entry_id, image_info in image_entries.items():
            entry = self.get_entry_by_id(entry_id)
            if not entry:
                continue

            base_name = "entry_0x%04x" % entry_id

            if image_info.image_type == ImageType.GZIP_BMP:
                gzip_data = entry.data[image_info.gzip_offset:]
                decompressed = gzip.decompress(gzip_data)

                if image_info.filename:
                    bmp_name = "%s_%s.bmp" % (base_name, Path(image_info.filename).stem)
                else:
                    bmp_name = "%s_%dx%d.bmp" % (base_name, image_info.width, image_info.height)

                bmp_path = output / bmp_name
                with open(bmp_path, 'wb') as f:
                    f.write(decompressed)

                gz_path = output / ("%s_original.gz" % base_name)
                with open(gz_path, 'wb') as f:
                    f.write(gzip_data)

                if image_info.gzip_offset > 0:
                    prefix_path = output / ("%s_prefix.bin" % base_name)
                    with open(prefix_path, 'wb') as f:
                        f.write(entry.data[:image_info.gzip_offset])

                print("Extracted gzipped BMP: %s (%dx%d, %dbpp)" % (bmp_name, image_info.width, image_info.height, image_info.bpp))
                extracted_images[entry_id] = image_info

            elif image_info.image_type == ImageType.RAW_BMP:
                bmp_name = "%s_%dx%d.bmp" % (base_name, image_info.width, image_info.height)
                bmp_path = output / bmp_name
                with open(bmp_path, 'wb') as f:
                    f.write(entry.data)

                print("Extracted raw BMP: %s (%dx%d, %dbpp)" % (bmp_name, image_info.width, image_info.height, image_info.bpp))
                extracted_images[entry_id] = image_info

            elif image_info.image_type == ImageType.GZIP_OTHER:
                gzip_data = entry.data[image_info.gzip_offset:]
                decompressed = gzip.decompress(gzip_data)

                if image_info.filename:
                    decomp_name = "%s_%s" % (base_name, Path(image_info.filename).name)
                else:
                    decomp_name = "%s_decompressed.bin" % base_name

                decomp_path = output / decomp_name
                with open(decomp_path, 'wb') as f:
                    f.write(decompressed)

                print("Extracted gzipped data: %s (%d bytes)" % (decomp_name, len(decompressed)))
                extracted_images[entry_id] = image_info

        if save_metadata and extracted_images:
            metadata = {
                'entries': {
                    str(entry_id): image_info.to_dict()
                    for entry_id, image_info in extracted_images.items()
                }
            }

            metadata_path = output / "image_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            print("Saved metadata to: %s" % metadata_path)

        return extracted_images

    def repack_images(self, input_dir: Path, metadata_file: Optional[Path] = None) -> None:
        if metadata_file is None:
            metadata_file = input_dir / "image_metadata.json"

        if not metadata_file.exists():
            print("Metadata file not found: %s" % metadata_file)
            return

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        for entry_id_str, image_info_dict in metadata['entries'].items():
            entry_id = int(entry_id_str)
            image_info = ImageInfo.from_dict(image_info_dict)
            entry = self.get_entry_by_id(entry_id)

            if not entry:
                continue

            base_name = "entry_0x%04x" % entry_id

            if image_info.image_type == ImageType.GZIP_BMP:
                new_data = bytearray()

                prefix_path = input_dir / ("%s_prefix.bin" % base_name)
                if prefix_path.exists():
                    with open(prefix_path, 'rb') as f:
                        new_data.extend(f.read())

                gz_path = input_dir / ("%s_original.gz" % base_name)
                if gz_path.exists():
                    with open(gz_path, 'rb') as f:
                        new_data.extend(f.read())
                else:
                    if image_info.filename:
                        bmp_name = "%s_%s.bmp" % (base_name, Path(image_info.filename).stem)
                    else:
                        bmp_name = "%s_%dx%d.bmp" % (base_name, image_info.width, image_info.height)

                    bmp_path = input_dir / bmp_name
                    if bmp_path.exists():
                        with open(bmp_path, 'rb') as f:
                            bmp_data = f.read()

                        gzipped = gzip.compress(bmp_data)
                        new_data.extend(gzipped)

                if len(new_data) <= entry.length:
                    self.image[entry.start + 0x200:entry.start + 0x200 + len(new_data)] = new_data
                    print("Repacked entry 0x%04x" % entry_id)
                else:
                    print("Warning: New data too large for entry 0x%04x" % entry_id)

    def extract_entries(self, output: Path, specific_ids: Optional[List[int]] = None):
        Path(output).mkdir(parents=True, exist_ok=True)

        if specific_ids is not None:
            entries_to_extract = self.get_entries_by_ids(specific_ids)
            if not entries_to_extract:
                print("No entries found with IDs: %s" % [hex(id) for id in specific_ids])
                return
        else:
            entries_to_extract = self.entries

        for entry in entries_to_extract:
            filename = "%s.bin" % str(entry)
            filepath = output / filename
            with open(filepath, 'wb') as fp:
                fp.write(entry.data)
            print("Extracted ID 0x%x: %s (%d bytes)" % (entry.id, filename, len(entry.data)))

        print("Extracted %d entries to '%s'." % (len(entries_to_extract), output))

        images_output = output / "images"
        extracted_images = self.extract_images(images_output, save_metadata=True)
        if extracted_images:
            print("Also extracted %d image entries to '%s'." % (len(extracted_images), images_output))

    def extract_single_entry(self, output: Path, id: int):
        entry = self.get_entry_by_id(id)
        if entry is None:
            print("Entry with ID 0x%x not found." % id)
            return

        Path(output).mkdir(parents=True, exist_ok=True)
        filename = "entry_0x%x.bin" % id
        filepath = output / filename

        with open(filepath, 'wb') as fp:
            fp.write(entry.data)

        print("Extracted entry ID 0x%x to '%s' (%d bytes)" % (id, filepath, len(entry.data)))

    def list_entries(self):
        print("Found %d entries:" % len(self.entries))
        print("ID      | Type    | Length  | Age | Offset   | Version | Image Info")
        print("--------|---------|---------|-----|----------|---------|------------------------------------------")

        image_entries = self.analyze_images()

        for entry in self.entries:
            image_info = ""
            if entry.id in image_entries:
                img_data = image_entries[entry.id]
                if img_data.image_type == ImageType.GZIP_BMP:
                    image_info = "gzipped BMP %dx%d %dbpp" % (img_data.width, img_data.height, img_data.bpp)
                    if img_data.filename:
                        image_info += " '%s'" % Path(img_data.filename).name
                elif img_data.image_type == ImageType.RAW_BMP:
                    image_info = "raw BMP %dx%d %dbpp" % (img_data.width, img_data.height, img_data.bpp)
                elif img_data.image_type == ImageType.GZIP_OTHER:
                    image_info = "gzipped data"
                    if img_data.filename:
                        image_info += " '%s'" % Path(img_data.filename).name

            print("0x%04x | 0x%04x | %7d | %3d | 0x%06x | %7d | %s" % (entry.id, entry.type, entry.length, entry.age, entry.start, entry.version, image_info))

    def list_images(self):
        pass

    def repack_entries(self, input: Path, output: Path):
        images_dir = input / "images"
        if images_dir.exists():
            metadata_file = images_dir / "image_metadata.json"
            if metadata_file.exists():
                print("Found image metadata, repacking images...")
                self.repack_images(images_dir, metadata_file)

        for entry in self.entries:
            filepath = input / ("%s.bin" % str(entry))
            if filepath.exists():
                with open(filepath, 'rb') as fp:
                    data = fp.read()
                    if len(data) <= entry.length:
                        self.image[entry.start+0x200:
                                   entry.start+0x200+len(data)] = data
                    else:
                        print("Warning: New data too large for entry 0x%04x" % entry.id)

        with open(output, 'wb') as fp:
            fp.write(self.image)
        print("Repacked entries to '%s'." % output)

def parse_id_list(id_string: str) -> List[int]:
    ids = []
    for part in id_string.split(','):
        part = part.strip()
        if part.startswith('0x'):
            ids.append(int(part, 16))
        else:
            ids.append(int(part))
    return ids

def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')

    parser_extract = subparsers.add_parser('extract', help='Extract entries and images.')
    parser_extract.add_argument('image', help='Path to the oeminfo image.', type=Path)
    parser_extract.add_argument('-o', '--output', help='Output path.', default='output', type=Path)
    parser_extract.add_argument('-i', '--ids', help='Comma-separated list of IDs to extract (hex or decimal)', type=str)
    parser_extract.add_argument('-s', '--single', help='Extract single entry by ID (hex or decimal)', type=str)
    parser_extract.add_argument('-l', '--list', help='List all entries with image info.', action='store_true')

    parser_repack = subparsers.add_parser('repack', help='Repack entries and images.')
    parser_repack.add_argument('image', help='Path to the oeminfo image.', type=Path)
    parser_repack.add_argument('input', help='Path to the extracted folder.', type=Path)
    parser_repack.add_argument('-o', '--output', help='Output file.', default='oeminfo.pack', type=Path)

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return

    image = OemInfoImage(args.image)

    if args.action == 'extract':
        if args.list:
            image.list_entries()
        elif args.single:
            if args.single.startswith('0x'):
                id_val = int(args.single, 16)
            else:
                id_val = int(args.single)
            image.extract_single_entry(args.output, id_val)
        elif args.ids:
            specific_ids = parse_id_list(args.ids)
            image.extract_entries(args.output, specific_ids)
        else:
            image.extract_entries(args.output)

    elif args.action == 'repack':
        image.repack_entries(args.input, args.output)

if __name__ == '__main__':
    main()
