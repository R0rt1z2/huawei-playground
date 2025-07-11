#!/usr/bin/env python3

import argparse
import os
import sys
import time
import usb.core
import usb.util
from typing import Dict, Optional, Tuple
from tqdm import tqdm

FASTBOOT_CLASS = 0xFF
FASTBOOT_SUBCLASS = 0x42
FASTBOOT_PROTOCOL = 0x03


class FastbootError(Exception):
    pass


class PartitionDumper:
    def __init__(self):
        self.device = None
        self.interface = None
        self.ep_in = None
        self.ep_out = None

    def find_device(self) -> bool:
        print("Waiting for fastboot device...")
        
        while True:
            devices = usb.core.find(find_all=True)
            for device in devices:
                try:
                    for cfg in device:
                        for intf in cfg:
                            if (intf.bInterfaceClass == FASTBOOT_CLASS and
                                intf.bInterfaceSubClass == FASTBOOT_SUBCLASS and
                                intf.bInterfaceProtocol == FASTBOOT_PROTOCOL):
                                
                                if self._initialize_device(device, intf):
                                    print("Found device = %04x:%04x" % (device.idVendor, device.idProduct))
                                    return True
                except Exception:
                    continue
            time.sleep(1)

    def _initialize_device(self, device, interface) -> bool:
        try:
            if device.is_kernel_driver_active(interface.bInterfaceNumber):
                device.detach_kernel_driver(interface.bInterfaceNumber)
            
            device.set_configuration()
            device.reset()
            time.sleep(0.5)
            usb.util.claim_interface(device, interface.bInterfaceNumber)
            
            ep_in = None
            ep_out = None
            
            for ep in interface:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    ep_out = ep
                elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    ep_in = ep
                    
            if ep_in is None or ep_out is None:
                return False
                
            self.device = device
            self.interface = interface
            self.ep_in = ep_in
            self.ep_out = ep_out
            return True
            
        except Exception:
            return False

    def _send_command(self, command: str) -> bool:
        if not self.device or not self.ep_out:
            return False
            
        try:
            data = command.encode() if isinstance(command, str) else command
            self.device.write(self.ep_out.bEndpointAddress, data, timeout=5000)
            return True
        except Exception:
            return False

    def _read_response(self, size: int = 64, timeout_ms: int = 5000) -> Optional[bytes]:
        if not self.device or not self.ep_in:
            return None
            
        try:
            data = self.device.read(self.ep_in.bEndpointAddress, size, timeout_ms)
            return bytes(data)
        except usb.core.USBTimeoutError:
            return None
        except Exception:
            return None

    def _flush_responses(self):
        while True:
            response = self._read_response(64, 100)
            if response is None:
                break

    def get_partition_size(self, partition_name: str) -> int:
        self._flush_responses()
        
        command = "getvar:partition-size:%s" % partition_name
        if not self._send_command(command):
            return 0

        response = self._read_response(64, 3000)
        if not response or len(response) < 4:
            return 0
            
        header = response[:4]
        data = response[4:].decode('utf-8', errors='ignore').strip()
        
        if header == b'OKAY':
            try:
                return int(data, 16)
            except ValueError:
                return 0
        elif header == b'FAIL':
            raise FastbootError("Failed to get partition size: %s" % data)
            
        return 0

    def list_partitions(self) -> Dict[str, Dict[str, any]]:
        self._flush_responses()
        
        command = "getvar:all"
        if not self._send_command(command):
            raise FastbootError("Failed to send getvar:all command")

        partitions = {}
        
        while True:
            response = self._read_response(64, 3000)
            if not response:
                break
                
            if len(response) < 4:
                continue
                
            header = response[:4]
            data = response[4:].decode('utf-8', errors='ignore').strip()
            
            if header == b'INFO':
                if data.startswith('partition-size:'):
                    colon_pos = data.find(':', 15)
                    if colon_pos != -1:
                        partition_name = data[15:colon_pos]
                        size_hex = data[colon_pos+2:]
                        try:
                            size_bytes = int(size_hex, 16)
                            if partition_name not in partitions:
                                partitions[partition_name] = {}
                            partitions[partition_name]['size'] = size_bytes
                        except ValueError:
                            continue
                elif data.startswith('partition-type:'):
                    colon_pos = data.find(':', 15)
                    if colon_pos != -1:
                        partition_name = data[15:colon_pos]
                        partition_type = data[colon_pos+2:]
                        if partition_name not in partitions:
                            partitions[partition_name] = {}
                        partitions[partition_name]['type'] = partition_type
            elif header == b'OKAY':
                break
            elif header == b'FAIL':
                raise FastbootError("Failed to get partition list: %s" % data)

        return partitions

    def dump_partition(self, partition_name: str, output_path: str) -> bool:
        try:
            expected_size = self.get_partition_size(partition_name)
        except FastbootError as e:
            print("Error: %s" % str(e))
            return False

        self._flush_responses()
        
        command = "oem dump-storage %s" % partition_name
        if not self._send_command(command):
            print("Error: Failed to send dump command")
            return False

        time.sleep(1)

        response = self._read_response(64, 10000)
        if not response:
            print("Error: No response from device")
            return False

        if len(response) < 4:
            print("Error: Invalid response length")
            return False

        header = response[:4]
        data = response[4:] if len(response) > 4 else b''

        if header == b'FAIL':
            error_msg = data.decode('utf-8', errors='ignore').strip()
            print("Error: Device reported failure: %s" % error_msg)
            return False

        if header != b'DUMP' or not data.startswith(b'START'):
            print("Error: Device did not start dump mode")
            return False

        try:
            with open(output_path, 'wb') as output_file:
                total_bytes = 0
                
                if expected_size > 0:
                    progress_bar = tqdm(
                        total=expected_size,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc="Dumping %s" % partition_name
                    )
                else:
                    progress_bar = tqdm(
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc="Dumping %s" % partition_name
                    )

                try:
                    while True:
                        block = self._read_response(512, 5000)
                        if block is None or len(block) == 0:
                            continue

                        if b'UMPEND' in block or b'END' in block:
                            end_markers = [b'UMPEND', b'END']
                            end_pos = -1

                            for marker in end_markers:
                                pos = block.find(marker)
                                if pos != -1:
                                    end_pos = pos
                                    break

                            if end_pos > 0:
                                output_file.write(block[:end_pos])
                                total_bytes += end_pos
                                progress_bar.update(end_pos)
                            break

                        output_file.write(block)
                        total_bytes += len(block)
                        progress_bar.update(len(block))

                finally:
                    progress_bar.close()

        except IOError as e:
            print("Error: Cannot write to file '%s': %s" % (output_path, str(e)))
            return False
        except KeyboardInterrupt:
            print("\nOperation cancelled")
            return False

        if total_bytes == 0:
            print("Error: No data was dumped")
            return False

        print("Success: %s dumped (%d bytes)" % (partition_name, total_bytes))
        return True

    def cleanup(self):
        if self.device and self.interface:
            try:
                usb.util.release_interface(self.device, self.interface.bInterfaceNumber)
            except Exception:
                pass


