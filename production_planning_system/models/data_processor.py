import pandas as pd
import numpy as np
from datetime import datetime
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataProcessor:
    """
    历史出货数据处理模块，负责数据导入、清洗、转换和分析
    """
    
    def __init__(self):
        """初始化数据处理器"""
        self.raw_data = None
        self.processed_data = None
        self.monthly_data = None
        self.material_summary = None
    
    def load_data(self, file_path):
        """
        加载数据文件
        
        参数:
            file_path: 数据文件路径
            
        返回:
            成功加载的DataFrame或None
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
            
            logger.info(f"成功加载数据，共 {len(df)} 行")
            self.raw_data = df
            return df
        
        except Exception as e:
            logger.error(f"数据加载失败: {str(e)}")
            return None
    
    def validate_data(self):
        """
        验证数据格式是否符合要求
        
        返回:
            (bool, str): (是否有效, 错误信息)
        """
        if self.raw_data is None:
            return False, "未加载数据"
        
        # 检查必要字段
        required_fields = ['销售请求日期', '仓库实际日期', '物料编号', '批次数量']
        missing_fields = [field for field in required_fields if field not in self.raw_data.columns]
        
        if missing_fields:
            return False, f"缺少必要字段: {', '.join(missing_fields)}"
        
        # 检查数据类型
        try:
            # 尝试转换日期
            pd.to_datetime(self.raw_data['仓库实际日期'])
            
            # 检查批次数量是否为数值
            if not pd.to_numeric(self.raw_data['批次数量'], errors='coerce').notna().all():
                return False, "批次数量包含非数值数据"
        
        except Exception as e:
            return False, f"数据类型验证失败: {str(e)}"
        
        return True, "数据验证通过"
    
    def preprocess_data(self):
        """
        预处理数据，包括清洗、格式转换等
        
        返回:
            DataFrame: 处理后的数据
        """
        if self.raw_data is None:
            logger.error("未加载数据，无法处理")
            return None
        
        try:
            # 创建副本避免修改原始数据
            df = self.raw_data.copy()
            
            # 转换日期格式
            df['仓库实际日期'] = pd.to_datetime(df['仓库实际日期'])
            
            # 添加年月字段，便于后续分析
            df['年份'] = df['仓库实际日期'].dt.year
            df['月份'] = df['仓库实际日期'].dt.month
            
            # 确保批次数量为数值类型
            df['批次数量'] = pd.to_numeric(df['批次数量'], errors='coerce')
            
            # 处理缺失值
            df = df.dropna(subset=['仓库实际日期', '物料编号', '批次数量'])
            
            # 移除批次数量小于等于0的记录
            df = df[df['批次数量'] > 0]
            
            logger.info(f"数据预处理完成，剩余 {len(df)} 行")
            self.processed_data = df
            return df
            
        except Exception as e:
            logger.error(f"数据预处理失败: {str(e)}")
            return None
    
    def aggregate_monthly_data(self):
        """
        将数据按月份和物料编号汇总
        
        返回:
            DataFrame: 月度汇总数据
        """
        if self.processed_data is None:
            logger.error("未处理数据，无法汇总")
            return None
        
        try:
            # 按年份、月份和物料编号分组
            monthly_data = self.processed_data.groupby(['年份', '月份', '物料编号']).agg({
                '批次数量': 'sum',
                '仓库实际日期': 'count'  # 计算每月订单数
            }).reset_index()
            
            # 重命名计数列
            monthly_data.rename(columns={'仓库实际日期': '订单数量'}, inplace=True)
            
            logger.info(f"月度数据汇总完成，共 {len(monthly_data)} 行")
            self.monthly_data = monthly_data
            return monthly_data
            
        except Exception as e:
            logger.error(f"月度数据汇总失败: {str(e)}")
            return None
    
    def analyze_material_data(self):
        """
        分析物料出货数据，计算趋势和季节性
        
        返回:
            DataFrame: 物料分析摘要
        """
        if self.monthly_data is None:
            logger.error("未生成月度数据，无法分析")
            return None
        
        try:
            # 创建物料摘要
            summary = self.monthly_data.groupby('物料编号').agg({
                '批次数量': ['sum', 'mean', 'std', 'count']
            }).reset_index()
            
            # 调整列名
            summary.columns = ['物料编号', '总出货量', '月均出货量', '出货标准差', '数据月份数']
            
            # 计算变异系数(CV)，评估需求波动性
            summary['变异系数'] = summary['出货标准差'] / summary['月均出货量']
            
            # 计算ABC分类(基于总出货量)
            summary = summary.sort_values('总出货量', ascending=False)
            summary['累计出货量占比'] = summary['总出货量'].cumsum() / summary['总出货量'].sum()
            
            # 分类: A类(前20%)，B类(接下来的30%)，C类(剩余50%)
            summary['ABC分类'] = 'C'
            summary.loc[summary['累计出货量占比'] <= 0.5, 'ABC分类'] = 'B'
            summary.loc[summary['累计出货量占比'] <= 0.2, 'ABC分类'] = 'A'
            
            logger.info(f"物料数据分析完成，共 {len(summary)} 种物料")
            self.material_summary = summary
            return summary
            
        except Exception as e:
            logger.error(f"物料数据分析失败: {str(e)}")
            return None
    
    def calculate_seasonality(self, material_id=None):
        """
        计算季节性指数
        
        参数:
            material_id: 可选，指定物料编号。如果为None，则计算所有物料
            
        返回:
            DataFrame: 季节性系数
        """
        if self.monthly_data is None:
            logger.error("未生成月度数据，无法计算季节性")
            return None
        
        try:
            # 筛选数据
            data = self.monthly_data
            if material_id:
                data = data[data['物料编号'] == material_id]
            
            # 确保数据足够进行季节性分析(至少12个月)
            if len(data) < 12:
                logger.warning(f"数据不足12个月，季节性分析可能不准确")
            
            # 计算每月平均出货量
            monthly_avg = data.groupby('月份')['批次数量'].mean().reset_index()
            
            # 计算年度平均
            yearly_avg = monthly_avg['批次数量'].mean()
            
            # 计算季节性指数
            monthly_avg['季节性指数'] = monthly_avg['批次数量'] / yearly_avg
            
            logger.info(f"季节性指数计算完成")
            return monthly_avg
            
        except Exception as e:
            logger.error(f"季节性计算失败: {str(e)}")
            return None
    
    def export_processed_data(self, file_path):
        """
        导出处理后的数据
        
        参数:
            file_path: 导出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.processed_data is None:
            logger.error("没有处理后的数据可供导出")
            return False
        
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                self.processed_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_extension.lower() in ['.xls', '.xlsx']:
                self.processed_data.to_excel(file_path, index=False)
            else:
                logger.error(f"不支持的导出文件类型: {file_extension}")
                return False
            
            logger.info(f"数据成功导出至 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据导出失败: {str(e)}")
            return False