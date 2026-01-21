#!/usr/bin/env python
# -*- coding: utf-8 -*- 
""" 
STEP/STP to STL Converter
支持网格优化、GLB导出、自动压缩
兼容 Windows 7 + Python 3.8.10
优化：并行处理、快速启动、大文件支持
""" 

import os
import sys
import time
import zipfile
import argparse
from pathlib import Path
from typing import Optional

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
except ImportError: 
    print("❌ 错误: 未安装 pythonocc-core", file=sys.stderr) 
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
    """STEP/STP 到 STL 转换器""" 
    
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
        
        # 加载STL（使用process=False避免自动处理，节省内存）
        mesh = trimesh.load_mesh(str(stl_path), process=False) 
        print(" ✓") 
        
        # 统计原始信息
        original_vertices = len(mesh.vertices) 
        original_faces = len(mesh.faces) 
        
        print(f"🔧 [优化] 原始网格: {original_vertices:,} 顶点, {original_faces:,} 三角面") 
        
        # 1. 合并重复顶点（这是最主要的优化）
        print("🔧 [优化] 合并重复顶点...", end='', flush=True) 
        mesh.merge_vertices() 
        print(" ✓") 
        
        # 2. 移除未引用的顶点（兼容性更好）
        print("🔧 [优化] 清理未使用顶点...", end='', flush=True) 
        mesh.remove_unreferenced_vertices() 
        print(" ✓") 
        
        # 3. 移除退化面（使用兼容的方法）
        print("🔧 [优化] 清理无效面...", end='', flush=True) 
        # 方法1：使用面积过滤（兼容所有版本）
        if hasattr(mesh, 'remove_degenerate_faces'):
            # 新版本trimesh
            mesh.remove_degenerate_faces()
        else:
            # 旧版本trimesh - 手动过滤零面积三角形
            valid_faces = mesh.area_faces > 1e-10  # 面积阈值
            if not all(valid_faces):
                mesh.update_faces(valid_faces)
        print(" ✓") 
        
        # 4. 移除重复面（使用兼容的方法）
        print("🔧 [优化] 去除重复面...", end='', flush=True) 
        if hasattr(mesh, 'remove_duplicate_faces'):
            # 新版本trimesh
            mesh.remove_duplicate_faces()
        else:
            # 旧版本trimesh - 使用unique方法
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
        
        # 保存优化后的STL（覆盖原文件） 
        print("🔧 [优化] 保存优化后的STL...", end='', flush=True) 
        mesh.export(str(stl_path)) 
        print(" ✓") 
        
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
    
    def export_glb(self, stl_path: Path, glb_path: Optional[Path] = None) -> Optional[Path]: 
        """ 
        将STL转换为GLB格式
        
        Args: 
            stl_path: STL文件路径
            glb_path: GLB输出路径（可选） 
            
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
            print(f"\n📦 [GLB] 转换为GLB格式...") 
            print("📦 [GLB] 加载STL网格...", end='', flush=True) 
            
            # 加载STL
            mesh = trimesh.load_mesh(str(stl_path), process=False) 
            print(" ✓") 
            
            # 导出为GLB
            print("📦 [GLB] 导出GLB格式...", end='', flush=True) 
            mesh.export(str(glb_path), file_type='glb') 
            print(" ✓") 
            
            stl_size = stl_path.stat().st_size / (1024 * 1024) 
            glb_size = glb_path.stat().st_size / (1024 * 1024) 
            ratio = (1 - glb_size / stl_size) * 100
            
            print(f"✅ [GLB] 导出成功: {glb_path.name}") 
            print(f"   📊 大小对比: STL {stl_size:.2f} MB → GLB {glb_size:.2f} MB (↓{ratio:.1f}%)") 
            
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
    
    def convert_file(self, input_path: str, output_path: Optional[str] = None, 
                    ascii_mode=False, optimize=False, export_glb=False, 
                    auto_zip=False) -> bool: 
        """ 
        转换单个文件
        
        Args: 
            input_path: 输入文件路径
            output_path: 输出文件路径（可选） 
            ascii_mode: 是否使用ASCII模式
            optimize: 是否优化STL
            export_glb: 是否导出GLB
            auto_zip: 是否自动压缩
            
        Returns: 
            bool: 转换是否成功
        """ 
        input_file = Path(input_path).resolve()  # 使用绝对路径
        start_time = time.time() 
        
        # 检查输入文件
        if not input_file.exists(): 
            print(f"❌ 错误: 文件不存在 - {input_path}", file=sys.stderr) 
            return False
        
        if input_file.suffix not in self.SUPPORTED_EXTENSIONS: 
            print(f"❌ 错误: 不支持的文件格式 - {input_file.suffix}", file=sys.stderr) 
            return False
        
        # 🔧 修复：改进输出路径处理逻辑
        if output_path is None: 
            output_file = input_file.with_suffix('.stl') 
        else: 
            output_file = Path(output_path).resolve()
            
            # 判断是目录还是文件
            # 如果路径以/或\结尾，或者已存在且是目录
            if str(output_path).endswith(('/', '\\')) or (output_file.exists() and output_file.is_dir()):
                # 是目录，在目录下创建同名stl文件
                output_file = output_file / f"{input_file.stem}.stl"
            elif output_file.suffix.lower() != '.stl':
                # 不是目录，但后缀不是.stl
                # 判断父目录是否存在，如果不存在则当作目录处理
                if not output_file.parent.exists():
                    # 父目录不存在，可能用户想创建目录
                    output_file = output_file / f"{input_file.stem}.stl"
                else:
                    # 父目录存在，添加.stl后缀
                    output_file = output_file.with_suffix('.stl')
        
        # 创建输出目录
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"❌ 错误: 无法创建输出目录 - {output_file.parent}", file=sys.stderr)
            print(f"   详细信息: {str(e)}", file=sys.stderr)
            return False
        
        input_size = input_file.stat().st_size / (1024 * 1024)  # MB
        print(f"\n{'='*70}") 
        print(f"📁 输入文件: {input_file.name} ({input_size:.2f} MB)") 
        print(f"📂 输出文件: {output_file}") 
        print(f"⚙️  质量设置: {self.quality_name}") 
        print(f"🚀 并行处理: {'启用' if self.parallel else '禁用'}") 
        if optimize: 
            print(f"🔧 网格优化: 启用") 
        if export_glb: 
            print(f"📦 GLB导出: 启用") 
        if auto_zip: 
            print(f"🗜️  自动压缩: 启用") 
        print(f"{'='*70}") 
        
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
            
            # 4. 生成网格（🚀 启用并行处理）
            print("🔨 [4/4] 生成STL网格...", end='', flush=True) 
            mesh = BRepMesh_IncrementalMesh( 
                shape, 
                linear_def, 
                False,  # isRelative
                self.angular_deflection, 
                self.parallel  # 🚀 并行处理（关键优化）
            ) 
            mesh.Perform() 
            
            if not mesh.IsDone(): 
                print(f"\n❌ 错误: 网格生成失败", file=sys.stderr) 
                return False
            print(" ✓") 
            
            # 5. 写入STL文件
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
            
            # 6. 优化STL（如果启用） 
            if optimize: 
                print() 
                optimized = self.optimize_stl(output_file) 
                if optimized: 
                    output_file = optimized
            
            # 7. 导出GLB（如果启用） 
            glb_file = None
            if export_glb: 
                glb_file = self.export_glb(output_file) 
            
            # 8. 压缩文件（如果启用） 
            if auto_zip: 
                print() 
                # 压缩STL
                self.compress_file(output_file) 
                
                # 压缩GLB（如果存在） 
                if glb_file: 
                    self.compress_file(glb_file) 
            
            # 统计信息
            elapsed_time = time.time() - start_time
            final_stl_size = output_file.stat().st_size / (1024 * 1024) 
            
            print(f"\n{'='*70}") 
            print(f"✅ 转换成功!") 
            print(f"   ⏱️  总耗时: {elapsed_time:.2f} 秒") 
            print(f"   📍 输出目录: {output_file.parent.absolute()}") 
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
            
        except Exception as e: 
            print(f"\n❌ 错误: 转换失败", file=sys.stderr) 
            print(f"   详细信息: {str(e)}", file=sys.stderr) 
            import traceback
            traceback.print_exc(file=sys.stderr) 
            return False
    
    def convert_directory(self, input_dir: str, output_dir: Optional[str] = None, 
                         ascii_mode=False, optimize=False, export_glb=False, 
                         auto_zip=False) -> dict: 
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
                               optimize, export_glb, auto_zip): 
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
        description='STEP/STP 转 STL 格式转换工具', 
        formatter_class=argparse.RawDescriptionHelpFormatter, 
        epilog=""" 
