import subprocess
from pathlib import Path
import re
from PIL import Image, ImageChops
from PIL.ImageOps import flip
from dataclasses import dataclass

diffuse_names = ["diffuse", "albedo", "color"]
roughness_names = ["rough"]
metallic_names = ["metal"]
ao_names = ["ao", "AO", "ambient"]
normal_names = ["normal", "bump", "nrml", "Nrml", "NRML"]

converting_folders: dict = {}
input_dir: Path = Path("input")
output_dir: Path = Path("output")

@dataclass
class Material:
    diffuse: str
    roughness: str = ""
    metallic: str = ""
    ao: str = ""
    normal: str = ""

test: Material = Material("test", "test1")
test.ao = "poop"

def analyze_inputs() -> None:
    for folder in input_dir.iterdir():
        if Path.is_dir(folder):
            converting_folders[folder] = Material("", "")
            for file in folder.iterdir():
                match handle_alt_names(file.name):
                    case "diffuse":
                        converting_folders[folder].diffuse = file
                    case "rough":
                        converting_folders[folder].roughness = file
                    case "metal":
                        converting_folders[folder].metallic = file
                    case "ao":
                        converting_folders[folder].ao = file
                    case "normal":
                        converting_folders[folder].normal = file

def handle_alt_names(file: str) -> str:
    if any(texmap in file for texmap in diffuse_names):
        return "diffuse"
    if any(texmap in file for texmap in roughness_names):
        return "rough"
    if any(texmap in file for texmap in metallic_names):
        return "metal"
    if any(texmap in file for texmap in ao_names):
        return "ao"
    if any(texmap in file for texmap in normal_names):
        return "normal"
    return ""

def create_vmt() -> None:
    for folder in converting_folders.keys():
        output_path: Path = Path("output/" + folder.name + "/" + folder.name + ".vmt")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as vmt:
            vmt.writelines([
                "PBR\n",
                '{\n',
				'	$basetexture               "' + folder.name + '_basecolor"\n',
				'	$bumpmap                   "'+ folder.name +'_bump"\n'
            ])

            vmt.writelines([
					'	$mraotexture               "'+ folder.name +'_mrao"\n',
            ])

            vmt.write('}')

def cross_channels(tex1: Image, chan1: int, tex2: Image, chan2: int):
    '''Takes a channel from tex1 and replaces the contents of tex2's chan2'''

    r1, g1, b1, a1 = tex1.convert('RGBA').split()
    r2, g2, b2, a2 = tex2.convert('RGBA').split()
    match chan1:
        case 0: src = r1
        case 1: src = g1
        case 2: src = b1
        case 3: src = a1
    match chan2:
        case 0: r2 = src
        case 1: g2 = src
        case 2: b2 = src
        case 3: a2 = src
    return Image.merge( 'RGBA', (r2, g2, b2, a2) )

def create_vtf(material: Material) -> None:
    # diffuse
    subprocess.run(["./bin/VTFCmd.exe", "-file", str(material.diffuse.resolve()), "-output", str((output_dir / material.diffuse.parent.name).resolve()), "-version", "7.4"])
    diffuse_vtf: Path = Path(str(output_dir) + "/" + material.diffuse.parent.name + "/" + material.diffuse.with_suffix('.vtf').name)
    diffuse_vtf.rename(diffuse_vtf.with_name(material.diffuse.parent.name + "_basecolor.vtf"))

    # process mrao
    diffuse_texture: Image = Image.open(converting_folders[list(converting_folders.keys())[0]].diffuse)
    metal_texture: Image = Image.new('RGB', diffuse_texture.size, (0, 0, 0))
    rough_texture: Image = Image.new('RGB', diffuse_texture.size, (255, 255, 255))
    ao_texture: Image = Image.new('RGB', diffuse_texture.size, (255, 255, 255))
    if material.metallic != "":
        metal_texture = Image.open(converting_folders[list(converting_folders.keys())[0]].metallic)
    if material.roughness != "":
        rough_texture = Image.open(converting_folders[list(converting_folders.keys())[0]].roughness)
    if material.ao != "":
        ao_texture = Image.open(converting_folders[list(converting_folders.keys())[0]].ao)
    
    mrao_texture: Image = Image.new('RGB', diffuse_texture.size, 255)
    mrao_texture = cross_channels(metal_texture, 0, mrao_texture, 0)
    mrao_texture = cross_channels(rough_texture, 0, mrao_texture, 1)
    mrao_texture = cross_channels(ao_texture, 0, mrao_texture, 2)
    mrao_path: Path = material.diffuse.parent / ("mrao.png")
    mrao_texture = mrao_texture.convert('RGB').save(mrao_path)

    # normal
    subprocess.run(["./bin/VTFCmd.exe", "-file", str(material.normal.resolve()), "-output", str((output_dir / material.diffuse.parent.name).resolve()), "-version", "7.4"])
    normal_vtf: Path = Path(str(output_dir) + "/" + material.normal.parent.name + "/" + material.normal.with_suffix('.vtf').name)
    normal_vtf.rename(normal_vtf.with_name(material.normal.parent.name + "_bump.vtf"))

    # mrao
    subprocess.run(["./bin/VTFCmd.exe", "-file", str(mrao_path.resolve()), "-output", str((output_dir / material.diffuse.parent.name).resolve()), "-version", "7.4", "-format", "dxt1"])
    mrao_vtf: Path = Path(str(output_dir) + "/" + material.diffuse.parent.name + "/" + mrao_path.with_suffix('.vtf').name)
    mrao_vtf.rename(mrao_vtf.with_name(material.diffuse.parent.name + "_mrao.vtf"))
 

def create_all_vtfs() -> None:
    for folder in converting_folders.keys():
        create_vtf(converting_folders[folder])

analyze_inputs()
create_vmt()
create_all_vtfs()