#!/usr/bin/env python
# -*- coding: utf-8 -*- 
""" 
STEP/STP to STL/GLB Converter (cadquery-ocp Implementation)
支持部件识别、中文名称、网格优化、GLB导出、自动压缩
兼容 Windows 7 + Python 3.8.10 + cadquery-ocp==7.5.3
Mac M2 + Python 3.9 + cadquery-ocp>=7.7.2
""" 

import os
import sys
import time
import zipfile
import argparse
import re
import shutil
import gc
from pathlib import Path
from typing import Optional, List, Dict, Set
from contextlib import contextmanager

# 状态码常量
EXIT_SUCCESS = 0
EXIT_ERROR_IMPORT = 1
EXIT_ERROR_FILE_NOT_FOUND = 2
EXIT_ERROR_CONVERSION_FAILED = 3
EXIT_ERROR_INVALID_FORMAT = 4
EXIT_ERROR_WRITE_FAILED = 5

# Windows 7 兼容：限制线程数
MAX_WORKERS = min(4, os.cpu_count() or 2)

try: 
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.StlAPI import StlAPI
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDataStd import TDataStd_Name
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_COMPOUND
    from OCP.TopExp import TopExp_Explorer
    
    # GLB 导出支持
    GLB_AVAILABLE = False
    try:
        from OCP.RWGltf import RWGltf_CafWriter
        from OCP.TColStd import TColStd_IndexedDataMapOfStringString
        from OCP.Message import Message_ProgressRange
        GLB_AVAILABLE = True
    except ImportError:
        pass
        
except ImportError as e: 
    print("ERROR: 未安装 cadquery-ocp", file=sys.stderr) 
    print(f"原因: {e}", file=sys.stderr) 
    print("请运行: pip install cadquery-ocp==7.5.3 (Windows 7)", file=sys.stderr) 
    print("        pip install cadquery-ocp (Mac M2)", file=sys.stderr) 
    sys.exit(EXIT_ERROR_IMPORT) 

# 可选依赖
TRIMESH_AVAILABLE = False
try: 
    import trimesh
    import numpy as np
    TRIMESH_AVAILABLE = True
except ImportError: 
    pass

@contextmanager
def suppress_stderr():
    """抑制 stderr 输出（包括 C++ 层面）"""
    stderr_fd = None
    old_stderr_fd = None
    devnull = None
    
    try:
        stderr_fd = sys.stderr.fileno()
        old_stderr_fd = os.dup(stderr_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stderr_fd)
    except:
        pass
    
    try:
        yield
    finally:
        try:
            if old_stderr_fd is not None and stderr_fd is not None:
                os.dup2(old_stderr_fd, stderr_fd)
            if old_stderr_fd is not None:
                os.close(old_stderr_fd)
            if devnull is not None:
                os.close(devnull)
        except:
            pass

@contextmanager
def suppress_stdout():
    """抑制 stdout 输出（包括 C++ 层面）"""
    stdout_fd = None
    old_stdout_fd = None
    devnull = None
    
    try:
        stdout_fd = sys.stdout.fileno()
        old_stdout_fd = os.dup(stdout_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stdout_fd)
    except:
        pass
    
    try:
        yield
    finally:
        try:
            if old_stdout_fd is not None and stdout_fd is not None:
                os.dup2(old_stdout_fd, stdout_fd)
            if old_stdout_fd is not None:
                os.close(old_stdout_fd)
            if devnull is not None:
                os.close(devnull)
        except:
            pass

@contextmanager
def suppress_output():
    """抑制所有输出"""
    with suppress_stdout():
        with suppress_stderr():
            yield

