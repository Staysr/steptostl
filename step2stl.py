#!/usr/bin/env python
# -*- coding: utf-8 -*- 
""" 
STEP/STP to STL Converter
支持网格优化、GLB导出、自动压缩、装配体部件拆分
兼容 Windows 7 + Python 3.8.10
优化：并行处理、快速启动、大文件支持
""" 

import os
import sys
import time
import zipfile
import argparse
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

# 状态码常量
EXIT_SUCCESS = 0
EXIT_ERROR_IMPORT = 1
EXIT_ERROR_FILE_NOT_FOUND = 2
EXIT_ERROR_CONVERSION_FAILED = 3
EXIT_ERROR_INVALID_FORMAT = 4
EXIT_ERROR_WRITE_FAILED = 5

try: 
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib_Add
    from OCC.Core.TopoDS import TopoDS_Shape
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopAbs import TopAbs_COMPOUND
    
    # XCAF相关导入（用于装配体识别）
    try:
        from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
        from OCC.Core.TDocStd import TDocStd_Document
        from OCC.Core.XCAFDoc import (
            XCAFDoc_DocumentTool_ShapeTool,
            XCAFDoc_DocumentTool_ColorTool
        )
        from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
        from OCC.Core.TCollection import TCollection_ExtendedString
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
        XCAF_AVAILABLE = True
    except ImportError:
        XCAF_AVAILABLE = False
        
except ImportError as e: 
    print("❌ 错误: 未安装 pythonocc-core", file=sys.stderr) 
    print(f"原因: {e}", file=sys.stderr) 
    print("请运行: pip install pythonocc-core", file=sys.stderr) 
    sys.exit(EXIT_ERROR_IMPORT) 

# 可选依赖检查
TRIMESH_AVAILABLE = False
try: 
    import trimesh
    import numpy as np
    TRIMESH_AVAILABLE = True
except ImportError: 
    pass

