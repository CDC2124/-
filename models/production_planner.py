import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, timedelta
# 移除 from ortools.linear_solver import pywraplp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionPlanner:
    """
    生产计划模块，负责根据销售预测生成优化的生产计划
    使用Google OR-Tools进行优化计算
    """
    
    def __init__(self):
        """初始化生产计划器"""
        self.forecast_data = None
        self.inventory_data = None
        self.capacity_data = None
        self.production_plan = None
        self.optimization_result = None
        self.production_constraints = {}
    
    def load_forecast_data(self, forecast_data):
        """
        加载销售预测数据
        
        参数:
            forecast_data: 销售预测DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(forecast_data, pd.DataFrame):
                logger.error("预测数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['年份', '月份', '物料编号', '预测值']
            missing_fields = [field for field in required_fields if field not in forecast_data.columns]
            
            if missing_fields:
                logger.error(f"预测数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.forecast_data = forecast_data.copy()
            logger.info(f"成功加载预测数据，共 {len(forecast_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载预测数据失败: {str(e)}")
            return False
    
    def load_inventory_data(self, inventory_data):
        """
        加载库存数据
        
        参数:
            inventory_data: 库存DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(inventory_data, pd.DataFrame):
                logger.error("库存数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['物料编号', '库存数量']
            missing_fields = [field for field in required_fields if field not in inventory_data.columns]
            
            if missing_fields:
                logger.error(f"库存数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.inventory_data = inventory_data.copy()
            logger.info(f"成功加载库存数据，共 {len(inventory_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载库存数据失败: {str(e)}")
            return False
    
    def load_capacity_data(self, capacity_data):
        """
        加载产能数据
        
        参数:
            capacity_data: 产能DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(capacity_data, pd.DataFrame):
                logger.error("产能数据格式错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_fields = ['年份', '月份', '产线', '最大产能']
            missing_fields = [field for field in required_fields if field not in capacity_data.columns]
            
            if missing_fields:
                logger.error(f"产能数据缺少必要字段: {', '.join(missing_fields)}")
                return False
            
            self.capacity_data = capacity_data.copy()
            logger.info(f"成功加载产能数据，共 {len(capacity_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载产能数据失败: {str(e)}")
            return False
    
    def set_production_constraints(self, constraints):
        """
        设置生产约束参数
        
        参数:
            constraints: 约束参数字典，包括安全库存、最小生产批量等
            
        返回:
            bool: 是否成功设置
        """
        try:
            # 验证约束参数
            if not isinstance(constraints, dict):
                logger.error("约束参数必须为字典类型")
                return False
            
            # 设置默认值
            default_constraints = {
                'min_service_level': 0.95,  # 最小服务水平（满足需求的概率）
                'min_batch_size': 100,      # 最小生产批量
                'safety_stock_days': 15,    # 安全库存天数
                'max_inventory_days': 60,   # 最大库存天数
                'production_smoothing': 0.3 # 生产平滑系数（0-1，越大波动越小）
            }
            
            # 更新约束参数
            merged_constraints = {**default_constraints, **constraints}
            self.production_constraints = merged_constraints
            
            logger.info(f"成功设置生产约束参数: {merged_constraints}")
            return True
            
        except Exception as e:
            logger.error(f"设置生产约束参数失败: {str(e)}")
            return False
    
    def get_inventory_level(self, material_id):
        """
        获取指定物料的库存量
        
        参数:
            material_id: 物料编号
            
        返回:
            float: 库存数量，如果没有库存记录则返回0
        """
        if self.inventory_data is None:
            return 0
        
        try:
            # 筛选指定物料的库存记录
            inventory_record = self.inventory_data[self.inventory_data['物料编号'] == material_id]
            
            if inventory_record.empty:
                logger.warning(f"未找到物料 {material_id} 的库存记录，假设为0")
                return 0
            else:
                return inventory_record.iloc[0]['库存数量']
                
        except Exception as e:
            logger.error(f"获取库存量失败: {str(e)}")
            return 0
    
    def optimize_production_plan(self, horizon=6, objective='min_cost'):
        """
        生成生产计划（简化版，不依赖OR-Tools）
        
        参数:
            horizon: 计划期数（月）
            objective: 优化目标，可选值：'min_cost', 'smooth_production', 'min_inventory'
            
        返回:
            DataFrame: 优化后的生产计划，如果失败则返回None
        """
        if self.forecast_data is None:
            logger.error("未加载预测数据，无法生成生产计划")
            return None
        
        try:
            # 限制计划期数
            max_forecast_periods = max(self.forecast_data['年份'] * 12 + self.forecast_data['月份']) - \
                                 min(self.forecast_data['年份'] * 12 + self.forecast_data['月份']) + 1
            
            if horizon > max_forecast_periods:
                logger.warning(f"计划期数 {horizon} 超过预测期数 {max_forecast_periods}，已调整为 {max_forecast_periods}")
                horizon = max_forecast_periods
            
            # 准备物料列表
            materials = self.forecast_data['物料编号'].unique()
            
            # 准备时间段列表
            time_periods = sorted(self.forecast_data[['年份', '月份']].drop_duplicates().itertuples(index=False, name=None),
                               key=lambda x: x[0] * 12 + x[1])
            
            time_periods = time_periods[:horizon]  # 限制期数
            
            # 构建生产计划DataFrame - 简化版实现
            plan_data = []
            
            # 获取约束参数
            min_batch_size = self.production_constraints.get('min_batch_size', 100)
            safety_stock_days = self.production_constraints.get('safety_stock_days', 15)
            
            # 对每个物料生成计划
            for material in materials:
                # 获取初始库存
                initial_inventory = self.get_inventory_level(material)
                current_inventory = initial_inventory
                
                for i, (year, month) in enumerate(time_periods):
                    # 获取当月需求
                    demand = self.get_forecast_demand(material, year, month)
                    
                    # 计算安全库存
                    safety_stock = demand * safety_stock_days / 30
                    
                    # 计算净需求（需求+安全库存-库存）
                    net_demand = max(0, demand + safety_stock - current_inventory)
                    
                    # 应用最小批量规则
                    if net_demand > 0:
                        # 如果需要生产，至少生产一个最小批量
                        production = max(net_demand, min_batch_size)
                        # 向上取整到最小批量的整数倍
                        production = np.ceil(production / min_batch_size) * min_batch_size
                    else:
                        production = 0
                    
                    # 更新库存
                    ending_inventory = current_inventory + production - demand
                    
                    # 保存结果
                    plan_data.append({
                        '年份': year,
                        '月份': month,
                        '物料编号': material,
                        '预测需求': demand,
                        '计划产量': round(production),
                        '期初库存': round(current_inventory),
                        '期末库存': round(ending_inventory),
                        '库存覆盖天数': round(ending_inventory / (demand / 30), 1) if demand > 0 else float('inf')
                    })
                    
                    # 更新库存到下月
                    current_inventory = ending_inventory
            
            # 创建DataFrame
            plan_df = pd.DataFrame(plan_data)
            
            # 排序
            plan_df = plan_df.sort_values(['物料编号', '年份', '月份'])
            
            # 保存结果
            self.production_plan = plan_df
            self.optimization_result = {
                'status': 'simplified',
                'objective_value': 0,  # 简化版无目标函数值
                'solver_time': 0
            }
            
            logger.info(f"成功生成简化版生产计划，共 {len(plan_df)} 条记录")
            return plan_df
            
        except Exception as e:
            logger.error(f"生成生产计划失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_forecast_demand(self, material_id, year, month):
        """
        获取指定物料在指定月份的预测需求
        
        参数:
            material_id: 物料编号
            year: 年份
            month: 月份
            
        返回:
            float: 预测需求量，如果没有预测则返回0
        """
        if self.forecast_data is None:
            return 0
        
        try:
            # 筛选指定物料和月份的预测记录
            forecast_record = self.forecast_data[
                (self.forecast_data['物料编号'] == material_id) & 
                (self.forecast_data['年份'] == year) & 
                (self.forecast_data['月份'] == month)
            ]
            
            if forecast_record.empty:
                logger.warning(f"未找到物料 {material_id} 在 {year}-{month} 的预测记录，假设为0")
                return 0
            else:
                return forecast_record.iloc[0]['预测值']
                
        except Exception as e:
            logger.error(f"获取预测需求失败: {str(e)}")
            return 0
    
    def adjust_production_plan(self, material_id, year, month, new_production):
        """
        手动调整生产计划
        
        参数:
            material_id: 物料编号
            year: 年份
            month: 月份
            new_production: 新的计划产量
            
        返回:
            bool: 是否成功调整
        """
        if self.production_plan is None:
            logger.error("未生成生产计划，无法调整")
            return False
        
        try:
            # 定位需要调整的行
            mask = ((self.production_plan['物料编号'] == material_id) & 
                  (self.production_plan['年份'] == year) & 
                  (self.production_plan['月份'] == month))
            
            if not any(mask):
                logger.error(f"未找到要调整的计划: 物料={material_id}, 年月={year}-{month}")
                return False
            
            # 获取原计划产量
            original_production = self.production_plan.loc[mask, '计划产量'].values[0]
            
            # 调整计划产量
            self.production_plan.loc[mask, '计划产量'] = new_production
            
            # 重新计算库存
            # 更新当前月的期末库存
            demand = self.production_plan.loc[mask, '预测需求'].values[0]
            beginning_inventory = self.production_plan.loc[mask, '期初库存'].values[0]
            new_ending_inventory = beginning_inventory + new_production - demand
            self.production_plan.loc[mask, '期末库存'] = new_ending_inventory
            
            # 更新库存覆盖天数
            if demand > 0:
                new_coverage_days = round(new_ending_inventory / (demand / 30), 1)
            else:
                new_coverage_days = float('inf')
            
            self.production_plan.loc[mask, '库存覆盖天数'] = new_coverage_days
            
            # 更新后续月份的库存
            self.propagate_inventory_changes(material_id, year, month)
            
            logger.info(f"已手动调整生产计划: 物料={material_id}, 年月={year}-{month}, "
                      f"产量从 {original_production} 调整为 {new_production}")
            
            return True
            
        except Exception as e:
            logger.error(f"调整生产计划失败: {str(e)}")
            return False
    
    def propagate_inventory_changes(self, material_id, start_year, start_month):
        """
        调整生产计划后，传播库存变化到后续月份
        
        参数:
            material_id: 物料编号
            start_year: 起始年份
            start_month: 起始月份
        """
        try:
            # 获取所有计划月份
            plan_months = self.production_plan[['年份', '月份']].drop_duplicates().values
            
            # 按时间排序
            plan_months = sorted(plan_months, key=lambda x: x[0] * 12 + x[1])
            
            # 找到起始月份的索引
            start_idx = -1
            for i, (year, month) in enumerate(plan_months):
                if year == start_year and month == start_month:
                    start_idx = i
                    break
            
            if start_idx == -1 or start_idx == len(plan_months) - 1:
                # 未找到起始月份或起始月份已是最后一个月，无需继续
                return
            
            # 从下一个月开始更新
            for i in range(start_idx + 1, len(plan_months)):
                year, month = plan_months[i]
                
                # 找到上一个月
                prev_year, prev_month = plan_months[i - 1]
                
                # 获取当前月的记录
                curr_mask = ((self.production_plan['物料编号'] == material_id) & 
                           (self.production_plan['年份'] == year) & 
                           (self.production_plan['月份'] == month))
                
                # 获取上一个月的记录
                prev_mask = ((self.production_plan['物料编号'] == material_id) & 
                           (self.production_plan['年份'] == prev_year) & 
                           (self.production_plan['月份'] == prev_month))
                
                if not any(curr_mask) or not any(prev_mask):
                    continue
                
                # 获取数据
                prev_ending_inventory = self.production_plan.loc[prev_mask, '期末库存'].values[0]
                curr_production = self.production_plan.loc[curr_mask, '计划产量'].values[0]
                curr_demand = self.production_plan.loc[curr_mask, '预测需求'].values[0]
                
                # 更新当前月的期初库存
                self.production_plan.loc[curr_mask, '期初库存'] = prev_ending_inventory
                
                # 更新当前月的期末库存
                new_ending_inventory = prev_ending_inventory + curr_production - curr_demand
                self.production_plan.loc[curr_mask, '期末库存'] = new_ending_inventory
                
                # 更新库存覆盖天数
                if curr_demand > 0:
                    new_coverage_days = round(new_ending_inventory / (curr_demand / 30), 1)
                else:
                    new_coverage_days = float('inf')
                
                self.production_plan.loc[curr_mask, '库存覆盖天数'] = new_coverage_days
            
        except Exception as e:
            logger.error(f"传播库存变化失败: {str(e)}")
    
    def export_production_plan(self, file_path):
        """
        导出生产计划
        
        参数:
            file_path: 导出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.production_plan is None:
            logger.error("未生成生产计划，无法导出")
            return False
        
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                self.production_plan.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_extension.lower() in ['.xls', '.xlsx']:
                self.production_plan.to_excel(file_path, index=False)
            else:
                logger.error(f"不支持的导出文件类型: {file_extension}")
                return False
            
            logger.info(f"生产计划成功导出至 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出生产计划失败: {str(e)}")
            return False