def print_partition_table(partitions: Dict[str, Dict[str, any]]):
    if not partitions:
        print("No partitions found")
        return

    print("Available partitions:")
    print("%-20s %-15s %-12s %s" % ("NAME", "TYPE", "SIZE", "SIZE (MB)"))
    print("-" * 60)
    
    for name in sorted(partitions.keys()):
        info = partitions[name]
        size_bytes = info.get('size', 0)
        size_mb = size_bytes / (1024 * 1024) if size_bytes > 0 else 0
        partition_type = info.get('type', 'unknown')
        
        print("%-20s %-15s %-12d %.2f" % (
            name, 
            partition_type[:15], 
            size_bytes, 
            size_mb
        ))


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  %(prog)s recovery recovery.img
  %(prog)s boot boot.img
  %(prog)s --list'''
    )
    
    parser.add_argument('partition', nargs='?', help='Partition name to dump')
    parser.add_argument('output', nargs='?', help='Output file path')
    parser.add_argument('-l', '--list', action='store_true', 
                       help='List all available partitions')

    args = parser.parse_args()
    
    dumper = PartitionDumper()
    
    try:
        if not dumper.find_device():
            print("Error: Could not find fastboot device")
            return 1

        if args.list:
            try:
                partitions = dumper.list_partitions()
                print_partition_table(partitions)
                return 0
            except FastbootError as e:
                print("Error: %s" % str(e))
                return 1
                
        elif args.partition and args.output:
            success = dumper.dump_partition(args.partition, args.output)
            return 0 if success else 1
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        return 1
    except Exception as e:
        print("Unexpected error: %s" % str(e))
        return 1
    finally:
        dumper.cleanup()


if __name__ == "__main__":
    sys.exit(main())