class StepToStlConverter: 
    """STEP/STP 到 STL 转换器（支持装配体拆分）""" 
    
    SUPPORTED_EXTENSIONS = ['.step', '.stp', '.STEP', '.STP'] 
    
    # 质量预设（优化后的参数） 
    QUALITY_PRESETS = { 
        'draft': {'linear': 0.1, 'angular': 1.0, 'name': '草图'}, 
        'low': {'linear': 0.05, 'angular': 0.8, 'name': '低质量'}, 
        'medium': {'linear': 0.01, 'angular': 0.5, 'name': '中等质量'}, 
        'high': {'linear': 0.005, 'angular': 0.3, 'name': '高质量'}, 
        'ultra': {'linear': 0.001, 'angular': 0.1, 'name': '超高质量'} 
    } 
    
    def __init__(self, quality='low', linear_deflection=None, 
                 angular_deflection=None, relative=True, parallel=True): 
        """ 
        初始化转换器
        
        Args: 
            quality: 质量预设 (draft/low/medium/high/ultra) 
            linear_deflection: 线性偏差（覆盖预设） 
            angular_deflection: 角度偏差（覆盖预设） 
            relative: 是否使用相对误差（推荐） 
            parallel: 是否启用并行处理（推荐） 
        """ 
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
        self.parallel = parallel  # 并行处理标志
    
    def get_bounding_box_size(self, shape): 
        """获取模型包围盒尺寸""" 
        bbox = Bnd_Box() 
        brepbndlib_Add(shape, bbox) 
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get() 
        
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        max_dim = max(dx, dy, dz) 
        return max_dim, (dx, dy, dz) 
    
    def calculate_deflection(self, shape, quality_factor=0.05): 
        """ 
        根据模型尺寸自动计算合适的偏差值
        
        Args: 
            shape: 模型形状
            quality_factor: 质量系数（相对于模型尺寸） 
        
        Returns: 
            float: 计算出的线性偏差
        """ 
        max_dim, dimensions = self.get_bounding_box_size(shape) 
        
        if self.relative: 
            # 相对误差：基于模型最大尺寸
            deflection = max_dim * quality_factor
        else: 
            # 绝对误差
            deflection = quality_factor
        
        return deflection, max_dim, dimensions

    def extract_assembly_components(self, input_path: str) -> List[Tuple[TopoDS_Shape, str, Optional[Tuple[float, float, float]]]]: 
        """ 
        从STEP文件中提取装配体的各个部件（修复版：正确提取名称）
        
        Args: 
            input_path: STEP文件路径
            
        Returns: 
            List[Tuple[shape, name, color]]: 部件列表
        """ 
        if not XCAF_AVAILABLE: 
            print("⚠️  警告: 未找到XCAF模块，无法识别装配体部件", file=sys.stderr) 
            return [] 
        
        try: 
            print("🔍 [部件识别] 使用XCAF API读取...", end='', flush=True) 
            
            # 导入额外需要的模块
            from OCC.Core.TDataStd import TDataStd_Name
            from OCC.Core.TDocStd import TDocStd_Document
            from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
            from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
            from OCC.Core.TDF import TDF_LabelSequence
            from OCC.Core.TopAbs import TopAbs_SOLID
            from collections import defaultdict
            import re
            
            # 1. 创建文档和读取器
            doc = TDocStd_Document("pythonocc-doc")
            shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
            color_tool = XCAFDoc_DocumentTool.ColorTool(doc.Main())
            
            reader = STEPCAFControl_Reader()
            reader.SetColorMode(True)
            reader.SetLayerMode(True)
            reader.SetNameMode(True)
            
            if reader.ReadFile(str(input_path)) != 1:
                print(" ❌ (无法读取文件)")
                return []
            
            if not reader.Transfer(doc):
                print(" ❌ (传输失败)")
                return []
            
            print(" ✓")
            
            # 2. 获取所有标签
            all_labels = TDF_LabelSequence()
            shape_tool.GetShapes(all_labels)
            
            total_records = all_labels.Length()
            print(f"🔍 [部件识别] 分析 {total_records} 个元素...")
            
            components = []
            name_counter = defaultdict(int)  # 用于处理重复名称
            seen_shapes = set()
            
            # 3. 辅助函数：从标签提取名称
            def get_name_from_label(label):
                """从标签提取名称（核心修复）"""
                name_attr = TDataStd_Name()
                try:
                    # 尝试 GetID() 或 GetID_s()
                    try:
                        guid = TDataStd_Name.GetID()
                    except AttributeError:
                        guid = TDataStd_Name.GetID_s()
                    
                    if label.FindAttribute(guid, name_attr):
                        ext_str = name_attr.Get()
                        # 转换为字符串
                        if hasattr(ext_str, 'ToExtString'):
                            return ext_str.ToExtString()
                        else:
                            return str(ext_str)
                except:
                    pass
                return None
            
            # 4. 辅助函数：从标签获取形状
            def get_shape_from_label(label):
                """从标签获取形状"""
                try:
                    # 尝试不同的API版本
                    try:
                        return shape_tool.GetShape(label)
                    except:
                        try:
                            from OCC.Core.XCAFDoc import XCAFDoc_ShapeTool
                            return XCAFDoc_ShapeTool.GetShape(label)
                        except:
                            return None
                except:
                    return None
            
            # 5. 辅助函数：获取颜色
            def get_color_from_label(label, shape):
                """从标签获取颜色"""
                try:
                    from OCC.Core.XCAFDoc import XCAFDoc_ColorGen
                    color = Quantity_Color()
                    if color_tool.GetColor(shape, XCAFDoc_ColorGen, color):
                        return (color.Red(), color.Green(), color.Blue())
                except:
                    pass
                return None
            
            # 6. 辅助函数：清理文件名
            def sanitize_filename(name):
                """清理文件名（去除非法字符）"""
                if not name:
                    return "unknown"
                # 替换非法字符
                cleaned = re.sub(r'[\\/*?:"<>|]', "_", str(name)).strip()
                # 转小写（避免Windows文件名冲突）
                return cleaned.lower() if cleaned else "unknown"
            
            # 7. 遍历所有标签
            for i in range(1, total_records + 1):
                try:
                    label = all_labels.Value(i)
                    
                    # 获取形状
                    shape = get_shape_from_label(label)
                    if not shape or shape.IsNull():
                        continue
                    
                    # 只保留SOLID类型（过滤掉EDGE、COMPOUND等）
                    if shape.ShapeType() != TopAbs_SOLID:
                        continue
                    
                    # 去重
                    shape_id = id(shape)
                    if shape_id in seen_shapes:
                        continue
                    seen_shapes.add(shape_id)
                    
                    # 提取名称（核心修复）
                    raw_name = get_name_from_label(label)
                    
                    # 如果当前标签没有名称，尝试从父标签获取
                    if not raw_name:
                        try:
                            father_label = label.Father()
                            if not father_label.IsNull():
                                raw_name = get_name_from_label(father_label)
                        except:
                            pass
                    
                    # 如果仍然没有名称，尝试从引用形状获取（GetReferredShape）
                    if not raw_name:
                        try:
                            referred_label = label
                            if shape_tool.GetReferredShape(label, referred_label):
                                if referred_label != label:
                                    raw_name = get_name_from_label(referred_label)
                        except:
                            pass
                    
                    # 如果还是没有名称，使用默认名称
                    if not raw_name or raw_name.strip() == "":
                        raw_name = "Part"
                    
                    # 清理名称
                    safe_name = sanitize_filename(raw_name)
                    
                    # 处理重复名称（关键：避免覆盖）
                    name_counter[safe_name] += 1
                    if name_counter[safe_name] > 1:
                        final_name = f"{safe_name}_{name_counter[safe_name]}"
                    else:
                        final_name = safe_name
                    
                    # 获取颜色
                    color = get_color_from_label(label, shape)
                    
                    # 添加到结果
                    components.append((shape, final_name, color))
                    
                    color_info = f" (颜色: RGB{color})" if color else ""
                    print(f"   ✓ 部件 {len(components)}: {final_name}{color_info}")
                
                except Exception as item_error:
                    # 跳过错误的项
                    continue
            
            if components:
                print(f"🔍 [部件识别] 成功识别 {len(components)} 个有效SOLID部件")
                return components
            else:
                print("⚠️  警告: 未找到有效SOLID部件")
                return []
        
        except Exception as e:
            print(f" ❌ (失败: {str(e)})")
            import traceback
            traceback.print_exc(file=sys.stderr)
            return []    

    def optimize_stl(self, stl_path: Path) -> Optional[Path]: 
        """ 
        优化STL文件（去除重复顶点，减小文件） 
        
        Args: 
            stl_path: STL文件路径
            
        Returns: 
            Path: 优化后的文件路径，失败返回None
        """ 
        if not TRIMESH_AVAILABLE: 
            print("⚠️  警告: 未安装trimesh，跳过优化", file=sys.stderr) 
            print("   安装命令: pip install trimesh", file=sys.stderr) 
            return None
        
        try: 
            print("🔧 [优化] 加载STL网格...", end='', flush=True) 
            original_size = stl_path.stat().st_size / (1024 * 1024) 
            
            # 加载STL（使用process=False避免自动处理） 
            mesh = trimesh.load_mesh(str(stl_path), process=False) 
            print(" ✓") 
            
            # 统计原始信息
            original_vertices = len(mesh.vertices) 
            original_faces = len(mesh.faces) 
            
            print(f"🔧 [优化] 原始网格: {original_vertices:,} 顶点, {original_faces:,} 三角面") 
            
            # 1. 合并重复顶点（最主要的优化） 
            print("🔧 [优化] 合并重复顶点...", end='', flush=True) 
            mesh.merge_vertices() 
            print(" ✓") 
            
            # 2. 移除未引用的顶点
            print("🔧 [优化] 清理未使用顶点...", end='', flush=True) 
            mesh.remove_unreferenced_vertices() 
            print(" ✓") 
            
            # 3. 移除退化面（使用新API） 
            print("🔧 [优化] 清理无效面...", end='', flush=True) 
            if hasattr(mesh, 'nondegenerate_faces'): 
                # 新版本 API
                mesh.update_faces(mesh.nondegenerate_faces()) 
            elif hasattr(mesh, 'remove_degenerate_faces'): 
                # 旧版本 API（已弃用但还能用） 
                import warnings
                with warnings.catch_warnings(): 
                    warnings.simplefilter("ignore", DeprecationWarning) 
                    mesh.remove_degenerate_faces() 
            else: 
                # 手动过滤
                valid_faces = mesh.area_faces > 1e-10
                if not all(valid_faces): 
                    mesh.update_faces(valid_faces) 
            print(" ✓") 
            
            # 4. 移除重复面（使用新API） 
            print("🔧 [优化] 去除重复面...", end='', flush=True) 
            if hasattr(mesh, 'unique_faces'): 
                # 新版本 API
                mesh.update_faces(mesh.unique_faces()) 
            elif hasattr(mesh, 'remove_duplicate_faces'): 
                # 旧版本 API（已弃用但还能用） 
                import warnings
                with warnings.catch_warnings(): 
                    warnings.simplefilter("ignore", DeprecationWarning) 
                    mesh.remove_duplicate_faces() 
            else: 
                # 手动去重
                unique_faces = trimesh.grouping.unique_rows(mesh.faces)[0] 
                if len(unique_faces) < len(mesh.faces): 
                    mesh.update_faces(mesh.faces[unique_faces]) 
            print(" ✓") 
            
            # 统计优化后信息
            optimized_vertices = len(mesh.vertices) 
            optimized_faces = len(mesh.faces) 
            
            vertex_reduction = (1 - optimized_vertices / original_vertices) * 100 if original_vertices > 0 else 0
            face_reduction = (1 - optimized_faces / original_faces) * 100 if original_faces > 0 else 0
            
            print(f"🔧 [优化] 优化后: {optimized_vertices:,} 顶点 (↓{vertex_reduction:.1f}%), " 
                  f"{optimized_faces:,} 三角面 (↓{face_reduction:.1f}%)") 
            
            # 简化版验证：只检查基本有效性
            print("🔧 [优化] 验证网格...", end='', flush=True) 
            
            # 检查面索引是否有效
            max_index = len(mesh.vertices) - 1
            if len(mesh.faces) > 0 and mesh.faces.max() > max_index: 
                print(f"\n⚠️  警告: 检测到无效的面索引，跳过优化", file=sys.stderr) 
                return None
            
            # 检查是否有面
            if len(mesh.faces) == 0: 
                print(f"\n⚠️  警告: 优化后没有三角面，跳过优化", file=sys.stderr) 
                return None
            
            print(" ✓") 
            
            # 保存优化后的STL（使用临时文件防止数据丢失） 
            print("🔧 [优化] 保存优化后的STL...", end='', flush=True) 
            
            temp_path = stl_path.parent / f"{stl_path.stem}_temp.stl" 
            
            try: 
                # 显式指定文件类型为 stl
                mesh.export(str(temp_path), file_type='stl') 
                
                # 验证导出的文件
                if temp_path.exists() and temp_path.stat().st_size > 0: 
                    # 成功，替换原文件
                    temp_path.replace(stl_path) 
                    print(" ✓") 
                else: 
                    print(f"\n⚠️  警告: 导出的文件无效，保留原始文件", file=sys.stderr) 
                    if temp_path.exists(): 
                        temp_path.unlink() 
                    return None
                    
            except Exception as export_error: 
                print(f"\n⚠️  警告: 导出失败 - {str(export_error)}", file=sys.stderr) 
                if temp_path.exists(): 
                    temp_path.unlink() 
                return None
            
            optimized_size = stl_path.stat().st_size / (1024 * 1024) 
            size_reduction = (1 - optimized_size / original_size) * 100 if original_size > 0 else 0
            
            print(f"✅ [优化] 文件大小: {original_size:.2f} MB → {optimized_size:.2f} MB " 
                  f"(↓{size_reduction:.1f}%)") 
            
            return stl_path
            
        except Exception as e: 
            print(f"\n⚠️  警告: STL优化失败 - {str(e)}", file=sys.stderr) 
            import traceback
            traceback.print_exc(file=sys.stderr) 
            return None
    
    def export_glb(self, stl_path: Path, glb_path: Optional[Path] = None, 
                   color: Optional[Tuple[float, float, float]] = None) -> Optional[Path]: 
        """ 
        将STL转换为GLB格式
        
        Args: 
            stl_path: STL文件路径
            glb_path: GLB输出路径（可选） 
            color: RGB颜色元组 (r, g, b) 范围0-1（可选）
            
        Returns: 
            Path: GLB文件路径，失败返回None
        """ 
        if not TRIMESH_AVAILABLE: 
            print("⚠️  警告: 未安装trimesh，无法导出GLB", file=sys.stderr) 
            print("   安装命令: pip install trimesh", file=sys.stderr) 
            return None
        
        if glb_path is None: 
            glb_path = stl_path.with_suffix('.glb') 
        
        try: 
            print(f"📦 [GLB] 转换 {stl_path.name} → {glb_path.name}...", end='', flush=True) 
            
            # 加载STL
            mesh = trimesh.load_mesh(str(stl_path), process=False) 
            
            # 应用颜色（如果提供）
            if color:
                # 转换为0-255范围
                color_255 = [int(c * 255) for c in color] + [255]  # RGBA
                mesh.visual = trimesh.visual.ColorVisuals(
                    mesh=mesh,
                    face_colors=color_255
                )
            
            # 导出为GLB
            mesh.export(str(glb_path), file_type='glb') 
            print(" ✓") 
            
            return glb_path
            
        except Exception as e: 
            print(f"\n⚠️  警告: GLB导出失败 - {str(e)}", file=sys.stderr) 
            return None
    
    def compress_file(self, file_path: Path) -> Optional[Path]: 
        """ 
        压缩文件为ZIP
        
        Args: 
            file_path: 要压缩的文件路径
            
        Returns: 
            Path: ZIP文件路径，失败返回None
        """ 
        zip_path = file_path.with_suffix(file_path.suffix + '.zip') 
        
        try: 
            print(f"🗜️  [压缩] 压缩 {file_path.name}...", end='', flush=True) 
            
            original_size = file_path.stat().st_size / (1024 * 1024) 
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf: 
                zipf.write(file_path, file_path.name) 
            
            compressed_size = zip_path.stat().st_size / (1024 * 1024) 
            ratio = (1 - compressed_size / original_size) * 100
            
            print(" ✓") 
            print(f"✅ [压缩] {zip_path.name}: {original_size:.2f} MB → {compressed_size:.2f} MB " 
                  f"(↓{ratio:.1f}%)") 
            
            return zip_path
            
        except Exception as e: 
            print(f"\n⚠️  警告: 压缩失败 - {str(e)}", file=sys.stderr) 
            return None
    
    def compress_directory(self, dir_path: Path, zip_path: Path) -> Optional[Path]:
        """
        压缩整个目录为ZIP
        
        Args:
            dir_path: 要压缩的目录路径
            zip_path: ZIP输出路径
            
        Returns:
            Path: ZIP文件路径，失败返回None
        """
        try:
            print(f"🗜️  [压缩] 压缩目录 {dir_path.name}...", end='', flush=True)
            
            # 计算目录总大小
            total_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
            total_size_mb = total_size / (1024 * 1024)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                for file in dir_path.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(dir_path)
                        zipf.write(file, arcname)
            
            compressed_size = zip_path.stat().st_size / (1024 * 1024)
            ratio = (1 - compressed_size / total_size_mb) * 100 if total_size_mb > 0 else 0
            
            print(" ✓")
            print(f"✅ [压缩] {zip_path.name}: {total_size_mb:.2f} MB → {compressed_size:.2f} MB "
                  f"(↓{ratio:.1f}%)")
            
            return zip_path
            
        except Exception as e:
            print(f"\n⚠️  警告: 目录压缩失败 - {str(e)}", file=sys.stderr)
            return None
    
    def convert_shape_to_stl(self, shape: TopoDS_Shape, output_path: Path, 
                            ascii_mode: bool = False) -> bool:
        """
        将单个形状转换为STL
        
        Args:
            shape: 要转换的形状
            output_path: 输出STL路径
            ascii_mode: 是否使用ASCII模式
            
        Returns:
            bool: 是否成功
        """
        try:
            # 计算网格参数
            if self.relative:
                calculated_deflection, max_dim, dims = self.calculate_deflection(
                    shape, self.linear_deflection
                )
                linear_def = calculated_deflection
            else:
                linear_def = self.linear_deflection
            
            # 生成网格
            mesh = BRepMesh_IncrementalMesh(
                shape,
                linear_def,
                False,
                self.angular_deflection,
                self.parallel
            )
            mesh.Perform()
            
            if not mesh.IsDone():
                return False
            
            # 写入STL
            stl_writer = StlAPI_Writer()
            stl_writer.SetASCIIMode(ascii_mode)
            success = stl_writer.Write(shape, str(output_path))
            
            # 清理
            del mesh
            
            return success
            
        except Exception as e:
            print(f"\n⚠️  警告: 形状转换失败 - {str(e)}", file=sys.stderr)
            return False
    
    def convert_file(self, input_path: str, output_path: Optional[str] = None, 
                ascii_mode=False, optimize=False, export_glb=False, 
                auto_zip=False, export_mode='whole') -> bool: 
        """ 
        转换单个文件
        
        Args: 
            input_path: 输入文件路径
            output_path: 输出文件路径（可选） 
            ascii_mode: 是否使用ASCII模式
            optimize: 是否优化STL
            export_glb: 是否导出GLB
            auto_zip: 是否自动压缩（仅对whole模式的完整文件生效）
            export_mode: 导出模式 (whole/parts/both)
            
        Returns: 
            bool: 转换是否成功
        """ 
        input_file = Path(input_path).resolve() 
        start_time = time.time() 
        
        # 用于finally中释放资源的变量
        shape = None
        mesh = None
        
        # 检查输入文件
        if not input_file.exists(): 
            print(f"❌ 错误: 文件不存在 - {input_path}", file=sys.stderr) 
            return False
        
        if input_file.suffix not in self.SUPPORTED_EXTENSIONS: 
            print(f"❌ 错误: 不支持的文件格式 - {input_file.suffix}", file=sys.stderr) 
            return False
        
        # 输出路径处理
        if output_path is None: 
            output_file = input_file.with_suffix('.stl') 
        else: 
            output_file = Path(output_path).resolve() 
            
            if str(output_path).endswith(('/', '\\')) or (output_file.exists() and output_file.is_dir()): 
                output_file = output_file / f"{input_file.stem}.stl" 
            elif output_file.suffix.lower() != '.stl': 
                if not output_file.parent.exists(): 
                    output_file = output_file / f"{input_file.stem}.stl" 
                else: 
                    output_file = output_file.with_suffix('.stl') 
        
        # 创建输出目录
        try: 
            output_file.parent.mkdir(parents=True, exist_ok=True) 
        except Exception as e: 
            print(f"❌ 错误: 无法创建输出目录 - {output_file.parent}", file=sys.stderr) 
            print(f"   详细信息: {str(e)}", file=sys.stderr) 
            return False
        
        input_size = input_file.stat().st_size / (1024 * 1024) 
        print(f"\n{'='*70}") 
        print(f"📁 输入文件: {input_file.name} ({input_size:.2f} MB)") 
        print(f"📂 输出目录: {output_file.parent.absolute()}") 
        print(f"⚙️  质量设置: {self.quality_name}") 
        print(f"🚀 并行处理: {'启用' if self.parallel else '禁用'}") 
        print(f"📦 导出模式: {export_mode.upper()}")
        if optimize: 
            print(f"🔧 网格优化: 启用") 
        if export_glb: 
            print(f"📦 GLB导出: 启用") 
        if auto_zip and export_mode == 'whole': 
            print(f"🗜️  自动压缩: 启用") 
        print(f"{'='*70}") 
        
        try:
            # ========================================
            # 根据export_mode选择处理方式
            # ========================================
            
            if export_mode == 'parts':
                # ========================================
                # 模式1: 只生成部件
                # ========================================
                return self._convert_parts_only(
                    input_file, output_file, ascii_mode, 
                    optimize, export_glb
                )
                
            elif export_mode == 'both':
                # ========================================
                # 模式2: 生成完整模型 + 部件
                # ========================================
                # 先生成完整模型
                whole_success = self._convert_whole_model(
                    input_file, output_file, ascii_mode,
                    optimize, export_glb, auto_zip
                )
                
                # 再生成部件
                parts_success = self._convert_parts_only(
                    input_file, output_file, ascii_mode,
                    optimize, export_glb
                )
                
                elapsed_time = time.time() - start_time
                print(f"\n{'='*70}")
                print(f"✅ 转换完成!")
                print(f"   ⏱️  总耗时: {elapsed_time:.2f} 秒")
                print(f"   📍 输出目录: {output_file.parent.absolute()}")
                print(f"{'='*70}\n")
                
                return whole_success or parts_success
                
            else:  # export_mode == 'whole'
                # ========================================
                # 模式3: 只生成完整模型（原逻辑）
                # ========================================
                return self._convert_whole_model(
                    input_file, output_file, ascii_mode,
                    optimize, export_glb, auto_zip
                )
            
        except Exception as e: 
            print(f"\n❌ 错误: 转换失败", file=sys.stderr) 
            print(f"   详细信息: {str(e)}", file=sys.stderr) 
            import traceback
            traceback.print_exc(file=sys.stderr) 
            return False
        
        finally: 
            # 内存释放
            try: 
                if shape is not None: 
                    del shape
                if mesh is not None: 
                    del mesh
                import gc
                gc.collect() 
            except: 
                pass
    
    def _convert_whole_model(self, input_file: Path, output_file: Path,
                            ascii_mode: bool, optimize: bool, 
                            export_glb: bool, auto_zip: bool) -> bool:
        """
        转换完整模型（原逻辑）
        
        Returns:
            bool: 是否成功
        """
        shape = None
        mesh = None
        
        try:
            # 1. 读取STEP文件
            print("📖 [1/4] 读取STEP文件...", end='', flush=True) 
            step_reader = STEPControl_Reader() 
            status = step_reader.ReadFile(str(input_file)) 
            
            if status != IFSelect_RetDone: 
                print(f"\n❌ 错误: 无法读取STEP文件", file=sys.stderr) 
                return False
            print(" ✓") 
            
            # 2. 传输数据
            print("🔄 [2/4] 传输几何数据...", end='', flush=True) 
            step_reader.TransferRoots() 
            shape = step_reader.OneShape() 
            
            if shape.IsNull(): 
                print(f"\n❌ 错误: STEP文件中没有有效的几何体", file=sys.stderr) 
                return False
            print(" ✓") 
            
            # 3. 计算网格参数
            print("📐 [3/4] 分析模型尺寸...", end='', flush=True) 
            
            if self.relative: 
                calculated_deflection, max_dim, dims = self.calculate_deflection( 
                    shape, self.linear_deflection
                ) 
                linear_def = calculated_deflection
                print(f" ✓") 
                print(f"   📏 模型尺寸: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm") 
                print(f"   🎯 网格精度: {linear_def:.4f} mm (相对误差 {self.linear_deflection*100}%)") 
            else: 
                linear_def = self.linear_deflection
                print(f" ✓") 
                print(f"   🎯 网格精度: {linear_def:.4f} mm (绝对误差)") 
            
            # 4. 生成网格
            print("🔨 [4/4] 生成STL网格...", end='', flush=True) 
            mesh = BRepMesh_IncrementalMesh( 
                shape, 
                linear_def, 
                False, 
                self.angular_deflection, 
                self.parallel
            ) 
            mesh.Perform() 
            
            if not mesh.IsDone(): 
                print(f"\n❌ 错误: 网格生成失败", file=sys.stderr) 
                return False
            print(" ✓") 
            
            # 5. 保存STL
            print("💾 保存STL文件...", end='', flush=True) 
            stl_writer = StlAPI_Writer() 
            stl_writer.SetASCIIMode(ascii_mode) 
            success = stl_writer.Write(shape, str(output_file)) 
            
            if not success: 
                print(f"\n❌ 错误: 写入STL文件失败", file=sys.stderr) 
                return False
            print(" ✓") 
            
            original_stl_size = output_file.stat().st_size / (1024 * 1024) 
            print(f"   📊 初始STL大小: {original_stl_size:.2f} MB") 
            
            # 6. 优化STL
            if optimize: 
                print() 
                optimized = self.optimize_stl(output_file) 
                if optimized: 
                    output_file = optimized
            
            # 7. 导出GLB
            glb_file = None
            if export_glb: 
                print()
                glb_file = self.export_glb(output_file) 
            
            # 8. 压缩文件
            if auto_zip: 
                print() 
                self.compress_file(output_file) 
                if glb_file: 
                    self.compress_file(glb_file) 
            
            # 统计信息
            final_stl_size = output_file.stat().st_size / (1024 * 1024) 
            
            print(f"\n{'='*70}") 
            print(f"✅ 转换成功!") 
            print(f"\n📦 输出文件:") 
            print(f"   📄 STL: {output_file.name} ({final_stl_size:.2f} MB)") 
            
            if auto_zip and output_file.with_suffix('.stl.zip').exists(): 
                zip_size = output_file.with_suffix('.stl.zip').stat().st_size / (1024 * 1024) 
                print(f"   🗜️  STL.ZIP: {output_file.stem}.stl.zip ({zip_size:.2f} MB)") 
            
            if glb_file and glb_file.exists(): 
                glb_size = glb_file.stat().st_size / (1024 * 1024) 
                print(f"   📦 GLB: {glb_file.name} ({glb_size:.2f} MB)") 
                
                if auto_zip and glb_file.with_suffix('.glb.zip').exists(): 
                    glb_zip_size = glb_file.with_suffix('.glb.zip').stat().st_size / (1024 * 1024) 
                    print(f"   🗜️  GLB.ZIP: {glb_file.stem}.glb.zip ({glb_zip_size:.2f} MB)") 
            
            print(f"{'='*70}\n") 
            
            return True
            
        finally:
            if shape is not None:
                del shape
            if mesh is not None:
                del mesh
            import gc
            gc.collect()
    
    def _convert_parts_only(self, input_file: Path, output_file: Path,
                           ascii_mode: bool, optimize: bool,
                           export_glb: bool) -> bool:
        """
        只转换部件（拆分装配体）
        
        Returns:
            bool: 是否成功
        """
        try:
            # 1. 提取部件
            components = self.extract_assembly_components(str(input_file))
            
            if not components:
                print("⚠️  未找到部件，尝试作为单一模型处理", file=sys.stderr)
                # 作为单一模型读取
                step_reader = STEPControl_Reader()
                status = step_reader.ReadFile(str(input_file))
                if status == IFSelect_RetDone:
                    step_reader.TransferRoots()
                    shape = step_reader.OneShape()
                    if not shape.IsNull():
                        components = [(shape, "model", None)]
                
                if not components:
                    return False
            
            print(f"\n🔨 开始转换 {len(components)} 个部件...")
            
            # 2. 创建临时目录
            temp_dir_stl = output_file.parent / f"{output_file.stem}_parts_temp"
            temp_dir_stl.mkdir(exist_ok=True)
            
            temp_dir_glb = None
            if export_glb:
                temp_dir_glb = output_file.parent / f"{output_file.stem}_parts_glb_temp"
                temp_dir_glb.mkdir(exist_ok=True)
            
            success_count = 0
            failed_count = 0
            
            # 3. 逐个转换部件
            for idx, (shape, name, color) in enumerate(components, 1):
                print(f"\n--- 部件 [{idx}/{len(components)}]: {name} ---")
                
                # 生成STL
                stl_part_path = temp_dir_stl / f"{name}.stl"
                print(f"📄 生成STL: {stl_part_path.name}...", end='', flush=True)
                
                if self.convert_shape_to_stl(shape, stl_part_path, ascii_mode):
                    print(" ✓")
                    part_size = stl_part_path.stat().st_size / (1024 * 1024)
                    print(f"   大小: {part_size:.2f} MB")
                    
                    # 优化STL
                    if optimize:
                        optimized = self.optimize_stl(stl_part_path)
                        if optimized:
                            stl_part_path = optimized
                    
                    # 生成GLB
                    if export_glb and temp_dir_glb:
                        glb_part_path = temp_dir_glb / f"{name}.glb"
                        self.export_glb(stl_part_path, glb_part_path, color)
                    
                    success_count += 1
                else:
                    print(" ❌")
                    failed_count += 1
            
            print(f"\n📊 部件转换完成: 成功 {success_count}, 失败 {failed_count}")
            
            # 4. 压缩STL部件目录
            zip_stl = output_file.parent / f"{output_file.stem}_parts.zip"
            print()
            self.compress_directory(temp_dir_stl, zip_stl)
            
            # 5. 压缩GLB部件目录
            zip_glb = None
            if export_glb and temp_dir_glb:
                zip_glb = output_file.parent / f"{output_file.stem}_parts_glb.zip"
                print()
                self.compress_directory(temp_dir_glb, zip_glb)
            
            # 6. 删除临时目录
            print(f"\n🧹 清理临时文件...", end='', flush=True)
            shutil.rmtree(temp_dir_stl, ignore_errors=True)
            if temp_dir_glb:
                shutil.rmtree(temp_dir_glb, ignore_errors=True)
            print(" ✓")
            
            # 7. 输出统计
            print(f"\n{'='*70}")
            print(f"✅ 部件拆分完成!")
            print(f"\n📦 输出文件:")
            
            if zip_stl.exists():
                zip_size = zip_stl.stat().st_size / (1024 * 1024)
                print(f"   🗜️  {zip_stl.name} ({zip_size:.2f} MB, {success_count} 个STL部件)")
            
            if zip_glb and zip_glb.exists():
                zip_glb_size = zip_glb.stat().st_size / (1024 * 1024)
                print(f"   🗜️  {zip_glb.name} ({zip_glb_size:.2f} MB, {success_count} 个GLB部件)")
            
            print(f"{'='*70}\n")
            
            return success_count > 0
            
        except Exception as e:
            print(f"\n❌ 错误: 部件转换失败 - {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False
    
    def convert_directory(self, input_dir: str, output_dir: Optional[str] = None, 
                         ascii_mode=False, optimize=False, export_glb=False, 
                         auto_zip=False, export_mode='whole') -> dict: 
        """批量转换目录中的所有STEP/STP文件""" 
        input_path = Path(input_dir) 
        
        if not input_path.exists() or not input_path.is_dir(): 
            print(f"❌ 错误: 目录不存在 - {input_dir}", file=sys.stderr) 
            return {'success': 0, 'failed': 0, 'total': 0} 
        
        # 确定输出目录
        if output_dir is None: 
            output_path = input_path
        else: 
            output_path = Path(output_dir) 
            output_path.mkdir(parents=True, exist_ok=True) 
        
        # 查找所有STEP/STP文件
        files = [] 
        for ext in self.SUPPORTED_EXTENSIONS: 
            files.extend(input_path.glob(f"*{ext}")) 
        
        if not files: 
            print(f"⚠️  警告: 在目录中未找到STEP/STP文件 - {input_dir}", file=sys.stderr) 
            return {'success': 0, 'failed': 0, 'total': 0} 
        
        print(f"\n🔍 找到 {len(files)} 个文件待转换") 
        
        results = {'success': 0, 'failed': 0, 'total': len(files)} 
        start_time = time.time() 
        
        for idx, file in enumerate(files, 1): 
            print(f"\n{'#'*70}") 
            print(f"📦 [{idx}/{len(files)}] 处理: {file.name}") 
            print(f"{'#'*70}") 
            output_file = output_path / f"{file.stem}.stl" 
            
            if self.convert_file(str(file), str(output_file), ascii_mode, 
                               optimize, export_glb, auto_zip, export_mode): 
                results['success'] += 1
            else: 
                results['failed'] += 1
        
        # 总结
        total_time = time.time() - start_time
        print(f"\n{'='*70}") 
        print(f"🎉 批量转换完成!") 
        print(f"   总计: {results['total']} 个文件") 
        print(f"   ✅ 成功: {results['success']}") 
        print(f"   ❌ 失败: {results['failed']}") 
        print(f"   ⏱️  总耗时: {total_time:.2f} 秒") 
        print(f"   📂 输出目录: {output_path.absolute()}") 
        print(f"{'='*70}\n") 
        
        return results

def main(): 
    parser = argparse.ArgumentParser( 
        description='STEP/STP 转 STL 格式转换工具（支持装配体拆分）', 
        formatter_class=argparse.RawDescriptionHelpFormatter, 
        epilog=""" 
📖 使用示例: 

  1️⃣  基础转换（完整模型）: 
     step2stl model.step

  2️⃣  拆分装配体部件: 
     step2stl model.step --export-mode parts

  3️⃣  完整模型 + 部件: 
     step2stl model.step --export-mode both

  4️⃣  部件 + 优化 + GLB: 
     step2stl model.step --export-mode parts --optimize --glb

  5️⃣  全家桶（完整+部件+优化+GLB）: 
     step2stl model.step --export-mode both --optimize --glb

  6️⃣  批量转换: 
     step2stl input_dir/ output_dir/ --export-mode parts --glb

  7️⃣  高质量部件拆分: 
     step2stl model.step -q high --export-mode parts --optimize

📦 导出模式 (--export-mode): 
   whole - 只生成完整模型 (默认，最快) ✨
   parts - 只生成部件ZIP包（拆分装配体）
   both  - 生成完整模型 + 部件ZIP包

🎨 部件功能特性: 
   ✅ 自动识别装配体部件
   ✅ 保留部件名称（无名称自动编号）
   ✅ 提取颜色信息（应用到GLB）
   ✅ 自动压缩为ZIP（不保留临时目录）
   ✅ 支持STL和GLB双格式

⚙️  质量预设: 
   draft  - 草图 (最快，最小) 
   low    - 低质量 (推荐日常) ✨ 默认
   medium - 中等质量
   high   - 高质量
   ultra  - 超高质量 (最慢，最大) 

🚀 性能优化: 
   默认启用并行处理，high质量转换速度提升约30-50% 

🔧 优化选项: 
   --optimize  去除重复顶点，优化网格（推荐） 
   --glb       同时导出GLB格式（支持颜色） 
   --zip       自动压缩完整模型文件（不影响parts模式）

💡 状态码: 
   0 - 转换成功
   1 - 依赖库缺失
   2 - 文件未找到
   3 - 转换失败
   4 - 不支持的格式
   5 - 写入失败

📦 依赖安装: 
   基础功能:  pip install pythonocc-core
   优化/GLB:  pip install trimesh numpy
        """ 
    ) 
    
    parser.add_argument( 
        'input', 
        help='输入文件或目录路径' 
    ) 
    
    parser.add_argument( 
        'output', 
        nargs='?', 
        default=None, 
        help='输出文件或目录路径（可选）' 
    ) 
    
    parser.add_argument(
        '--export-mode',
        choices=['whole', 'parts', 'both'],
        default='whole',
        help='导出模式: whole=完整模型(默认), parts=只部件, both=完整+部件'
    )
    
    parser.add_argument( 
        '-q', '--quality', 
        choices=['draft', 'low', 'medium', 'high', 'ultra'], 
        default='low', 
        help='质量预设 (默认: low)' 
    ) 
    
    parser.add_argument( 
        '-l', '--linear-deflection', 
        type=float, 
        default=None, 
        help='线性偏差（覆盖质量预设）' 
    ) 
    
    parser.add_argument( 
        '-a', '--angular-deflection', 
        type=float, 
        default=None, 
        help='角度偏差（覆盖质量预设）' 
    ) 
    
    parser.add_argument( 
        '--absolute', 
        action='store_true', 
        help='使用绝对误差而非相对误差' 
    ) 
    
    parser.add_argument( 
        '--no-parallel', 
        action='store_true', 
        help='禁用并行处理（兼容低配电脑）' 
    ) 
    
    parser.add_argument( 
        '--ascii', 
        action='store_true', 
        help='使用ASCII格式输出STL（默认为二进制）' 
    ) 
    
    parser.add_argument( 
        '--optimize', 
        action='store_true', 
        help='优化STL网格（去除重复顶点）' 
    ) 
    
    parser.add_argument( 
        '--glb', 
        action='store_true', 
        help='同时导出GLB格式（支持颜色）' 
    ) 
    
    parser.add_argument( 
        '--zip', 
        action='store_true', 
        help='自动压缩完整模型文件（不影响parts模式）' 
    ) 
    
    args = parser.parse_args() 
    
    # 检查优化功能依赖
    if (args.optimize or args.glb) and not TRIMESH_AVAILABLE: 
        print("⚠️  警告: 优化和GLB功能需要安装 trimesh", file=sys.stderr) 
        print("   安装命令: pip install trimesh numpy", file=sys.stderr) 
        print() 
        response = input("是否继续进行基础转换? (y/n): ") 
        if response.lower() != 'y': 
            sys.exit(EXIT_ERROR_IMPORT) 
        args.optimize = False
        args.glb = False
    
    # 检查部件拆分功能依赖
    if args.export_mode in ['parts', 'both'] and not XCAF_AVAILABLE:
        print("⚠️  警告: 部件拆分功能需要完整的pythonocc-core安装", file=sys.stderr)
        print("   当前缺少XCAF模块", file=sys.stderr)
        print()
        response = input("是否回退到完整模型模式? (y/n): ")
        if response.lower() != 'y':
            sys.exit(EXIT_ERROR_IMPORT)
        args.export_mode = 'whole'
    
    # 创建转换器 默认启用并行
    converter = StepToStlConverter( 
        quality=args.quality, 
        linear_deflection=args.linear_deflection, 
        angular_deflection=args.angular_deflection, 
        relative=not args.absolute, 
        parallel=not args.no_parallel
    ) 
    
    input_path = Path(args.input) 
    
    # 判断是文件还是目录
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
        print(f"❌ 错误: 路径不存在 - {args.input}", file=sys.stderr) 
        sys.exit(EXIT_ERROR_FILE_NOT_FOUND) 

if __name__ == '__main__': 
    main()