📖 使用示例: 

  1️⃣  基础转换（low质量，推荐）: 
     step2stl model.step

  2️⃣  指定输出目录: 
     step2stl model.step output_dir/ -q high

  3️⃣ （去重顶点，减小文件）: 
     step2stl model.step --optimize

  4️⃣  导出GLB格式: 
     step2stl model.step --optimize --glb

  5️⃣  完整版（优化+GLB+压缩）: 
     step2stl model.step --optimize --glb --zip

  6️⃣  批量转换: 
     step2stl input_dir/ output_dir/ --optimize --glb

  7️⃣  高质量转换: 
     step2stl model.step -q high --optimize

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
   --glb       同时导出GLB格式（文件更小） 
   --zip       自动压缩输出文件

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
        help='同时导出GLB格式' 
    ) 
    
    parser.add_argument( 
        '--zip', 
        action='store_true', 
        help='自动压缩输出文件' 
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
            args.optimize, args.glb, args.zip
        ) 
        sys.exit(EXIT_SUCCESS if success else EXIT_ERROR_CONVERSION_FAILED) 
        
    elif input_path.is_dir(): 
        results = converter.convert_directory( 
            args.input, args.output, args.ascii, 
            args.optimize, args.glb, args.zip
        ) 
        sys.exit(EXIT_SUCCESS if results['failed'] == 0 else EXIT_ERROR_CONVERSION_FAILED) 
        
    else: 
        print(f"❌ 错误: 路径不存在 - {args.input}", file=sys.stderr) 
        sys.exit(EXIT_ERROR_FILE_NOT_FOUND) 

if __name__ == '__main__': 
    main()