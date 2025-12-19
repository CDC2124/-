import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict
# 移除 from ortools.linear_solver import pywraplp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MRPCalculator:
    """
    原材料需求计划(MRP)计算模块
    基于生产计划和BOM计算原材料需求，并使用OR-Tools优化采购计划
    """
    
    def __init__(self, bom_manager=None):
        """
        初始化MRP计算器
        
        参数:
            bom_manager: BOM管理器实例，用于获取BOM结构
        """
        self.bom_manager = bom_manager
        self.production_plan = None
        self.raw_material_inventory = None
        self.semifinished_inventory = None
        self.supplier_data = None
        self.raw_material_requirements = None
        self.semifinished_requirements = None
        self.purchase_plan = None
        self.mrp_parameters = {}
    
    def set_bom_manager(self, bom_manager):
        """
        设置BOM管理器
        
        参数:
            bom_manager: BOM管理器实例
            
        返回:
            bool: 是否成功设置
        """
        if bom_manager is None:
            logger.error("BOM管理器不能为空")
            return False
        
        self.bom_manager = bom_manager
        logger.info("成功设置BOM管理器")
        return True
    
    def load_production_plan(self, production_plan):
        """
        加载生产计划
        
        参数:
            production_plan: 生产计划DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(production_plan, pd.DataFrame):
                logger.error("生产计划格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['年份', '月份', '物料编号', '计划产量']
            missing_fields = [field for field in required_fields if field not in production_plan.columns]
            
            if missing_fields:
                logger.error(f"生产计划缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.production_plan = production_plan.copy()
            logger.info(f"成功加载生产计划，共 {len(production_plan)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载生产计划失败: {str(e)}")
            return False
    
    def load_raw_material_inventory(self, inventory_data):
        """
        加载原材料库存数据
        
        参数:
            inventory_data: 库存DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(inventory_data, pd.DataFrame):
                logger.error("原材料库存数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['物料编号', '库存数量']
            missing_fields = [field for field in required_fields if field not in inventory_data.columns]
            
            if missing_fields:
                logger.error(f"原材料库存数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.raw_material_inventory = inventory_data.copy()
            logger.info(f"成功加载原材料库存数据，共 {len(inventory_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载原材料库存数据失败: {str(e)}")
            return False
    
    def load_semifinished_inventory(self, inventory_data):
        """
        加载半成品库存数据
        
        参数:
            inventory_data: 库存DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(inventory_data, pd.DataFrame):
                logger.error("半成品库存数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['物料编号', '库存数量']
            missing_fields = [field for field in required_fields if field not in inventory_data.columns]
            
            if missing_fields:
                logger.error(f"半成品库存数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.semifinished_inventory = inventory_data.copy()
            logger.info(f"成功加载半成品库存数据，共 {len(inventory_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载半成品库存数据失败: {str(e)}")
            return False
    
    def load_supplier_data(self, supplier_data):
        """
        加载供应商数据
        
        参数:
            supplier_data: 供应商DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(supplier_data, pd.DataFrame):
                logger.error("供应商数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['物料编号', '供应商编号', '单价', '最小订购量', '采购提前期']
            missing_fields = [field for field in required_fields if field not in supplier_data.columns]
            
            if missing_fields:
                logger.error(f"供应商数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.supplier_data = supplier_data.copy()
            logger.info(f"成功加载供应商数据，共 {len(supplier_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载供应商数据失败: {str(e)}")
            return False
    
    def set_mrp_parameters(self, parameters):
        """
        设置MRP参数
        
        参数:
            parameters: 参数字典
            
        返回:
            bool: 是否成功设置
        """
        try:
            # 验证参数
            if not isinstance(parameters, dict):
                logger.error("MRP参数必须为字典类型")
                return False
            
            # 设置默认值
            default_parameters = {
                'safety_stock_days': 15,    # 安全库存天数
                'max_inventory_days': 60,   # 最大库存天数
                'order_multiple': 1,        # 订单倍数
                'planning_horizon': 6       # 计划期数（月）
            }
            
            # 更新参数
            merged_parameters = {**default_parameters, **parameters}
            self.mrp_parameters = merged_parameters
            
            logger.info(f"成功设置MRP参数: {merged_parameters}")
            return True
            
        except Exception as e:
            logger.error(f"设置MRP参数失败: {str(e)}")
            return False
    
    def calculate_requirements(self):
        """
        计算物料需求
        
        返回:
            tuple: (原材料需求DataFrame, 半成品需求DataFrame) 如果失败则返回(None, None)
        """
        if self.bom_manager is None:
            logger.error("未设置BOM管理器，无法计算需求")
            return None, None
        
        if self.production_plan is None:
            logger.error("未加载生产计划，无法计算需求")
            return None, None
        
        try:
            # 计算原材料需求
            raw_requirements = self.bom_manager.calculate_raw_material_requirements(self.production_plan)
            
            if raw_requirements is None:
                logger.error("计算原材料需求失败")
                return None, None
            
            # 计算半成品需求
            semifinished_requirements = self.bom_manager.calculate_semifinished_requirements(self.production_plan)
            
            if semifinished_requirements is None:
                logger.error("计算半成品需求失败")
                return None, None
            
            # 保存计算结果
            self.raw_material_requirements = raw_requirements
            self.semifinished_requirements = semifinished_requirements
            
            logger.info(f"成功计算物料需求，原材料: {len(raw_requirements)}种，半成品: {len(semifinished_requirements)}种")
            return raw_requirements, semifinished_requirements
            
        except Exception as e:
            logger.error(f"计算物料需求失败: {str(e)}")
            return None, None
    
    def allocate_requirements_to_periods(self):
        """
        将物料需求分配到各个时间段
        
        返回:
            tuple: (原材料按期需求DataFrame, 半成品按期需求DataFrame) 如果失败则返回(None, None)
        """
        if self.raw_material_requirements is None or self.semifinished_requirements is None:
            logger.error("未计算物料需求，无法分配")
            return None, None
        
        if self.production_plan is None:
            logger.error("未加载生产计划，无法分配需求")
            return None, None
        
        try:
            # 获取计划期数
            time_periods = self.production_plan[['年份', '月份']].drop_duplicates()
            time_periods = time_periods.sort_values(['年份', '月份'])
            
            # 限制期数
            planning_horizon = self.mrp_parameters.get('planning_horizon', 6)
            if len(time_periods) > planning_horizon:
                logger.warning(f"计划期数超过设定值，已截断为 {planning_horizon} 期")
                time_periods = time_periods.head(planning_horizon)
            
            # 分配原材料需求
            raw_periods_data = []
            
            for _, row in self.raw_material_requirements.iterrows():
                material_id = row['物料编号']
                total_demand = row['需求量']
                
                # 获取生产计划中该物料的每期需求比例
                production_by_period = {}
                total_production = 0
                
                for _, prod_row in self.production_plan.iterrows():
                    year, month = prod_row['年份'], prod_row['月份']
                    if (year, month) in [(y, m) for _, y, m in time_periods.itertuples()]:
                        production = prod_row['计划产量']
                        production_by_period[(year, month)] = production_by_period.get((year, month), 0) + production
                        total_production += production
                
                # 按比例分配需求
                for _, tp_row in time_periods.iterrows():
                    year, month = tp_row['年份'], tp_row['月份']
                    
                    if total_production > 0:
                        period_ratio = production_by_period.get((year, month), 0) / total_production
                        period_demand = total_demand * period_ratio
                    else:
                        # 如果总产量为0，则平均分配
                        period_demand = total_demand / len(time_periods)
                    
                    raw_periods_data.append({
                        '年份': year,
                        '月份': month,
                        '物料编号': material_id,
                        '物料类型': row['物料类型'],
                        '描述': row['描述'],
                        '期间需求量': period_demand,
                        '总需求量': total_demand
                    })
            
            # 分配半成品需求
            semifinished_periods_data = []
            
            for _, row in self.semifinished_requirements.iterrows():
                material_id = row['物料编号']
                total_demand = row['需求量']
                
                # 获取生产计划中该物料的每期需求比例
                production_by_period = {}
                total_production = 0
                
                for _, prod_row in self.production_plan.iterrows():
                    year, month = prod_row['年份'], prod_row['月份']
                    if (year, month) in [(y, m) for _, y, m in time_periods.itertuples()]:
                        production = prod_row['计划产量']
                        production_by_period[(year, month)] = production_by_period.get((year, month), 0) + production
                        total_production += production
                
                # 按比例分配需求
                for _, tp_row in time_periods.iterrows():
                    year, month = tp_row['年份'], tp_row['月份']
                    
                    if total_production > 0:
                        period_ratio = production_by_period.get((year, month), 0) / total_production
                        period_demand = total_demand * period_ratio
                    else:
                        # 如果总产量为0，则平均分配
                        period_demand = total_demand / len(time_periods)
                    
                    semifinished_periods_data.append({
                        '年份': year,
                        '月份': month,
                        '物料编号': material_id,
                        '物料类型': row['物料类型'],
                        '描述': row['描述'],
                        '期间需求量': period_demand,
                        '总需求量': total_demand
                    })
            
            # 创建DataFrame
            raw_periods_df = pd.DataFrame(raw_periods_data)
            semifinished_periods_df = pd.DataFrame(semifinished_periods_data)
            
            logger.info(f"成功分配需求到各时间段，原材料: {len(raw_periods_df)}条，半成品: {len(semifinished_periods_df)}条")
            return raw_periods_df, semifinished_periods_df
            
        except Exception as e:
            logger.error(f"分配需求到各时间段失败: {str(e)}")
            return None, None
    
    def get_material_inventory(self, material_id, material_type):
        """
        获取指定物料的库存量
        
        参数:
            material_id: 物料编号
            material_type: 物料类型
            
        返回:
            float: 库存数量，如果没有库存记录则返回0
        """
        try:
            if material_type == "基础原料" and self.raw_material_inventory is not None:
                inventory = self.raw_material_inventory[self.raw_material_inventory['物料编号'] == material_id]
                if not inventory.empty:
                    return inventory.iloc[0]['库存数量']
            
            elif material_type == "半成品" and self.semifinished_inventory is not None:
                inventory = self.semifinished_inventory[self.semifinished_inventory['物料编号'] == material_id]
                if not inventory.empty:
                    return inventory.iloc[0]['库存数量']
            
            return 0
            
        except Exception as e:
            logger.error(f"获取物料库存失败: {str(e)}")
            return 0
    
    def get_supplier_info(self, material_id):
        """
        获取指定物料的供应商信息
        
        参数:
            material_id: 物料编号
            
        返回:
            DataFrame: 供应商信息，如没有则返回空DataFrame
        """
        try:
            if self.supplier_data is None:
                return pd.DataFrame()
            
            suppliers = self.supplier_data[self.supplier_data['物料编号'] == material_id]
            return suppliers
            
        except Exception as e:
            logger.error(f"获取供应商信息失败: {str(e)}")
            return pd.DataFrame()
    
    def optimize_purchase_plan(self):
        """
        生成采购计划（简化版，不依赖OR-Tools）
        
        返回:
            DataFrame: 优化后的采购计划，如果失败则返回None
        """
        if self.raw_material_requirements is None:
            logger.error("未计算原材料需求，无法优化采购计划")
            return None
        
        if self.supplier_data is None:
            logger.warning("未加载供应商数据，将使用默认供应商配置")
        
        try:
            # 分配需求到各时间段
            raw_periods_df, _ = self.allocate_requirements_to_periods()
            
            if raw_periods_df is None:
                logger.error("分配需求到各时间段失败")
                return None
            
            # 准备采购计划数据
            purchase_plan_data = []
            
            # 获取计划期数
            time_periods = sorted(raw_periods_df[['年份', '月份']].drop_duplicates().itertuples(index=False, name=None),
                               key=lambda x: x[0] * 12 + x[1])
            
            # 获取MRP参数
            safety_stock_days = self.mrp_parameters.get('safety_stock_days', 15)
            order_multiple = self.mrp_parameters.get('order_multiple', 1)
            
            # 对每种原材料生成采购计划
            for material_id in raw_periods_df['物料编号'].unique():
                material_periods = raw_periods_df[raw_periods_df['物料编号'] == material_id].sort_values(['年份', '月份'])
                
                if material_periods.empty:
                    continue
                
                # 获取物料描述
                material_desc = material_periods.iloc[0]['描述']
                
                # 获取物料初始库存
                inventory = self.get_material_inventory(material_id, "基础原料")
                
                # 获取供应商信息
                suppliers = self.get_supplier_info(material_id)
                
                if suppliers.empty:
                    # 如果没有供应商信息，创建默认供应商
                    supplier_id = "默认供应商"
                    lead_time = 15  # 默认采购提前期为15天
                    min_order_qty = 100  # 默认最小订购量为100
                    price = 1.0  # 默认单价为1.0
                else:
                    # 选择首选供应商（这里可以添加更复杂的供应商选择逻辑）
                    supplier = suppliers.iloc[0]
                    supplier_id = supplier['供应商编号']
                    lead_time = supplier['采购提前期']
                    min_order_qty = supplier['最小订购量']
                    price = supplier['单价']
                
                # 处理每个时间段
                for i, (year, month) in enumerate(time_periods):
                    # 获取当期的需求
                    current_data = material_periods[
                        (material_periods['年份'] == year) &
                        (material_periods['月份'] == month)
                    ]
                    
                    if current_data.empty:
                        demand = 0
                    else:
                        demand = current_data.iloc[0]['期间需求量']
                    
                    # 计算安全库存
                    safety_stock = demand * safety_stock_days / 30
                    
                    # 计算净需求量: 需求 + 安全库存 - 期初库存
                    net_demand = max(0, demand + safety_stock - inventory)
                    
                    # 确定采购量
                    if net_demand > 0:
                        # 应用最小订购量
                        purchase = max(net_demand, min_order_qty)
                        
                        # 应用订单倍数（向上取整到最小订单量的整数倍）
                        if order_multiple > 1:
                            purchase = np.ceil(purchase / (min_order_qty * order_multiple)) * (min_order_qty * order_multiple)
                        elif order_multiple == 1 and min_order_qty > 1:
                            purchase = np.ceil(purchase / min_order_qty) * min_order_qty
                    else:
                        purchase = 0
                    
                    # 更新库存: 期初库存 + 采购 - 需求
                    previous_inventory = inventory
                    inventory = previous_inventory + purchase - demand
                    
                    # 计算预计到货日期和订单下达日期
                    delivery_date = datetime(year, month, 1)
                    order_date = delivery_date - timedelta(days=lead_time)
                    
                    # 只有在有采购时才添加到计划
                    if purchase > 0:
                        # 计算采购成本
                        purchase_cost = purchase * price
                        
                        plan_data = {
                            '年份': year,
                            '月份': month,
                            '物料编号': material_id,
                            '描述': material_desc,
                            '物料类型': "基础原料",
                            '毛需求量': demand,
                            '期初库存': round(previous_inventory, 2),
                            '净需求量': round(net_demand, 2),
                            '计划采购量': round(purchase, 2),
                            '期末库存': round(inventory, 2),
                            '供应商': supplier_id,
                            '采购提前期': lead_time,
                            '订单下达日期': order_date.strftime('%Y-%m-%d'),
                            '预计到货日期': delivery_date.strftime('%Y-%m-%d'),
                            '单价': price,
                            '预计成本': round(purchase_cost, 2)
                        }
                        
                        purchase_plan_data.append(plan_data)
            
            # 创建DataFrame
            if purchase_plan_data:
                purchase_plan_df = pd.DataFrame(purchase_plan_data)
                
                # 排序
                purchase_plan_df = purchase_plan_df.sort_values(['物料编号', '年份', '月份'])
                
                # 保存结果
                self.purchase_plan = purchase_plan_df
                
                logger.info(f"成功生成简化版采购计划，共 {len(purchase_plan_df)} 条记录")
                return purchase_plan_df
            else:
                logger.warning("未生成任何采购计划")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"生成采购计划失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def generate_semifinished_production_plan(self):
        """
        根据半成品需求生成半成品生产计划
        
        返回:
            DataFrame: 半成品生产计划，如果失败则返回None
        """
        if self.semifinished_requirements is None:
            logger.error("未计算半成品需求，无法生成生产计划")
            return None
        
        try:
            # 分配需求到各时间段
            _, semifinished_periods_df = self.allocate_requirements_to_periods()
            
            if semifinished_periods_df is None:
                logger.error("分配需求到各时间段失败")
                return None
            
            # 准备生产计划数据
            production_plan_data = []
            
            # 获取计划期数
            time_periods = sorted(semifinished_periods_df[['年份', '月份']].drop_duplicates().itertuples(index=False, name=None),
                               key=lambda x: x[0] * 12 + x[1])
            
            # 订单倍数
            order_multiple = self.mrp_parameters.get('order_multiple', 1)
            
            # 对每种半成品生成生产计划
            for material_id in semifinished_periods_df['物料编号'].unique():
                material_periods = semifinished_periods_df[semifinished_periods_df['物料编号'] == material_id].sort_values(['年份', '月份'])
                
                if material_periods.empty:
                    continue
                
                # 获取物料描述
                material_desc = material_periods.iloc[0]['描述']
                
                # 获取物料库存
                inventory = self.get_material_inventory(material_id, "半成品")
                
                # 为每个时期创建生产计划
                for _, row in material_periods.iterrows():
                    year = row['年份']
                    month = row['月份']
                    demand = row['期间需求量']
                    
                    # 计算净需求
                    net_demand = max(0, demand - inventory)
                    
                    # 应用订单倍数（向上取整到最小批量的整数倍）
                    if net_demand > 0:
                        production = np.ceil(net_demand / order_multiple) * order_multiple
                    else:
                        production = 0
                    
                    # 更新库存
                    ending_inventory = inventory + production - demand
                    
                    production_plan_data.append({
                        '年份': year,
                        '月份': month,
                        '物料编号': material_id,
                        '描述': material_desc,
                        '物料类型': "半成品",
                        '需求量': demand,
                        '期初库存': round(inventory, 2),
                        '计划生产量': round(production, 2),
                        '期末库存': round(ending_inventory, 2)
                    })
                    
                    # 更新下一期的期初库存
                    inventory = ending_inventory
            
            # 创建DataFrame
            if production_plan_data:
                semifinished_plan_df = pd.DataFrame(production_plan_data)
                
                # 排序
                semifinished_plan_df = semifinished_plan_df.sort_values(['物料编号', '年份', '月份'])
                
                logger.info(f"成功生成半成品生产计划，共 {len(semifinished_plan_df)} 条记录")
                return semifinished_plan_df
            else:
                logger.warning("未生成任何半成品生产计划")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"生成半成品生产计划失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def generate_mrp_report(self):
        """
        生成MRP综合报告
        
        返回:
            dict: MRP报告，包含各种计算结果
        """
        try:
            # 计算物料需求
            raw_requirements, semifinished_requirements = self.calculate_requirements()
            
            if raw_requirements is None or semifinished_requirements is None:
                logger.error("计算物料需求失败，无法生成报告")
                return None
            
            # 优化采购计划
            purchase_plan = self.optimize_purchase_plan()
            
            if purchase_plan is None:
                logger.error("优化采购计划失败，无法生成报告")
                return None
            
            # 生成半成品生产计划
            semifinished_plan = self.generate_semifinished_production_plan()
            
            if semifinished_plan is None:
                logger.error("生成半成品生产计划失败，无法生成报告")
                return None
            
            # 计算成本汇总
            if not purchase_plan.empty:
                total_purchase_cost = purchase_plan['预计成本'].sum()
            else:
                total_purchase_cost = 0
            
            # 创建报告
            mrp_report = {
                'raw_material_requirements': raw_requirements,
                'semifinished_requirements': semifinished_requirements,
                'purchase_plan': purchase_plan,
                'semifinished_production_plan': semifinished_plan,
                'summary': {
                    'total_raw_materials': len(raw_requirements),
                    'total_semifinished': len(semifinished_requirements),
                    'total_purchase_cost': total_purchase_cost,
                    'planning_horizon': self.mrp_parameters.get('planning_horizon', 6)
                }
            }
            
            logger.info("MRP报告生成成功")
            return mrp_report
            
        except Exception as e:
            logger.error(f"生成MRP报告失败: {str(e)}")
            return None
    
    def export_mrp_report(self, folder_path):
        """
        导出MRP报告到文件夹
        
        参数:
            folder_path: 导出文件夹路径
            
        返回:
            bool: 是否成功导出
        """
        try:
            # 确保文件夹存在
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            # 生成报告
            mrp_report = self.generate_mrp_report()
            
            if mrp_report is None:
                logger.error("生成MRP报告失败，无法导出")
                return False
            
            # 导出原材料需求
            raw_requirements_path = os.path.join(folder_path, "原材料需求.xlsx")
            mrp_report['raw_material_requirements'].to_excel(raw_requirements_path, index=False)
            
            # 导出半成品需求
            semifinished_requirements_path = os.path.join(folder_path, "半成品需求.xlsx")
            mrp_report['semifinished_requirements'].to_excel(semifinished_requirements_path, index=False)
            
            # 导出采购计划
            purchase_plan_path = os.path.join(folder_path, "采购计划.xlsx")
            mrp_report['purchase_plan'].to_excel(purchase_plan_path, index=False)
            
            # 导出半成品生产计划
            semifinished_plan_path = os.path.join(folder_path, "半成品生产计划.xlsx")
            mrp_report['semifinished_production_plan'].to_excel(semifinished_plan_path, index=False)
            
            # 导出汇总报告
            summary_path = os.path.join(folder_path, "MRP汇总报告.txt")
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("MRP汇总报告\n")
                f.write("==============\n\n")
                f.write(f"计划期数: {mrp_report['summary']['planning_horizon']}个月\n")
                f.write(f"基础原料总数: {mrp_report['summary']['total_raw_materials']}种\n")
                f.write(f"半成品总数: {mrp_report['summary']['total_semifinished']}种\n")
                f.write(f"预计采购总成本: {mrp_report['summary']['total_purchase_cost']:.2f}\n")
                
                # 添加日期和时间戳
                f.write(f"\n报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            logger.info(f"MRP报告成功导出到文件夹: {folder_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出MRP报告失败: {str(e)}")
            return False