class StepToStlConverter: 
    """STEP/STP 到 STL/GLB 转换器 (cadquery-ocp 实现)""" 
    
    SUPPORTED_EXTENSIONS = ['.step', '.stp', '.STEP', '.STP'] 
    
    QUALITY_PRESETS = { 
        'draft': {'linear': 0.1, 'angular': 1.0, 'name': '草图'}, 
        'low': {'linear': 0.05, 'angular': 0.8, 'name': '低质量'}, 
        'medium': {'linear': 0.01, 'angular': 0.5, 'name': '中等质量'}, 
        'high': {'linear': 0.005, 'angular': 0.3, 'name': '高质量'}, 
        'ultra': {'linear': 0.001, 'angular': 0.1, 'name': '超高质量'} 
    } 
    
    def __init__(self, quality='low', linear_deflection=None, 
                 angular_deflection=None, relative=True, parallel=True): 
        if quality in self.QUALITY_PRESETS: 
            preset = self.QUALITY_PRESETS[quality] 
            self.linear_deflection = linear_deflection or preset['linear'] 
            self.angular_deflection = angular_deflection or preset['angular'] 
            self.quality_name = preset['name'] 
        else: 
            self.linear_deflection = linear_deflection or 0.05
            self.angular_deflection = angular_deflection or 0.8
            self.quality_name = '自定义' 
        
        self.relative = relative
        self.parallel = parallel
    
    def sanitize_filename(self, name: str) -> str: 
        """清理文件名（兼容 Windows，保留中文）""" 
        if not name: 
            return "Part" 
        # 只替换 Windows 不允许的字符，保留中文
        cleaned = re.sub(r'[\\/*?:"<>|]', "_", str(name)).strip()
        cleaned = cleaned.replace(' ', '_')
        # 移除连续的下划线
        cleaned = re.sub(r'_+', '_', cleaned)
        cleaned = cleaned.strip('_')
        return cleaned if cleaned else "Part"
    
    def get_label_name(self, label, shape_tool) -> str:
        """获取 Label 的名称（支持中文）"""
        std_name = TDataStd_Name()
        
        try:
            guid = TDataStd_Name.GetID_s()
        except AttributeError:
            try:
                guid = TDataStd_Name.GetID()
            except:
                return ""
        
        if label.FindAttribute(guid, std_name):
            try:
                ext_str = std_name.Get()
                # 尝试多种方法获取字符串
                for method in ['ToUTF8CString', 'ToExtString']:
                    try:
                        result = getattr(ext_str, method)()
                        if result:
                            return str(result)
                    except:
                        continue
                
                # 尝试 AsciiString
                try:
                    ascii_str = TCollection_AsciiString(ext_str)
                    return ascii_str.ToCString()
                except:
                    pass
            except:
                pass
        
        return ""
    
    def get_shape_from_label(self, label, shape_tool):
        """从 Label 获取 Shape"""
        try:
            return shape_tool.GetShape_s(label)
        except AttributeError:
            try:
                return XCAFDoc_ShapeTool.GetShape_s(label)
            except:
                return None
    
    def get_label_hash(self, label) -> int:
        """获取 Label 的唯一标识"""
        try:
            # 使用 Entry 作为唯一标识
            entry = TCollection_AsciiString()
            label.Entry(entry)
            return hash(entry.ToCString())
        except:
            return id(label)
    
    def get_shape_hash(self, shape) -> int:
        """获取 Shape 的唯一标识"""
        try:
            return shape.HashCode(2147483647)
        except:
            return id(shape)
    
    def extract_parts_from_shape(self, shape, name: str, parts: List, 
                                  processed_shapes: Set[int], name_counter: Dict):
        """从形状中提取所有 SOLID 部件"""
        if shape is None or shape.IsNull():
            return
        
        shape_hash = self.get_shape_hash(shape)
        
        # 检查是否已处理过这个形状
        if shape_hash in processed_shapes:
            return
        
        shape_type = shape.ShapeType()
        
        # 如果是 SOLID，直接添加
        if shape_type == TopAbs_SOLID:
            processed_shapes.add(shape_hash)
            
            safe_name = self.sanitize_filename(name) if name else "Solid"
            
            # 处理重名
            name_lower = safe_name.lower()
            if name_lower not in name_counter:
                name_counter[name_lower] = 0
            name_counter[name_lower] += 1
            
            count = name_counter[name_lower]
            unique_name = f"{safe_name}_{count}"
            
            parts.append({
                'shape': shape,
                'name': unique_name,
                'raw_name': name or "Solid"
            })
            return
        
        # 如果是 COMPOUND，遍历提取 SOLID
        if shape_type == TopAbs_COMPOUND:
            explorer = TopExp_Explorer(shape, TopAbs_SOLID)
            solid_idx = 0
            while explorer.More():
                solid = explorer.Current()
                solid_hash = self.get_shape_hash(solid)
                
                if solid_hash not in processed_shapes:
                    processed_shapes.add(solid_hash)
                    solid_idx += 1
                    
                    # 生成名称
                    if name:
                        solid_name = f"{name}_{solid_idx}" if solid_idx > 1 else name
                    else:
                        solid_name = f"Solid_{solid_idx}"
                    
                    safe_name = self.sanitize_filename(solid_name)
                    
                    name_lower = safe_name.lower()
                    if name_lower not in name_counter:
                        name_counter[name_lower] = 0
                    name_counter[name_lower] += 1
                    
                    count = name_counter[name_lower]
                    unique_name = f"{safe_name}_{count}"
                    
                    parts.append({
                        'shape': solid,
                        'name': unique_name,
                        'raw_name': solid_name
                    })
                
                explorer.Next()
    
    def collect_parts(self, shape_tool, doc) -> List[Dict]:
        """收集所有唯一的部件（避免重复）"""
        parts = []
        processed_shapes: Set[int] = set()  # 记录已处理的形状
        processed_labels: Set[int] = set()  # 记录已处理的标签
        name_counter: Dict[str, int] = {}
        
        # 获取所有顶层形状（FreeShapes）
        free_shapes = TDF_LabelSequence()
        try:
            shape_tool.GetFreeShapes_s(free_shapes)
        except:
            try:
                shape_tool.GetFreeShapes(free_shapes)
            except:
                pass
        
        print(f"   顶层形状数量: {free_shapes.Length()}")
        
        # 递归处理函数
        def process_label(label, parent_name: str = ""):
            label_hash = self.get_label_hash(label)
            
            # 避免重复处理同一个标签
            if label_hash in processed_labels:
                return
            processed_labels.add(label_hash)
            
            # 获取名称
            name = self.get_label_name(label, shape_tool)
            if not name:
                name = parent_name
            
            # 检查是否是引用
            is_ref = False
            try:
                is_ref = shape_tool.IsReference_s(label)
            except:
                try:
                    is_ref = XCAFDoc_ShapeTool.IsReference_s(label)
                except:
                    pass
            
            # 如果是引用，获取真实的形状标签
            if is_ref:
                ref_label = label  # 临时变量
                try:
                    ref_label_seq = TDF_LabelSequence()
                    # 获取引用的目标
                    resolved = shape_tool.GetReferredShape_s(label, ref_label)
                    if resolved:
                        label = ref_label
                except:
                    pass
            
            # 检查是否是装配体
            is_assembly = False
            try:
                is_assembly = shape_tool.IsAssembly_s(label)
            except:
                try:
                    is_assembly = XCAFDoc_ShapeTool.IsAssembly_s(label)
                except:
                    pass
            
            if is_assembly:
                # 获取子组件
                components = TDF_LabelSequence()
                try:
                    shape_tool.GetComponents_s(label, components)
                except:
                    try:
                        XCAFDoc_ShapeTool.GetComponents_s(label, components)
                    except:
                        pass
                
                for i in range(1, components.Length() + 1):
                    comp_label = components.Value(i)
                    process_label(comp_label, name)
            else:
                # 获取形状并提取 SOLID
                shape = self.get_shape_from_label(label, shape_tool)
                if shape and not shape.IsNull():
                    self.extract_parts_from_shape(shape, name, parts, 
                                                  processed_shapes, name_counter)
        
        # 处理所有顶层形状
        for i in range(1, free_shapes.Length() + 1):
            label = free_shapes.Value(i)
            process_label(label, "")
        
        return parts
    
    def get_bounding_box_size(self, shape): 
        """获取模型包围盒尺寸""" 
        bbox = Bnd_Box() 
        
        try:
            BRepBndLib.Add_s(shape, bbox)
        except AttributeError:
            try:
                from OCP.BRepBndLib import brepbndlib
                brepbndlib.Add(shape, bbox)
            except:
                BRepBndLib.Add(shape, bbox)
        
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get() 
        
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        max_dim = max(dx, dy, dz) 
        return max_dim, (dx, dy, dz) 
    
    def calculate_deflection(self, shape, quality_factor=0.05): 
        max_dim, dimensions = self.get_bounding_box_size(shape) 
        
        if self.relative: 
            deflection = max_dim * quality_factor
        else: 
            deflection = quality_factor
        
        return deflection, max_dim, dimensions
    
    def mesh_shape(self, shape, linear_def: float) -> bool:
        """网格化单个形状"""
        try:
            mesh = BRepMesh_IncrementalMesh(
                shape,
                linear_def,
                False,
                self.angular_deflection,
                self.parallel
            )
            mesh.Perform()
            return mesh.IsDone()
        except:
            return False
    
    def convert_shape_to_stl(self, shape, output_path: Path, ascii_mode: bool = False) -> bool:
        """将单个形状转换为 STL"""
        try:
            stl_api = StlAPI()
            success = stl_api.Write_s(shape, str(output_path), ascii_mode)
            return success and output_path.exists() and output_path.stat().st_size > 0
        except:
            return False
    
    def optimize_stl(self, stl_path: Path) -> Optional[Path]: 
        """优化STL文件""" 
        if not TRIMESH_AVAILABLE: 
            return None
        
        try: 
            mesh = trimesh.load_mesh(str(stl_path), process=False) 
            mesh.merge_vertices() 
            mesh.remove_unreferenced_vertices() 
            
            if hasattr(mesh, 'nondegenerate_faces'): 
                mesh.update_faces(mesh.nondegenerate_faces()) 
            if hasattr(mesh, 'unique_faces'): 
                mesh.update_faces(mesh.unique_faces()) 
            
            if len(mesh.faces) == 0: 
                return None
            
            temp_path = stl_path.parent / f"{stl_path.stem}_temp.stl" 
            mesh.export(str(temp_path), file_type='stl') 
            
            if temp_path.exists() and temp_path.stat().st_size > 0: 
                temp_path.replace(stl_path) 
                return stl_path
            
            if temp_path.exists():
                temp_path.unlink()
            return None
        except: 
            return None
    
    def export_glb_native(self, doc, glb_path: Path) -> Optional[Path]: 
        """使用 OCP 原生导出 GLB（隐藏警告）""" 
        if not GLB_AVAILABLE: 
            return None
        
        try: 
            with suppress_output():
                writer = RWGltf_CafWriter(TCollection_AsciiString(str(glb_path)), True)
                file_info = TColStd_IndexedDataMapOfStringString()
                progress = Message_ProgressRange()
                result = writer.Perform(doc, file_info, progress)
            
            if result and glb_path.exists():
                return glb_path
            return None
        except:
            return None
    
    def export_glb_trimesh(self, stl_path: Path, glb_path: Path) -> Optional[Path]: 
        """使用 trimesh 导出 GLB""" 
        if not TRIMESH_AVAILABLE: 
            return None
        
        try: 
            mesh = trimesh.load_mesh(str(stl_path), process=False) 
            mesh.export(str(glb_path), file_type='glb') 
            
            if glb_path.exists():
                return glb_path
            return None
        except: 
            return None
    
    def compress_file(self, file_path: Path) -> Optional[Path]: 
        """压缩单个文件""" 
        zip_path = file_path.with_suffix(file_path.suffix + '.zip') 
        
        try: 
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf: 
                zipf.write(file_path, file_path.name) 
            return zip_path
        except: 
            return None
    
    def safe_compress_directory(self, dir_path: Path, zip_path: Path) -> bool:
        """安全压缩目录"""
        try:
            gc.collect()
            
            files = [f for f in dir_path.rglob('*') if f.is_file()]
            
            if not files:
                return False
            
            total_size = sum(f.stat().st_size for f in files)
            total_size_mb = total_size / (1024 * 1024)
            
            print(f"   {len(files)} 个文件, 总计 {total_size_mb:.2f} MB")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for file in files:
                    arcname = file.relative_to(dir_path)
                    with open(file, 'rb') as f:
                        data = f.read()
                    zipf.writestr(str(arcname), data)
            
            compressed_size = zip_path.stat().st_size / (1024 * 1024)
            ratio = (1 - compressed_size / total_size_mb) * 100 if total_size_mb > 0 else 0
            
            print(f"   OK 压缩完成: {compressed_size:.2f} MB (减少{ratio:.1f}%)")
            return True
        except Exception as e:
            print(f"   压缩失败: {e}")
            return False
    
    def convert_whole(self, input_file: Path, output_file: Path, doc, shape_tool,
                     ascii_mode: bool, optimize: bool, export_glb: bool, auto_zip: bool,
                     linear_def: float) -> bool:
        """转换完整模型"""
        print("\n[整体模式] 导出完整模型...")
        
        free_shapes = TDF_LabelSequence()
        try:
            shape_tool.GetFreeShapes_s(free_shapes)
        except:
            shape_tool.GetFreeShapes(free_shapes)
        
        if free_shapes.Length() == 0:
            print("ERROR: 没有找到有效形状")
            return False
        
        main_label = free_shapes.Value(1)
        shape = self.get_shape_from_label(main_label, shape_tool)
        
        if shape is None or shape.IsNull():
            print("ERROR: 主形状无效")
            return False
        
        print("   网格化...", end='', flush=True)
        if not self.mesh_shape(shape, linear_def):
            print(" FAILED")
            return False
        print(" OK")
        
        print(f"   保存 STL: {output_file.name}...", end='', flush=True)
        if not self.convert_shape_to_stl(shape, output_file, ascii_mode):
            print(" FAILED")
            return False
        
        stl_size = output_file.stat().st_size / (1024 * 1024)
        print(f" OK ({stl_size:.2f} MB)")
        
        if optimize:
            print("   优化 STL...", end='', flush=True)
            if self.optimize_stl(output_file):
                new_size = output_file.stat().st_size / (1024 * 1024)
                print(f" OK ({new_size:.2f} MB)")
            else:
                print(" 跳过")
        
        glb_file = None
        if export_glb:
            glb_path = output_file.with_suffix('.glb')
            print(f"   导出 GLB: {glb_path.name}...", end='', flush=True)
            
            glb_file = self.export_glb_native(doc, glb_path)
            if glb_file is None:
                glb_file = self.export_glb_trimesh(output_file, glb_path)
            
            if glb_file:
                glb_size = glb_file.stat().st_size / (1024 * 1024)
                print(f" OK ({glb_size:.2f} MB)")
            else:
                print(" FAILED")
        
        if auto_zip:
            print("   压缩文件...")
            zip_stl = self.compress_file(output_file)
            if zip_stl:
                zip_size = zip_stl.stat().st_size / (1024 * 1024)
                print(f"      STL.zip: {zip_size:.2f} MB")
            
            if glb_file:
                zip_glb = self.compress_file(glb_file)
                if zip_glb:
                    zip_size = zip_glb.stat().st_size / (1024 * 1024)
                    print(f"      GLB.zip: {zip_size:.2f} MB")
        
        return True
    
    def convert_parts(self, input_file: Path, output_file: Path, doc, shape_tool,
                     ascii_mode: bool, optimize: bool, export_glb: bool,
                     linear_def: float) -> bool:
        """拆分部件并转换"""
        print("\n[部件模式] 拆分装配体...")
        
        # 收集所有唯一部件
        parts = self.collect_parts(shape_tool, doc)
        
        if not parts:
            print("ERROR: 未找到任何部件")
            return False
        
        print(f"   识别到 {len(parts)} 个唯一部件")
        
        # 创建临时目录
        temp_dir_stl = output_file.parent / f"{output_file.stem}_parts_temp"
        temp_dir_stl.mkdir(exist_ok=True)
        
        temp_dir_glb = None
        if export_glb:
            temp_dir_glb = output_file.parent / f"{output_file.stem}_parts_glb_temp"
            temp_dir_glb.mkdir(exist_ok=True)
        
        success_count = 0
        failed_count = 0
        stl_files = []
        glb_tasks = []
        
        BATCH_SIZE = 50
        
        for idx, part in enumerate(parts, 1):
            shape = part['shape']
            name = part['name']
            raw_name = part['raw_name']
            
            # 简化输出
            if idx <= 10 or idx == len(parts) or idx % 100 == 0:
                print(f"\n--- 部件 [{idx}/{len(parts)}]: {raw_name} ---")
            elif idx == 11:
                print(f"\n... 处理中 ...")
            
            # 网格化
            if not self.mesh_shape(shape, linear_def):
                failed_count += 1
                continue
            
            # 导出 STL
            stl_path = temp_dir_stl / f"{name}.stl"
            
            if self.convert_shape_to_stl(shape, stl_path, ascii_mode):
                stl_files.append(stl_path)
                success_count += 1
                
                if export_glb and temp_dir_glb:
                    glb_tasks.append((stl_path, temp_dir_glb / f"{name}.glb"))
                
                if idx <= 10 or idx == len(parts):
                    stl_size = stl_path.stat().st_size / (1024 * 1024)
                    print(f"   STL: {stl_path.name} ({stl_size:.2f} MB)")
            else:
                failed_count += 1
            
            if idx % BATCH_SIZE == 0:
                gc.collect()
        
        print(f"\nSTL 转换完成: 成功 {success_count}, 失败 {failed_count}")
        
        # 优化 STL
        if optimize and stl_files:
            print(f"\n优化 {len(stl_files)} 个 STL 文件...")
            for stl_path in stl_files:
                self.optimize_stl(stl_path)
        
        gc.collect()
        
        # 批量生成 GLB
        if export_glb and glb_tasks:
            print(f"\n生成 {len(glb_tasks)} 个 GLB 文件...")
            glb_success = 0
            
            for idx, (stl_path, glb_path) in enumerate(glb_tasks, 1):
                result = self.export_glb_trimesh(stl_path, glb_path)
                if result:
                    glb_success += 1
                
                if idx % BATCH_SIZE == 0:
                    gc.collect()
            
            print(f"GLB 转换完成: 成功 {glb_success}/{len(glb_tasks)}")
        
        gc.collect()
        time.sleep(0.5)
        
        # 压缩目录
        print(f"\n压缩文件...")
        zip_stl = output_file.parent / f"{output_file.stem}_parts.zip"
        zip_glb = None
        
        if self.safe_compress_directory(temp_dir_stl, zip_stl):
            print(f"   STL 压缩完成: {zip_stl.name}")
        else:
            print(f"   STL 压缩失败")
        
        if export_glb and temp_dir_glb:
            zip_glb = output_file.parent / f"{output_file.stem}_parts_glb.zip"
            if self.safe_compress_directory(temp_dir_glb, zip_glb):
                print(f"   GLB 压缩完成: {zip_glb.name}")
            else:
                print(f"   GLB 压缩失败")
        
        # 清理临时目录
        print(f"\n清理临时文件...", end='', flush=True)
        
        gc.collect()
        time.sleep(0.5)
        
        try:
            shutil.rmtree(temp_dir_stl, ignore_errors=True)
            if temp_dir_glb:
                shutil.rmtree(temp_dir_glb, ignore_errors=True)
            print(" OK")
        except Exception as e:
            print(f" 警告: {e}")
        
        # 输出统计
        print(f"\n{'='*70}")
        print(f"部件拆分完成!")
        print(f"\n输出文件:")
        
        if zip_stl.exists():
            zip_size = zip_stl.stat().st_size / (1024 * 1024)
            print(f"   {zip_stl.name} ({zip_size:.2f} MB, {success_count} 个STL部件)")
        
        if zip_glb and zip_glb.exists():
            zip_glb_size = zip_glb.stat().st_size / (1024 * 1024)
            print(f"   {zip_glb.name} ({zip_glb_size:.2f} MB)")
        
        print(f"{'='*70}\n")
        
        return success_count > 0
    
    def convert_file(self, input_path: str, output_path: Optional[str] = None, 
                ascii_mode=False, optimize=False, export_glb=False, 
                auto_zip=False, export_mode='whole') -> bool: 
        """转换单个文件"""
        input_file = Path(input_path).resolve()
        start_time = time.time()
        
        doc = None
        
        if not input_file.exists():
            print(f"ERROR: 文件不存在 - {input_path}", file=sys.stderr)
            return False
        
        if input_file.suffix not in self.SUPPORTED_EXTENSIONS:
            print(f"ERROR: 不支持的文件格式 - {input_file.suffix}", file=sys.stderr)
            return False
        
        if output_path is None:
            output_file = input_file.with_suffix('.stl')
        else:
            output_file = Path(output_path).resolve()
            
            if str(output_path).endswith(('/', '\\')):
                output_file = output_file / f"{input_file.stem}.stl"
            elif output_file.exists() and output_file.is_dir():
                output_file = output_file / f"{input_file.stem}.stl"
            elif output_file.suffix.lower() != '.stl':
                if not output_file.parent.exists():
                    output_file = output_file / f"{input_file.stem}.stl"
                else:
                    output_file = output_file.with_suffix('.stl')
        
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"ERROR: 无法创建输出目录 - {output_file.parent}", file=sys.stderr)
            return False
        
        input_size = input_file.stat().st_size / (1024 * 1024)
        print(f"\n{'='*70}")
        print(f"输入文件: {input_file.name} ({input_size:.2f} MB)")
        print(f"输出路径: {output_file.parent}")
        print(f"质量设置: {self.quality_name}")
        print(f"并行处理: {'启用' if self.parallel else '禁用'}")
        print(f"导出模式: {export_mode}")
        if optimize:
            print(f"网格优化: 启用")
        if export_glb:
            print(f"GLB导出: 启用")
        if auto_zip:
            print(f"自动压缩: 启用")
        print(f"{'='*70}")
        
        try:
            print("[1/4] 读取STEP文件...", end='', flush=True)
            
            app = XCAFApp_Application.GetApplication_s()
            doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
            
            step_reader = STEPCAFControl_Reader()
            step_reader.SetNameMode(True)
            step_reader.SetColorMode(True)
            
            status = step_reader.ReadFile(str(input_file))
            
            if status != IFSelect_RetDone:
                print(f"\nERROR: 无法读取STEP文件", file=sys.stderr)
                return False
            print(" OK")
            
            print("[2/4] 传输几何数据...", end='', flush=True)
            step_reader.Transfer(doc)
            
            shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
            print(" OK")
            
            print("[3/4] 分析模型...", end='', flush=True)
            
            free_shapes = TDF_LabelSequence()
            try:
                shape_tool.GetFreeShapes_s(free_shapes)
            except:
                shape_tool.GetFreeShapes(free_shapes)
            
            linear_def = self.linear_deflection
            
            if free_shapes.Length() > 0:
                first_label = free_shapes.Value(1)
                first_shape = self.get_shape_from_label(first_label, shape_tool)
                
                if first_shape and not first_shape.IsNull():
                    if self.relative:
                        calculated_deflection, max_dim, dims = self.calculate_deflection(
                            first_shape, self.linear_deflection
                        )
                        linear_def = calculated_deflection
                        print(f" OK")
                        print(f"   模型尺寸: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")
                        print(f"   网格精度: {linear_def:.4f} mm (相对误差 {self.linear_deflection*100}%)")
                    else:
                        print(f" OK")
                        print(f"   网格精度: {linear_def:.4f} mm (绝对误差)")
                else:
                    print(" OK (使用默认精度)")
            else:
                print(" OK (使用默认精度)")
            
            print("[4/4] 执行转换...")
            
            result = False
            
            if export_mode == 'whole':
                result = self.convert_whole(input_file, output_file, doc, shape_tool,
                                           ascii_mode, optimize, export_glb, auto_zip, linear_def)
            
            elif export_mode == 'parts':
                result = self.convert_parts(input_file, output_file, doc, shape_tool,
                                           ascii_mode, optimize, export_glb, linear_def)
            
            elif export_mode == 'both':
                print("\n--- 整体模型 ---")
                result1 = self.convert_whole(input_file, output_file, doc, shape_tool,
                                            ascii_mode, optimize, export_glb, auto_zip, linear_def)
                
                print("\n--- 拆分部件 ---")
                result2 = self.convert_parts(input_file, output_file, doc, shape_tool,
                                            ascii_mode, optimize, export_glb, linear_def)
                
                result = result1 or result2
            
            elapsed_time = time.time() - start_time
            
            print(f"\n{'='*70}")
            if result:
                print(f"SUCCESS 转换成功!")
            else:
                print(f"转换完成（部分失败）")
            print(f"   总耗时: {elapsed_time:.2f} 秒")
            print(f"   输出目录: {output_file.parent.absolute()}")
            print(f"{'='*70}\n")
            
            return result
            
        except Exception as e:
            print(f"\nERROR: 转换失败", file=sys.stderr)
            print(f"   详细信息: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False
        
        finally:
            try:
                if doc is not None:
                    del doc
                gc.collect()
            except:
                pass
    
    def convert_directory(self, input_dir: str, output_dir: Optional[str] = None, 
                         ascii_mode=False, optimize=False, export_glb=False, 
                         auto_zip=False, export_mode='whole') -> dict: 
        """批量转换目录"""
        input_path = Path(input_dir)
        
        if not input_path.exists() or not input_path.is_dir():
            print(f"ERROR: 目录不存在 - {input_dir}", file=sys.stderr)
            return {'success': 0, 'failed': 0, 'total': 0}
        
        if output_dir is None:
            output_path = input_path
        else:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        
        files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            files.extend(input_path.glob(f"*{ext}"))
        
        if not files:
            print(f"WARNING: 未找到STEP/STP文件 - {input_dir}", file=sys.stderr)
            return {'success': 0, 'failed': 0, 'total': 0}
        
        print(f"\n找到 {len(files)} 个文件待转换")
        
        results = {'success': 0, 'failed': 0, 'total': len(files)}
        start_time = time.time()
        
        for idx, file in enumerate(files, 1):
            print(f"\n{'#'*70}")
            print(f"[{idx}/{len(files)}] 处理: {file.name}")
            print(f"{'#'*70}")
            output_file = output_path / f"{file.stem}.stl"
            
            if self.convert_file(str(file), str(output_file), ascii_mode,
                               optimize, export_glb, auto_zip, export_mode):
                results['success'] += 1
            else:
                results['failed'] += 1
        
        total_time = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"批量转换完成!")
        print(f"   总计: {results['total']} 个文件")
        print(f"   成功: {results['success']}")
        print(f"   失败: {results['failed']}")
        print(f"   总耗时: {total_time:.2f} 秒")
        print(f"   输出目录: {output_path.absolute()}")
        print(f"{'='*70}\n")
        
        return results

