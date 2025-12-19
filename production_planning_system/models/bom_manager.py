import pandas as pd
import numpy as np
import networkx as nx
import logging
import os
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定义物料类型常量
MATERIAL_TYPE_FINISHED = "成品"
MATERIAL_TYPE_SEMIFINISHED = "半成品"
MATERIAL_TYPE_RAW = "基础原料"

class BOMManager:
    """
    物料清单(BOM)管理模块，负责BOM数据的导入、验证和处理
    支持三级物料结构：成品 -> 半成品 -> 基础原料
    """
    
    def __init__(self):
        """初始化BOM管理器"""
        self.bom_data = None
        self.bom_graph = None
        self.material_info = {}  # 存储物料的附加信息，包括物料类型
        self.suppliers = {}  # 存储供应商信息
        self.material_types = {}  # 存储每个物料的类型
    
    def load_bom_data(self, file_path):
        """
        从文件中加载BOM数据
        
        参数:
            file_path: BOM数据文件路径
            
        返回:
            DataFrame或None: 加载的BOM数据
        """
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_extension.lower() in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)
            else:
                logger.error(f"不支持的文件类型: {file_extension}")
                return None
            
            logger.info(f"成功加载BOM数据，共 {len(df)} 行")
            self.bom_data = df
            return df
        
        except Exception as e:
            logger.error(f"BOM数据加载失败: {str(e)}")
            return None
    
    def validate_bom_data(self):
        """
        验证BOM数据格式和内容是否有效，同时推断物料类型
        
        返回:
            (bool, str): (是否有效, 错误信息)
        """
        if self.bom_data is None:
            return False, "未加载BOM数据"
        
        # 检查必要字段
        required_fields = ['成品编号', '子件编号', '单位用量']
        missing_fields = [field for field in required_fields if field not in self.bom_data.columns]
        
        if missing_fields:
            return False, f"BOM数据缺少必要字段: {', '.join(missing_fields)}"
        
        # 检查数据类型
        try:
            # 检查用量是否为数值
            if not pd.to_numeric(self.bom_data['单位用量'], errors='coerce').notna().all():
                return False, "单位用量包含非数值数据"
        
        except Exception as e:
            return False, f"数据类型验证失败: {str(e)}"
        
        # 检查BOM结构中是否有循环引用
        try:
            self.build_bom_graph()
            if nx.is_directed_acyclic_graph(self.bom_graph):
                # 推断并验证物料类型
                self.infer_material_types()
                
                # 验证BOM层次结构
                is_valid, error_msg = self.validate_hierarchy()
                if is_valid:
                    return True, "BOM数据验证通过"
                else:
                    return False, error_msg
            else:
                cycles = list(nx.simple_cycles(self.bom_graph))
                return False, f"BOM结构中存在循环引用: {cycles}"
        
        except Exception as e:
            return False, f"BOM结构验证失败: {str(e)}"
    
    def build_bom_graph(self):
        """
        构建BOM的有向图表示
        
        返回:
            DiGraph: BOM的有向图表示
        """
        if self.bom_data is None:
            logger.error("未加载BOM数据，无法构建图")
            return None
        
        try:
            G = nx.DiGraph()
            
            # 添加节点和边
            for _, row in self.bom_data.iterrows():
                parent = row['成品编号']
                child = row['子件编号']
                quantity = row['单位用量']
                
                # 存储物料信息
                if '成品描述' in row:
                    if parent not in self.material_info:
                        self.material_info[parent] = {}
                    self.material_info[parent]['description'] = row['成品描述']
                
                if '子件描述' in row:
                    if child not in self.material_info:
                        self.material_info[child] = {}
                    self.material_info[child]['description'] = row['子件描述']
                
                # 添加物料类型信息（如果在数据中有提供）
                if '成品类型' in row:
                    self.material_types[parent] = row['成品类型']
                
                if '子件类型' in row:
                    self.material_types[child] = row['子件类型']
                
                # 添加节点和边
                G.add_node(parent)
                G.add_node(child)
                G.add_edge(parent, child, quantity=quantity)
            
            self.bom_graph = G
            logger.info(f"BOM图构建成功，包含 {G.number_of_nodes()} 个节点和 {G.number_of_edges()} 条边")
            return G
            
        except Exception as e:
            logger.error(f"构建BOM图失败: {str(e)}")
            return None
    
    def infer_material_types(self):
        """
        根据BOM结构推断物料类型（成品、半成品、基础原料）
        
        返回:
            dict: 物料类型字典，键为物料编号，值为物料类型
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法推断物料类型")
            return {}
        
        try:
            # 遍历所有节点进行初步分类
            for node in self.bom_graph.nodes():
                # 如果已经指定了类型，则跳过
                if node in self.material_types:
                    continue
                
                # 出度为0表示未被用作其他物料的组件，可能是成品
                # 入度为0表示不包含其他组件，可能是基础原料
                out_degree = self.bom_graph.out_degree(node)
                in_degree = self.bom_graph.in_degree(node)
                
                if out_degree == 0 and in_degree > 0:
                    # 没有子件且被其他物料使用，可能是基础原料
                    self.material_types[node] = MATERIAL_TYPE_RAW
                elif out_degree > 0 and in_degree == 0:
                    # 有子件且不被其他物料使用，可能是成品
                    self.material_types[node] = MATERIAL_TYPE_FINISHED
                elif out_degree > 0 and in_degree > 0:
                    # 既有子件又被其他物料使用，可能是半成品
                    self.material_types[node] = MATERIAL_TYPE_SEMIFINISHED
                else:
                    # 孤立节点，无法确定类型
                    self.material_types[node] = "未知"
                    logger.warning(f"物料 {node} 在BOM中是孤立节点，无法确定类型")
            
            # 更新物料信息
            for material, material_type in self.material_types.items():
                if material not in self.material_info:
                    self.material_info[material] = {}
                self.material_info[material]['type'] = material_type
            
            logger.info(f"物料类型推断完成，成品: {list(self.material_types.values()).count(MATERIAL_TYPE_FINISHED)}, "
                      f"半成品: {list(self.material_types.values()).count(MATERIAL_TYPE_SEMIFINISHED)}, "
                      f"基础原料: {list(self.material_types.values()).count(MATERIAL_TYPE_RAW)}")
            
            return self.material_types
            
        except Exception as e:
            logger.error(f"推断物料类型失败: {str(e)}")
            return {}
    
    def validate_hierarchy(self):
        """
        验证BOM的层次结构是否符合要求:
        1. 成品可以由基础原料直接构成
        2. 成品也可以由基础原料和半成品共同构成
        3. 半成品应由基础原料构成
        
        返回:
            (bool, str): (是否有效, 错误信息)
        """
        if not self.material_types:
            logger.error("物料类型未定义，无法验证层次结构")
            return False, "物料类型未定义"
        
        try:
            # 验证成品的组成
            for node, node_type in self.material_types.items():
                if node_type == MATERIAL_TYPE_FINISHED:
                    # 获取成品的子件
                    children = self.get_material_children(node)
                    child_types = [self.material_types.get(child[0], "未知") for child in children]
                    
                    # 检查成品的组成是否符合要求
                    if not child_types:
                        logger.warning(f"成品 {node} 没有子件")
                    elif not (all(t == MATERIAL_TYPE_RAW for t in child_types) or 
                             (MATERIAL_TYPE_RAW in child_types and MATERIAL_TYPE_SEMIFINISHED in child_types)):
                        return False, f"成品 {node} 的组成不符合要求，应由基础原料或基础原料和半成品构成"
                
                elif node_type == MATERIAL_TYPE_SEMIFINISHED:
                    # 获取半成品的子件
                    children = self.get_material_children(node)
                    child_types = [self.material_types.get(child[0], "未知") for child in children]
                    
                    # 检查半成品的组成是否符合要求
                    if not child_types:
                        logger.warning(f"半成品 {node} 没有子件")
                    elif not all(t == MATERIAL_TYPE_RAW for t in child_types):
                        return False, f"半成品 {node} 的组成不符合要求，应由基础原料构成"
            
            return True, "层次结构验证通过"
            
        except Exception as e:
            logger.error(f"验证层次结构失败: {str(e)}")
            return False, f"验证层次结构失败: {str(e)}"
    
    def get_material_children(self, material_id):
        """
        获取指定物料的直接子件
        
        参数:
            material_id: 物料编号
            
        返回:
            list: 直接子件列表，每个子件为 (子件编号, 单位用量)
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法获取子件")
            return []
        
        try:
            if material_id not in self.bom_graph:
                logger.warning(f"物料 {material_id} 不存在于BOM中")
                return []
            
            # 获取所有出边及其属性
            children = []
            for _, child, data in self.bom_graph.out_edges(material_id, data=True):
                children.append((child, data['quantity']))
            
            return children
            
        except Exception as e:
            logger.error(f"获取子件失败: {str(e)}")
            return []
    
    def get_material_parents(self, material_id):
        """
        获取使用指定物料的父项
        
        参数:
            material_id: 物料编号
            
        返回:
            list: 父项列表，每个父项为 (父项编号, 单位用量)
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法获取父项")
            return []
        
        try:
            if material_id not in self.bom_graph:
                logger.warning(f"物料 {material_id} 不存在于BOM中")
                return []
            
            # 获取所有入边及其属性
            parents = []
            for parent, _, data in self.bom_graph.in_edges(material_id, data=True):
                parents.append((parent, data['quantity']))
            
            return parents
            
        except Exception as e:
            logger.error(f"获取父项失败: {str(e)}")
            return []
    
    def get_material_type(self, material_id):
        """
        获取指定物料的类型
        
        参数:
            material_id: 物料编号
            
        返回:
            str: 物料类型（成品、半成品、基础原料或未知）
        """
        if material_id in self.material_types:
            return self.material_types[material_id]
        else:
            logger.warning(f"物料 {material_id} 的类型未定义")
            return "未知"
    
    def explode_bom(self, material_id, levels=None, material_type=None):
        """
        展开BOM，获取所有组件及其用量
        
        参数:
            material_id: 物料编号
            levels: 展开的层级数，None表示全部展开
            material_type: 筛选特定类型的物料，None表示不筛选
            
        返回:
            DataFrame: 展开的BOM，包含组件编号、描述、物料类型、总用量和层级
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法展开BOM")
            return None
        
        if material_id not in self.bom_graph:
            logger.error(f"物料 {material_id} 不存在于BOM中")
            return None
        
        try:
            # 使用BFS展开BOM
            components = []
            visited = set()
            queue = [(material_id, 1, 0, 1)]  # (物料编号, 用量, 层级, 路径乘数)
            
            while queue:
                current, qty, level, path_multiplier = queue.pop(0)
                
                # 如果达到指定层级，则停止展开
                if levels is not None and level > levels:
                    continue
                
                # 获取子件
                children = self.get_material_children(current)
                
                # 如果是叶子节点(无子件)或已达最大层级，则添加到组件列表
                if not children or (levels is not None and level == levels):
                    if current != material_id:  # 不包括顶级物料自身
                        # 获取物料类型
                        mat_type = self.get_material_type(current)
                        
                        # 如果指定了物料类型筛选，则跳过不匹配的物料
                        if material_type is not None and mat_type != material_type:
                            continue
                        
                        # 计算对应于顶级物料的总用量
                        total_qty = qty * path_multiplier
                        
                        # 获取物料描述
                        description = "未知"
                        if current in self.material_info and 'description' in self.material_info[current]:
                            description = self.material_info[current]['description']
                        
                        components.append({
                            '组件编号': current,
                            '描述': description,
                            '物料类型': mat_type,
                            '总用量': total_qty,
                            '层级': level
                        })
                
                # 将未访问过的子件加入队列
                for child, child_qty in children:
                    if (current, child) not in visited:
                        visited.add((current, child))
                        queue.append((child, child_qty, level + 1, path_multiplier * qty))
            
            # 转换为DataFrame
            if components:
                df = pd.DataFrame(components)
                
                # 按组件编号分组合并相同组件的用量
                df = df.groupby('组件编号').agg({
                    '描述': 'first',      # 取第一个描述
                    '物料类型': 'first',   # 取第一个物料类型
                    '总用量': 'sum',       # 合并用量
                    '层级': 'min'          # 取最小层级
                }).reset_index()
                
                logger.info(f"成功展开物料 {material_id} 的BOM，包含 {len(df)} 个组件")
                return df
            else:
                logger.warning(f"物料 {material_id} 没有符合条件的子组件")
                return pd.DataFrame(columns=['组件编号', '描述', '物料类型', '总用量', '层级'])
                
        except Exception as e:
            logger.error(f"展开BOM失败: {str(e)}")
            return None
    
    def calculate_raw_material_requirements(self, production_plan):
        """
        根据生产计划计算基础原料需求
        
        参数:
            production_plan: DataFrame，包含物料编号和计划产量
            
        返回:
            DataFrame: 基础原料需求，包含物料编号、描述和需求量
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法计算需求")
            return None
        
        if not isinstance(production_plan, pd.DataFrame):
            logger.error("生产计划格式错误，需要DataFrame")
            return None
        
        # 检查必要字段
        required_fields = ['物料编号', '计划产量']
        missing_fields = [field for field in required_fields if field not in production_plan.columns]
        
        if missing_fields:
            logger.error(f"生产计划缺少必要字段: {missing_fields}")
            return None
        
        try:
            # 存储基础原料的总需求
            raw_requirements = defaultdict(float)
            
            # 处理每个产品
            for _, row in production_plan.iterrows():
                material_id = row['物料编号']
                quantity = row['计划产量']
                
                # 确认是否为成品
                material_type = self.get_material_type(material_id)
                if material_type != MATERIAL_TYPE_FINISHED:
                    logger.warning(f"物料 {material_id} 不是成品，跳过")
                    continue
                
                # 展开该产品的BOM，只获取基础原料
                exploded_bom = self.explode_bom(material_id, material_type=MATERIAL_TYPE_RAW)
                
                if exploded_bom is not None and not exploded_bom.empty:
                    # 累加该产品对应的基础原料需求
                    for _, comp_row in exploded_bom.iterrows():
                        comp_id = comp_row['组件编号']
                        comp_qty = comp_row['总用量']
                        
                        # 累加到总需求中
                        raw_requirements[comp_id] += comp_qty * quantity
            
            # 转换为DataFrame
            if raw_requirements:
                requirements_data = []
                
                for mat_id, qty in raw_requirements.items():
                    # 获取物料描述
                    description = "未知"
                    if mat_id in self.material_info and 'description' in self.material_info[mat_id]:
                        description = self.material_info[mat_id]['description']
                    
                    requirements_data.append({
                        '物料编号': mat_id,
                        '描述': description,
                        '物料类型': MATERIAL_TYPE_RAW,
                        '需求量': qty
                    })
                
                df = pd.DataFrame(requirements_data)
                logger.info(f"成功计算基础原料需求，共 {len(df)} 种物料")
                return df
            else:
                logger.warning("未计算出任何基础原料需求")
                return pd.DataFrame(columns=['物料编号', '描述', '物料类型', '需求量'])
                
        except Exception as e:
            logger.error(f"计算基础原料需求失败: {str(e)}")
            return None
    
    def calculate_semifinished_requirements(self, production_plan):
        """
        根据生产计划计算半成品需求
        
        参数:
            production_plan: DataFrame，包含物料编号和计划产量
            
        返回:
            DataFrame: 半成品需求，包含物料编号、描述和需求量
        """
        if self.bom_graph is None:
            logger.error("BOM图未构建，无法计算需求")
            return None
        
        if not isinstance(production_plan, pd.DataFrame):
            logger.error("生产计划格式错误，需要DataFrame")
            return None
        
        try:
            # 存储半成品的总需求
            semifinished_requirements = defaultdict(float)
            
            # 处理每个产品
            for _, row in production_plan.iterrows():
                material_id = row['物料编号']
                quantity = row['计划产量']
                
                # 确认是否为成品
                material_type = self.get_material_type(material_id)
                if material_type != MATERIAL_TYPE_FINISHED:
                    logger.warning(f"物料 {material_id} 不是成品，跳过")
                    continue
                
                # 展开该产品的BOM，只获取半成品
                exploded_bom = self.explode_bom(material_id, material_type=MATERIAL_TYPE_SEMIFINISHED)
                
                if exploded_bom is not None and not exploded_bom.empty:
                    # 累加该产品对应的半成品需求
                    for _, comp_row in exploded_bom.iterrows():
                        comp_id = comp_row['组件编号']
                        comp_qty = comp_row['总用量']
                        
                        # 累加到总需求中
                        semifinished_requirements[comp_id] += comp_qty * quantity
            
            # 转换为DataFrame
            if semifinished_requirements:
                requirements_data = []
                
                for mat_id, qty in semifinished_requirements.items():
                    # 获取物料描述
                    description = "未知"
                    if mat_id in self.material_info and 'description' in self.material_info[mat_id]:
                        description = self.material_info[mat_id]['description']
                    
                    requirements_data.append({
                        '物料编号': mat_id,
                        '描述': description,
                        '物料类型': MATERIAL_TYPE_SEMIFINISHED,
                        '需求量': qty
                    })
                
                df = pd.DataFrame(requirements_data)
                logger.info(f"成功计算半成品需求，共 {len(df)} 种物料")
                return df
            else:
                logger.warning("未计算出任何半成品需求")
                return pd.DataFrame(columns=['物料编号', '描述', '物料类型', '需求量'])
                
        except Exception as e:
            logger.error(f"计算半成品需求失败: {str(e)}")
            return None
    
    def load_supplier_data(self, file_path):
        """
        加载供应商数据
        
        参数:
            file_path: 供应商数据文件路径
            
        返回:
            DataFrame或None: 加载的供应商数据
        """
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_extension.lower() in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)
            else:
                logger.error(f"不支持的文件类型: {file_extension}")
                return None
            
            # 将供应商数据存储为字典，便于查询
            self.suppliers = {}
            
            # 假设供应商数据格式为：物料编号、供应商编号、单价、最小订购量等
            for _, row in df.iterrows():
                material_id = row['物料编号']
                supplier_id = row['供应商编号']
                
                if material_id not in self.suppliers:
                    self.suppliers[material_id] = []
                
                # 存储该物料的供应商信息
                supplier_info = {
                    'supplier_id': supplier_id,
                    'price': row.get('单价', 0),
                    'min_order_qty': row.get('最小订购量', 1),
                    'lead_time': row.get('采购提前期', 0)
                }
                
                self.suppliers[material_id].append(supplier_info)
            
            logger.info(f"成功加载供应商数据，共 {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"供应商数据加载失败: {str(e)}")
            return None
    
    def get_supplier_info(self, material_id):
        """
        获取指定物料的供应商信息
        
        参数:
            material_id: 物料编号
            
        返回:
            list: 供应商信息列表
        """
        return self.suppliers.get(material_id, [])
    
    def export_bom_data(self, file_path):
        """
        导出BOM数据
        
        参数:
            file_path: 导出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.bom_data is None:
            logger.error("没有BOM数据可供导出")
            return False
        
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                self.bom_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_extension.lower() in ['.xls', '.xlsx']:
                self.bom_data.to_excel(file_path, index=False)
            else:
                logger.error(f"不支持的导出文件类型: {file_extension}")
                return False
            
            logger.info(f"BOM数据成功导出至 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"BOM数据导出失败: {str(e)}")
            return False