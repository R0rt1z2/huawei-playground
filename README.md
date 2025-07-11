# Huawei playground

![License](https://img.shields.io/github/license/R0rt1z2/huawei-playground)
![GitHub Issues](https://img.shields.io/github/issues-raw/R0rt1z2/huawei-playground?color=red)

In my journey of exploring Huawei devices, I've created a variety of scripts and tools, each serving different purposes.<br><br>
To make these tools readily available and easily accessible for anyone interested in reverse engineering (RE) Huawei devices, I have centralized all of them into a single repository. I will keep updating the collection with new scripts and tools.

## Description
* `cm2parser.py`: Script designed to parse CM3 images, including modem, hifi, or mcu images. It will print the header information and will dump all the sections of the image.
* `fastbootimage.py`: Script designed to parse bootloader (fastboot.img) images. It will print the header information (i.e: load address, end address and first cmd).
* `oeminfo.py`: Script to unpack and repack oeminfo images. Repacking data with higher size will result in a brick.
* `partdumper.py`: Script to dump partitions directly from fastboot mode using custom OEM commands. Experimental and might only work on MediaTek based Huawei(s).
* `update-extractor.py`: Script to extract `UPDATE.APP` files. It will extract and print information about the images contained in the update file.

## Usage
Each tool comes with its unique functionality. To understand how to use them, you can access the help documentation by invoking it with the `-h` parameter.

## Examples

### CM3 Parser
Parse a CM3 image (modem/hifi/mcu):
```bash
python cm3parser.py modem.img
```

### Fastboot Image Parser
Parse bootloader header info:
```bash
python fastbootimage.py fastboot.img
python fastbootimage.py --start-offset 0x20 fastboot.img
```

### OEM Info Tool
List all entries in an oeminfo image:
```bash
python oeminfo.py extract -l oeminfo.img
```

Extract all entries and images:
```bash
python oeminfo.py extract oeminfo.img -o extracted/
```

Extract specific entries by ID:
```bash
python oeminfo.py extract oeminfo.img -i 0x01,0x02,0x05
```

Extract a single entry:
```bash
python oeminfo.py extract oeminfo.img -s 0x01
```

Repack modified entries back into image:
```bash
python oeminfo.py repack oeminfo.img extracted/ -o oeminfo_modified.img
```

### Partition Dumper
List all available partitions:
```bash
python partdumper.py --list
```

Dump a specific partition
```bash
python partdumper.py recovery recovery.img
python partdumper.py boot boot.img
python partdumper.py system system.img
```

### UPDATE.APP Extractor
List partitions in UPDATE.APP:
```bash
python update-extractor.py UPDATE.APP
```

Extract all partitions:
```bash
python update-extractor.py UPDATE.APP -e -o output/
```

Extract specific partition:
```bash
python update-extractor.py UPDATE.APP -e -p SYSTEM -o output/
```

## License
This project is licensed under the GPL-3.0 License - see the [LICENSE](https://github.com/R0rt1z2/huawei_playground/tree/master/LICENSE) file for details.