def main():
    parser = argparse.ArgumentParser(
        description='STEP/STP 转 STL/GLB 转换工具 (cadquery-ocp)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

  1. 基础转换（完整模型）:
     python step2stl.py model.step

  2. 拆分部件:
     python step2stl.py model.step --export-mode parts

  3. 同时导出完整模型和部件:
     python step2stl.py model.step --export-mode both

  4. 高质量 + 优化 + GLB:
     python step2stl.py model.step -q high --optimize --glb

  5. 批量转换:
     python step2stl.py input_dir/ output_dir/ --export-mode parts

导出模式:
   whole - 完整模型（默认）
   parts - 只导出部件（自动打包为zip）
   both  - 完整模型 + 部件

质量预设:
   draft  - 草图 (最快)
   low    - 低质量 [默认]
   medium - 中等质量
   high   - 高质量
   ultra  - 超高质量 (最慢)

依赖安装:
   Windows 7:  pip install cadquery-ocp==7.5.3
   Mac M2:     pip install cadquery-ocp
   优化功能:   pip install trimesh numpy
        """
    )
    
    parser.add_argument('input', help='输入文件或目录路径')
    
    parser.add_argument('output', nargs='?', default=None,
                       help='输出文件或目录路径（可选）')
    
    parser.add_argument('-q', '--quality',
                       choices=['draft', 'low', 'medium', 'high', 'ultra'],
                       default='low', help='质量预设 (默认: low)')
    
    parser.add_argument('-l', '--linear-deflection', type=float, default=None,
                       help='线性偏差（覆盖质量预设）')
    
    parser.add_argument('-a', '--angular-deflection', type=float, default=None,
                       help='角度偏差（覆盖质量预设）')
    
    parser.add_argument('--absolute', action='store_true',
                       help='使用绝对误差而非相对误差')
    
    parser.add_argument('--no-parallel', action='store_true',
                       help='禁用并行处理')
    
    parser.add_argument('--ascii', action='store_true',
                       help='使用ASCII格式输出STL')
    
    parser.add_argument('--optimize', action='store_true',
                       help='优化STL网格')
    
    parser.add_argument('--glb', action='store_true',
                       help='同时导出GLB格式')
    
    parser.add_argument('--export-mode',
                       choices=['whole', 'parts', 'both'],
                       default='whole',
                       help='导出模式: whole=完整模型, parts=部件, both=全部')
    
    parser.add_argument('--zip', action='store_true',
                       help='自动压缩输出文件')
    
    args = parser.parse_args()
    
    if args.optimize and not TRIMESH_AVAILABLE:
        print("WARNING: 优化需要安装 trimesh", file=sys.stderr)
        # print("   安装命令: pip install trimesh numpy", file=sys.stderr)
        # response = input("是否继续? (y/n): ")
        # if response.lower() != 'y':
        #     sys.exit(EXIT_ERROR_IMPORT)
        # args.optimize = False
    
    converter = StepToStlConverter(
        quality=args.quality,
        linear_deflection=args.linear_deflection,
        angular_deflection=args.angular_deflection,
        relative=not args.absolute,
        parallel=not args.no_parallel
    )
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        success = converter.convert_file(
            args.input, args.output, args.ascii,
            args.optimize, args.glb, args.zip, args.export_mode
        )
        sys.exit(EXIT_SUCCESS if success else EXIT_ERROR_CONVERSION_FAILED)
        
    elif input_path.is_dir():
        results = converter.convert_directory(
            args.input, args.output, args.ascii,
            args.optimize, args.glb, args.zip, args.export_mode
        )
        sys.exit(EXIT_SUCCESS if results['failed'] == 0 else EXIT_ERROR_CONVERSION_FAILED)
        
    else:
        print(f"ERROR: 路径不存在 - {args.input}", file=sys.stderr)
        sys.exit(EXIT_ERROR_FILE_NOT_FOUND)

if __name__ == '__main__':
    main()