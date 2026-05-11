#!/usr/bin/env python3

from pathlib import Path
from struct import unpack
from argparse import ArgumentParser
from typing import List, Dict, BinaryIO

MAGIC = b'\x55\xAA\x5A\xA5'

CHUNK_SIZE = 0x400
ALIGNMENT = 4

COPY_CHUNK = 1 << 20
IO_BUF     = 1 << 20

class Partition:
    __slots__ = ('start', 'hdr_sz', 'unk1', 'hw_id', 'seq', 'size',
                 'date', 'time', 'type', 'hdr_crc', 'block_size',
                 'data_offset', 'end')

    def __init__(self, start, hdr_sz, unk1, hw_id, seq, size,
                 date, time, ftype, hdr_crc, block_size,
                 data_offset, end):
        self.start = start
        self.hdr_sz = hdr_sz
        self.unk1 = unk1
        self.hw_id = hw_id
        self.seq = seq
        self.size = size
        self.date = date
        self.time = time
        self.type = ftype
        self.hdr_crc = hdr_crc
        self.block_size = block_size
        self.data_offset = data_offset
        self.end = end

    @classmethod
    def from_file(cls, file: BinaryIO, offset: int):
        hdr_sz, unk1, hw_id, seq, size = unpack('<LLQLL', file.read(24))
        date  = file.read(16).decode(errors='replace').strip('\x00')
        time  = file.read(16).decode(errors='replace').strip('\x00')
        ftype = file.read(16).decode(errors='replace').strip('\x00')
        file.read(16)                       # blank1
        hdr_crc    = file.read(2).hex()
        block_size = file.read(2).hex()
        file.read(2)                        # blank2
        file.read(hdr_sz - 98)              # checksum table?

        data_offset = file.tell()
        file.seek(size, 1)
        pad = (ALIGNMENT - file.tell() % ALIGNMENT) % ALIGNMENT
        if pad:
            file.seek(pad, 1)

        return cls(offset, hdr_sz, unk1, hw_id, seq, size,
                   date, time, ftype, hdr_crc, block_size,
                   data_offset, file.tell())

class UpdateExtractor:
    def __init__(self, package: Path, output: Path):
        self.package = package.open('rb', buffering=IO_BUF)
        self.output = output
        self.partitions: List[Partition] = []
        self.parse_partitions()

    def parse_partitions(self):
        f = self.package
        read = f.read
        while True:
            buf = read(4)
            if not buf:
                break
            if buf == MAGIC:
                self.partitions.append(Partition.from_file(f, f.tell()))

    def extract(self, name: str = None):
        self.output.mkdir(exist_ok=True, parents=True)
        name_counts: Dict[str, int] = {}
        f = self.package

        for p in self.partitions:
            if name is not None and p.type != name:
                continue
            if p.type in name_counts:
                name_counts[p.type] += 1
                filename = '%s_%d.img' % (p.type, name_counts[p.type])
            else:
                name_counts[p.type] = 0
                filename = '%s.img' % p.type

            f.seek(p.data_offset)
            remaining = p.size
            with open(self.output / filename, 'wb', buffering=IO_BUF) as out:
                while remaining:
                    chunk = f.read(COPY_CHUNK if remaining > COPY_CHUNK else remaining)
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)

def main():
    parser = ArgumentParser()
    parser.add_argument('package', help='UPDATE.APP package.', type=Path)
    parser.add_argument('-e', '--extract', action='store_true')
    parser.add_argument('-o', '--output', default='output', type=Path)
    parser.add_argument('-p', '--partition', type=str, default=None)
    args = parser.parse_args()

    extractor = UpdateExtractor(args.package, args.output)
    for p in extractor.partitions:
        print("%s (%d bytes) @ %s - %s" % (p.type, p.size, hex(p.start), hex(p.end)))
    if args.extract:
        extractor.extract(args.partition)

if __name__ == '__main__':
    main()