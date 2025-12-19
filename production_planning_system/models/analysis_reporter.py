import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import io
import os
import logging
from datetime import datetime, timedelta
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
import statsmodels.api as sm
import math

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnalysisReporter:
    """
    预测分析报告模块，负责生成预测vs实际需求的对比分析报告
    """
    
    def __init__(self):
        """初始化分析报告器"""
        self.forecast_data = None
        self.actual_data = None
        self.comparison_data = None
        self.product_categories = {}  # 产品类别映射
        self.analysis_result = None
    
    def load_forecast_data(self, forecast_data):
        """
        加载预测数据
        
        参数:
            forecast_data: 预测数据DataFrame
            
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
    
    def load_actual_data(self, actual_data):
        """
        加载实际销售数据
        
        参数:
            actual_data: 实际销售数据DataFrame
            
        返回:
            bool: 是否成功加载
        """
        try:
            if not isinstance(actual_data, pd.DataFrame):
                logger.error("实际数据格式错误，需要DataFrame")
                return False
            
            # 处理不同格式的实际销售数据
            # 如果是原始出货数据，需要进行月度汇总
            if '仓库实际日期' in actual_data.columns and '物料编号' in actual_data.columns and '批次数量' in actual_data.columns:
                # 转换日期
                actual_data['仓库实际日期'] = pd.to_datetime(actual_data['仓库实际日期'])
                
                # 提取年月
                actual_data['年份'] = actual_data['仓库实际日期'].dt.year
                actual_data['月份'] = actual_data['仓库实际日期'].dt.month
                
                # 按年月和物料汇总
                aggregated_data = actual_data.groupby(['年份', '月份', '物料编号'])['批次数量'].sum().reset_index()
                aggregated_data = aggregated_data.rename(columns={'批次数量': '实际值'})
                
                self.actual_data = aggregated_data
                
            elif '年份' in actual_data.columns and '月份' in actual_data.columns and '物料编号' in actual_data.columns:
                # 检查是否包含实际销售量字段
                if '实际值' not in actual_data.columns and '实际销售量' in actual_data.columns:
                    actual_data = actual_data.rename(columns={'实际销售量': '实际值'})
                elif '实际值' not in actual_data.columns and '销售量' in actual_data.columns:
                    actual_data = actual_data.rename(columns={'销售量': '实际值'})
                elif '实际值' not in actual_data.columns and '出货量' in actual_data.columns:
                    actual_data = actual_data.rename(columns={'出货量': '实际值'})
                elif '实际值' not in actual_data.columns:
                    logger.error("无法识别实际销售量字段")
                    return False
                
                self.actual_data = actual_data
            else:
                logger.error("实际数据格式不符合要求，无法处理")
                return False
            
            logger.info(f"成功加载实际销售数据，共 {len(self.actual_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载实际销售数据失败: {str(e)}")
            return False
    
    def load_product_categories(self, category_data):
        """
        加载产品类别数据
        
        参数:
            category_data: 产品类别DataFrame或字典
            
        返回:
            bool: 是否成功加载
        """
        try:
            if isinstance(category_data, pd.DataFrame):
                # 验证必要字段
                required_fields = ['物料编号', '产品类别']
                missing_fields = [field for field in required_fields if field not in category_data.columns]
                
                if missing_fields:
                    logger.error(f"产品类别数据缺少必要字段: {', '.join(missing_fields)}")
                    return False
                
                # 转换为字典
                self.product_categories = dict(zip(category_data['物料编号'], category_data['产品类别']))
                
            elif isinstance(category_data, dict):
                self.product_categories = category_data
            else:
                logger.error("产品类别数据格式错误，需要DataFrame或字典")
                return False
            
            logger.info(f"成功加载产品类别数据，共 {len(self.product_categories)} 个产品")
            return True
            
        except Exception as e:
            logger.error(f"加载产品类别数据失败: {str(e)}")
            return False
    
    def prepare_comparison_data(self):
        """
        准备预测与实际数据的对比
        
        返回:
            DataFrame: 包含预测值和实际值的对比数据
        """
        if self.forecast_data is None:
            logger.error("未加载预测数据，无法进行对比")
            return None
        
        if self.actual_data is None:
            logger.error("未加载实际销售数据，无法进行对比")
            return None
        
        try:
            # 合并预测数据和实际数据
            comparison = pd.merge(
                self.forecast_data[['年份', '月份', '物料编号', '预测值']],
                self.actual_data[['年份', '月份', '物料编号', '实际值']],
                on=['年份', '月份', '物料编号'],
                how='outer'
            )
            
            # 填充缺失值
            comparison['预测值'].fillna(0, inplace=True)
            comparison['实际值'].fillna(0, inplace=True)
            
            # 计算绝对偏差和相对偏差
            comparison['绝对偏差'] = comparison['预测值'] - comparison['实际值']
            comparison['相对偏差'] = comparison.apply(
                lambda x: (x['绝对偏差'] / x['实际值']) * 100 if x['实际值'] > 0 else 0, 
                axis=1
            )
            
            # 添加偏差方向
            comparison['偏差方向'] = comparison.apply(
                lambda x: '预测过高' if x['绝对偏差'] > 0 else ('预测过低' if x['绝对偏差'] < 0 else '无偏差'),
                axis=1
            )
            
            # 添加预测准确率
            comparison['预测准确率'] = comparison.apply(
                lambda x: max(0, 100 - abs(x['相对偏差'])) if x['实际值'] > 0 else 0,
                axis=1
            )
            
            # 添加产品类别
            if self.product_categories:
                comparison['产品类别'] = comparison['物料编号'].map(lambda x: self.product_categories.get(x, '未分类'))
            else:
                comparison['产品类别'] = '未分类'
            
            # 排序
            comparison = comparison.sort_values(['年份', '月份', '物料编号'])
            
            self.comparison_data = comparison
            logger.info(f"成功生成预测vs实际对比数据，共 {len(comparison)} 条记录")
            return comparison
            
        except Exception as e:
            logger.error(f"准备对比数据失败: {str(e)}")
            return None
    
    def calculate_forecast_accuracy(self):
        """
        计算预测准确率，按产品类别和整体进行统计
        
        返回:
            tuple: (整体准确率DataFrame, 类别准确率DataFrame)
        """
        if self.comparison_data is None:
            logger.error("未生成对比数据，无法计算准确率")
            return None, None
        
        try:
            comparison = self.comparison_data.copy()
            
            # 计算整体准确率
            overall_accuracy = comparison.groupby(['年份', '月份']).agg({
                '预测准确率': 'mean',
                '物料编号': 'count'
            }).reset_index()
            
            overall_accuracy.rename(columns={'物料编号': '产品数量'}, inplace=True)
            
            # 计算类别准确率
            category_accuracy = comparison.groupby(['年份', '月份', '产品类别']).agg({
                '预测准确率': 'mean',
                '物料编号': 'count'
            }).reset_index()
            
            category_accuracy.rename(columns={'物料编号': '产品数量'}, inplace=True)
            
            # 添加总体统计
            category_totals = comparison.groupby(['产品类别']).agg({
                '预测准确率': 'mean',
                '物料编号': 'nunique'
            }).reset_index()
            
            category_totals['年份'] = '总计'
            category_totals['月份'] = '总计'
            category_totals.rename(columns={'物料编号': '产品数量'}, inplace=True)
            category_accuracy = pd.concat([category_accuracy, category_totals])
            
            logger.info("成功计算预测准确率")
            return overall_accuracy, category_accuracy
            
        except Exception as e:
            logger.error(f"计算准确率失败: {str(e)}")
            return None, None
    
    def analyze_forecast_bias(self, top_n=10):
        """
        预测偏差分析，识别偏差最大的产品及可能原因
        
        参数:
            top_n: 返回偏差最大的前N个产品
            
        返回:
            tuple: (正偏差产品DataFrame, 负偏差产品DataFrame, 偏差原因分析)
        """
        if self.comparison_data is None:
            logger.error("未生成对比数据，无法分析偏差")
            return None, None, None
        
        try:
            comparison = self.comparison_data.copy()
            
            # 对每个产品计算平均绝对偏差和平均相对偏差
            product_bias = comparison.groupby(['物料编号', '产品类别']).agg({
                '绝对偏差': 'mean',
                '相对偏差': 'mean',
                '预测值': 'mean',
                '实际值': 'mean'
            }).reset_index()
            
            # 排序并选取偏差最大的正负产品
            positive_bias = product_bias[product_bias['绝对偏差'] > 0].sort_values('绝对偏差', ascending=False).head(top_n)
            negative_bias = product_bias[product_bias['绝对偏差'] < 0].sort_values('绝对偏差').head(top_n)
            
            # 分析可能的原因
            bias_analysis = []
            
            for bias_type, bias_data in [("预测过高", positive_bias), ("预测过低", negative_bias)]:
                for _, row in bias_data.iterrows():
                    material_id = row['物料编号']
                    bias = row['绝对偏差']
                    relative_bias = row['相对偏差']
                    
                    # 获取该物料的历史数据
                    material_history = comparison[comparison['物料编号'] == material_id].sort_values(['年份', '月份'])
                    
                    # 计算预测与实际的相关系数
                    if len(material_history) > 2:
                        correlation = material_history[['预测值', '实际值']].corr().iloc[0, 1]
                    else:
                        correlation = 0
                    
                    # 判断是否为季节性问题
                    seasonal_issue = False
                    if len(material_history) >= 12:
                        # 简单的季节性检测：检查是否在同一月份上存在类似的偏差模式
                        for month in range(1, 13):
                            monthly_data = material_history[material_history['月份'] == month]
                            if len(monthly_data) >= 2:
                                monthly_bias = monthly_data['绝对偏差'].mean()
                                if (bias > 0 and monthly_bias > 0) or (bias < 0 and monthly_bias < 0):
                                    seasonal_issue = True
                                    break
                    
                    # 判断是否为趋势问题（预测未及时反应趋势变化）
                    trend_issue = False
                    if len(material_history) >= 3:
                        # 检查实际值是否有明显趋势，而预测滞后跟进
                        actual_vals = material_history['实际值'].values
                        if (bias > 0 and np.polyfit(range(len(actual_vals)), actual_vals, 1)[0] < 0) or \
                           (bias < 0 and np.polyfit(range(len(actual_vals)), actual_vals, 1)[0] > 0):
                            trend_issue = True
                    
                    # 分析原因
                    reasons = []
                    
                    if abs(relative_bias) > 50:
                        reasons.append("偏差非常大，可能是异常订单或市场重大变化")
                    
                    if correlation < 0.5:
                        reasons.append("预测与实际相关性低，预测模型可能不适合")
                    
                    if seasonal_issue:
                        reasons.append("可能存在季节性问题，预测未正确考虑季节因素")
                    
                    if trend_issue:
                        reasons.append("预测未能及时跟进销售趋势变化")
                    
                    if not reasons:
                        reasons.append("需要进一步调查原因")
                    
                    bias_analysis.append({
                        '物料编号': material_id,
                        '产品类别': row['产品类别'],
                        '平均预测值': row['预测值'],
                        '平均实际值': row['实际值'],
                        '绝对偏差': bias,
                        '相对偏差(%)': relative_bias,
                        '偏差方向': bias_type,
                        '可能原因': '; '.join(reasons)
                    })
            
            bias_analysis_df = pd.DataFrame(bias_analysis)
            
            logger.info(f"成功分析预测偏差，识别了 {len(bias_analysis)} 个高偏差产品")
            return positive_bias, negative_bias, bias_analysis_df
            
        except Exception as e:
            logger.error(f"分析预测偏差失败: {str(e)}")
            return None, None, None
    
    def generate_trend_charts(self, key_materials=None, report_period=None):
        """
        生成关键产品的预测vs实际需求趋势图
        
        参数:
            key_materials: 关键物料编号列表，如果为None则自动选择TOP产品
            report_period: 报告期(年份,月份)，用于标记当前报告月份
            
        返回:
            dict: 包含图表对象的字典
        """
        if self.comparison_data is None:
            logger.error("未生成对比数据，无法生成趋势图")
            return None
        
        try:
            comparison = self.comparison_data.copy()
            
            # 如果未指定关键物料，则选择销量最大的前5个产品
            if key_materials is None:
                key_materials = comparison.groupby('物料编号')['实际值'].sum().nlargest(5).index.tolist()
            
            # 如果列表过长，截断到10个
            if len(key_materials) > 10:
                key_materials = key_materials[:10]
            
            # 创建图表字典
            charts = {}
            
            # 为每个关键产品生成趋势图
            for material_id in key_materials:
                material_data = comparison[comparison['物料编号'] == material_id].sort_values(['年份', '月份'])
                
                if material_data.empty:
                    continue
                
                # 创建图表
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # 生成横轴日期标签
                date_labels = [f"{year}-{month}" for year, month in zip(material_data['年份'], material_data['月份'])]
                
                # 绘制预测值和实际值
                ax.plot(date_labels, material_data['预测值'], marker='o', label='预测值')
                ax.plot(date_labels, material_data['实际值'], marker='x', label='实际值')
                
                # 如果有报告期，添加垂直线标记当前月份
                if report_period is not None:
                    report_year, report_month = report_period
                    report_label = f"{report_year}-{report_month}"
                    if report_label in date_labels:
                        ax.axvline(x=date_labels.index(report_label), color='r', linestyle='--', label='当前报告月')
                
                # 添加标题和标签
                product_category = material_data['产品类别'].iloc[0] if not material_data['产品类别'].iloc[0] == '未分类' else ''
                title = f"物料 {material_id} {product_category} 预测vs实际趋势"
                ax.set_title(title)
                ax.set_xlabel('年月')
                ax.set_ylabel('数量')
                ax.legend()
                
                # 旋转x轴标签
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # 添加到图表字典
                charts[material_id] = fig
            
            # 生成整体趋势图
            overall_data = comparison.groupby(['年份', '月份']).agg({
                '预测值': 'sum',
                '实际值': 'sum'
            }).reset_index()
            
            overall_data = overall_data.sort_values(['年份', '月份'])
            
            # 创建整体趋势图
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 生成横轴日期标签
            date_labels = [f"{year}-{month}" for year, month in zip(overall_data['年份'], overall_data['月份'])]
            
            # 绘制预测值和实际值
            ax.plot(date_labels, overall_data['预测值'], marker='o', label='总预测值')
            ax.plot(date_labels, overall_data['实际值'], marker='x', label='总实际值')
            
            # 如果有报告期，添加垂直线标记当前月份
            if report_period is not None:
                report_year, report_month = report_period
                report_label = f"{report_year}-{report_month}"
                if report_label in date_labels:
                    ax.axvline(x=date_labels.index(report_label), color='r', linestyle='--', label='当前报告月')
            
            # 添加标题和标签
            ax.set_title("所有产品总体预测vs实际趋势")
            ax.set_xlabel('年月')
            ax.set_ylabel('数量')
            ax.legend()
            
            # 旋转x轴标签
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 添加到图表字典
            charts['overall'] = fig
            
            # 生成预测准确率趋势图
            accuracy_data = comparison.groupby(['年份', '月份']).agg({
                '预测准确率': 'mean'
            }).reset_index()
            
            accuracy_data = accuracy_data.sort_values(['年份', '月份'])
            
            # 创建准确率趋势图
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 生成横轴日期标签
            date_labels = [f"{year}-{month}" for year, month in zip(accuracy_data['年份'], accuracy_data['月份'])]
            
            # 绘制预测准确率
            ax.plot(date_labels, accuracy_data['预测准确率'], marker='o')
            ax.axhline(y=90, color='g', linestyle='--', label='优秀 (90%)')
            ax.axhline(y=80, color='y', linestyle='--', label='良好 (80%)')
            ax.axhline(y=70, color='r', linestyle='--', label='及格 (70%)')
            
            # 如果有报告期，添加垂直线标记当前月份
            if report_period is not None:
                report_year, report_month = report_period
                report_label = f"{report_year}-{report_month}"
                if report_label in date_labels:
                    ax.axvline(x=date_labels.index(report_label), color='r', linestyle='--', label='当前报告月')
            
            # 添加标题和标签
            ax.set_title("预测准确率趋势")
            ax.set_xlabel('年月')
            ax.set_ylabel('准确率 (%)')
            ax.set_ylim([0, 100])
            ax.legend()
            
            # 旋转x轴标签
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 添加到图表字典
            charts['accuracy'] = fig
            
            logger.info(f"成功生成 {len(charts)} 个趋势图")
            return charts
            
        except Exception as e:
            logger.error(f"生成趋势图失败: {str(e)}")
            return None
    
    def generate_model_recommendations(self):
        """
        基于历史偏差模式生成预测模型调整建议
        
        返回:
            DataFrame: 模型调整建议
        """
        if self.comparison_data is None:
            logger.error("未生成对比数据，无法生成模型建议")
            return None
        
        try:
            comparison = self.comparison_data.copy()
            
            # 按产品分组计算指标
            product_metrics = comparison.groupby('物料编号').agg({
                '相对偏差': ['mean', 'std'],
                '绝对偏差': ['mean', 'std'],
                '预测值': ['mean', 'std'],
                '实际值': ['mean', 'std'],
                '预测准确率': 'mean'
            })
            
            product_metrics.columns = ['相对偏差_均值', '相对偏差_标准差', 
                                      '绝对偏差_均值', '绝对偏差_标准差',
                                      '预测值_均值', '预测值_标准差',
                                      '实际值_均值', '实际值_标准差',
                                      '预测准确率_均值']
            
            product_metrics.reset_index(inplace=True)
            
            # 添加产品类别
            if self.product_categories:
                product_metrics['产品类别'] = product_metrics['物料编号'].map(lambda x: self.product_categories.get(x, '未分类'))
            else:
                product_metrics['产品类别'] = '未分类'
            
            # 生成建议
            recommendations = []
            
            for _, row in product_metrics.iterrows():
                material_id = row['物料编号']
                
                # 准备数据
                material_data = comparison[comparison['物料编号'] == material_id].sort_values(['年份', '月份'])
                
                # 至少需要3个数据点才能分析
                if len(material_data) < 3:
                    continue
                
                # 提取指标
                bias_mean = row['绝对偏差_均值']
                bias_std = row['绝对偏差_标准差']
                rel_bias_mean = row['相对偏差_均值']
                rel_bias_std = row['相对偏差_标准差']
                accuracy = row['预测准确率_均值']
                
                # 计算时间序列特征
                if len(material_data) >= 12:
                    # 检查季节性
                    try:
                        # 使用简单的季节性分解
                        time_series = material_data['实际值'].values
                        result = sm.tsa.seasonal_decompose(time_series, model='additive', period=12)
                        
                        # 计算季节强度
                        seasonal_strength = abs(result.seasonal).max() / abs(time_series).std()
                        has_seasonality = seasonal_strength > 0.3
                    except:
                        has_seasonality = False
                        seasonal_strength = 0
                else:
                    has_seasonality = False
                    seasonal_strength = 0
                
                # 检查趋势
                actual_vals = material_data['实际值'].values
                trend_coefficient = np.polyfit(range(len(actual_vals)), actual_vals, 1)[0]
                trend_strength = abs(trend_coefficient) / material_data['实际值'].mean()
                has_trend = trend_strength > 0.1
                
                # 检查波动性
                volatility = material_data['实际值'].std() / material_data['实际值'].mean()
                is_volatile = volatility > 0.3
                
                # 生成建议
                recommendation = {
                    '物料编号': material_id,
                    '产品类别': row['产品类别'],
                    '当前准确率(%)': accuracy,
                    '建议': [],
                    '建议预测方法': [],
                    '置信区间调整': ''
                }
                
                # 基于不同情况生成建议
                if accuracy < 70:
                    recommendation['建议'].append("准确率低，需要重新评估预测方法")
                    
                    if abs(rel_bias_mean) > 20:
                        if rel_bias_mean > 0:
                            recommendation['建议'].append(f"预测持续偏高，建议降低预测基准约 {abs(rel_bias_mean):.1f}%")
                        else:
                            recommendation['建议'].append(f"预测持续偏低，建议提高预测基准约 {abs(rel_bias_mean):.1f}%")
                
                # 根据时间序列特征推荐方法
                if has_seasonality:
                    recommendation['建议'].append(f"检测到明显季节性(强度:{seasonal_strength:.2f})，需考虑季节因素")
                    recommendation['建议预测方法'].append("SARIMA或季节性指数平滑")
                
                if has_trend:
                    if trend_coefficient > 0:
                        trend_dir = "上升"
                    else:
                        trend_dir = "下降"
                    
                    recommendation['建议'].append(f"检测到明显{trend_dir}趋势(强度:{trend_strength:.2f})，预测应跟踪趋势变化")
                    recommendation['建议预测方法'].append("具有趋势项的ARIMA或Holt冬季指数平滑")
                
                if is_volatile:
                    recommendation['建议'].append(f"销售波动较大(波动率:{volatility:.2f})，预测难度高")
                    recommendation['建议预测方法'].append("机器学习方法如随机森林或xgboost")
                    recommendation['置信区间调整'] = f"扩大置信区间至±{min(50, int(volatility*100))}%"
                else:
                    recommendation['置信区间调整'] = f"标准置信区间±{max(10, int(volatility*50))}%"
                
                # 如果没有特别建议，给出默认建议
                if not recommendation['建议预测方法']:
                    if accuracy > 85:
                        recommendation['建议预测方法'].append("保持当前方法")
                    else:
                        recommendation['建议预测方法'].append("简单指数平滑或移动平均")
                
                # 合并建议文本
                recommendation['建议'] = '; '.join(recommendation['建议'])
                recommendation['建议预测方法'] = '; '.join(recommendation['建议预测方法'])
                
                recommendations.append(recommendation)
            
            # 创建DataFrame
            if recommendations:
                recommendations_df = pd.DataFrame(recommendations)
                logger.info(f"成功生成 {len(recommendations)} 个模型调整建议")
                return recommendations_df
            else:
                logger.warning("未生成任何模型调整建议")
                return pd.DataFrame(columns=['物料编号', '产品类别', '当前准确率(%)', '建议', '建议预测方法', '置信区间调整'])
                
        except Exception as e:
            logger.error(f"生成模型建议失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def calculate_confidence_intervals(self, target_period=None):
        """
        计算下月需求预测的置信区间
        
        参数:
            target_period: 目标预测期(年份,月份)，如果为None则使用最近一期的下一月
            
        返回:
            DataFrame: 包含置信区间的预测数据
        """
        if self.comparison_data is None:
            logger.error("未生成对比数据，无法计算置信区间")
            return None
        
        try:
            comparison = self.comparison_data.copy()
            
            # 确定目标预测期
            if target_period is None:
                # 获取最近一期
                latest = comparison.sort_values(['年份', '月份']).iloc[-1]
                latest_year, latest_month = latest['年份'], latest['月份']
                
                # 计算下一月
                if latest_month == 12:
                    target_year = latest_year + 1
                    target_month = 1
                else:
                    target_year = latest_year
                    target_month = latest_month + 1
                
                target_period = (target_year, target_month)
            
            # 为每个产品计算预测误差标准差
            prediction_errors = comparison.groupby('物料编号').apply(
                lambda x: np.std(x['预测值'] - x['实际值']) / 
                          max(1, x['实际值'].mean())  # 归一化以计算相对误差
            ).reset_index()
            prediction_errors.columns = ['物料编号', '归一化误差标准差']
            
            # 生成置信区间
            forecast_with_ci = []
            
            for material_id, error_std in zip(prediction_errors['物料编号'], prediction_errors['归一化误差标准差']):
                # 获取物料的历史数据
                material_data = comparison[comparison['物料编号'] == material_id].sort_values(['年份', '月份'])
                
                if material_data.empty:
                    continue
                
                # 获取最新的预测值
                latest_data = material_data.sort_values(['年份', '月份']).iloc[-1]
                latest_forecast = latest_data['预测值']
                
                # 获取產品类别
                product_category = latest_data['产品类别']
                
                # 计算预测值（简单方法：使用最新预测）
                forecast_value = latest_forecast
                
                # 使用历史误差标准差计算置信区间
                # 95%置信区间约为±1.96个标准差
                confidence_factor = 1.96
                
                # 最小误差标准设为5%
                error_std = max(0.05, error_std)
                
                # 计算置信区间
                lower_bound = forecast_value * (1 - confidence_factor * error_std)
                upper_bound = forecast_value * (1 + confidence_factor * error_std)
                
                # 记录结果
                forecast_with_ci.append({
                    '物料编号': material_id,
                    '产品类别': product_category,
                    '预测年份': target_period[0],
                    '预测月份': target_period[1],
                    '预测值': forecast_value,
                    '下限': max(0, lower_bound),  # 预测量不能为负
                    '上限': upper_bound,
                    '置信区间(%)': f"±{round(confidence_factor * error_std * 100, 1)}%",
                    '历史预测误差(%)': round(error_std * 100, 1)
                })
            
            # 创建DataFrame
            if forecast_with_ci:
                ci_df = pd.DataFrame(forecast_with_ci)
                logger.info(f"成功计算 {len(forecast_with_ci)} 个产品的预测置信区间")
                return ci_df
            else:
                logger.warning("未生成任何预测置信区间")
                return pd.DataFrame(columns=['物料编号', '产品类别', '预测年份', '预测月份', 
                                            '预测值', '下限', '上限', '置信区间(%)', '历史预测误差(%)'])
                
        except Exception as e:
            logger.error(f"计算置信区间失败: {str(e)}")
            return None
    
    def generate_analysis_report(self, report_period=None, key_materials=None):
        """
        生成完整的分析报告
        
        参数:
            report_period: 报告期(年份,月份)，如果为None则使用最近一期
            key_materials: 关键物料编号列表，如果为None则自动选择TOP产品
            
        返回:
            dict: 报告内容字典
        """
        try:
            # 准备对比数据
            self.prepare_comparison_data()
            
            if self.comparison_data is None:
                logger.error("生成对比数据失败，无法生成报告")
                return None
            
            comparison = self.comparison_data.copy()
            
            # 确定报告期
            if report_period is None:
                # 获取最近一期
                latest = comparison.sort_values(['年份', '月份']).iloc[-1]
                report_period = (latest['年份'], latest['月份'])
            
            # 计算预测准确率
            overall_accuracy, category_accuracy = self.calculate_forecast_accuracy()
            
            # 分析预测偏差
            positive_bias, negative_bias, bias_analysis = self.analyze_forecast_bias()
            
            # 生成趋势图
            trend_charts = self.generate_trend_charts(key_materials, report_period)
            
            # 生成模型建议
            model_recommendations = self.generate_model_recommendations()
            
            # 计算置信区间
            # 获取目标预测期（报告期的下一月）
            report_year, report_month = report_period
            if report_month == 12:
                target_year = report_year + 1
                target_month = 1
            else:
                target_year = report_year
                target_month = report_month + 1
                
            confidence_intervals = self.calculate_confidence_intervals((target_year, target_month))
            
            # 创建报告结果
            report = {
                'report_period': report_period,
                'comparison_data': comparison,
                'overall_accuracy': overall_accuracy,
                'category_accuracy': category_accuracy,
                'positive_bias': positive_bias,
                'negative_bias': negative_bias,
                'bias_analysis': bias_analysis,
                'trend_charts': trend_charts,
                'model_recommendations': model_recommendations,
                'confidence_intervals': confidence_intervals
            }
            
            # 设置分析结果
            self.analysis_result = report
            
            logger.info(f"成功生成{report_period[0]}年{report_period[1]}月的预测分析报告")
            return report
            
        except Exception as e:
            logger.error(f"生成分析报告失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def export_excel_report(self, output_path):
        """
        导出Excel格式的分析报告
        
        参数:
            output_path: 输出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.analysis_result is None:
            logger.error("未生成分析报告，无法导出Excel")
            return False
        
        try:
            report = self.analysis_result
            
            # 创建Excel文件
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 写入对比数据
                report['comparison_data'].to_excel(writer, sheet_name='预测vs实际对比', index=False)
                
                # 写入准确率数据
                report['overall_accuracy'].to_excel(writer, sheet_name='整体准确率', index=False)
                report['category_accuracy'].to_excel(writer, sheet_name='类别准确率', index=False)
                
                # 写入偏差分析
                if report['bias_analysis'] is not None:
                    report['bias_analysis'].to_excel(writer, sheet_name='预测偏差分析', index=False)
                
                # 写入模型建议
                if report['model_recommendations'] is not None:
                    report['model_recommendations'].to_excel(writer, sheet_name='预测模型调整建议', index=False)
                
                # 写入置信区间
                if report['confidence_intervals'] is not None:
                    report['confidence_intervals'].to_excel(writer, sheet_name='下月预测置信区间', index=False)
                
                # 写入报告摘要
                summary_data = []
                
                # 添加报告期信息
                report_year, report_month = report['report_period']
                summary_data.append(['报告期', f"{report_year}年{report_month}月"])
                
                # 添加整体准确率
                if report['overall_accuracy'] is not None and not report['overall_accuracy'].empty:
                    current_accuracy = report['overall_accuracy'][
                        (report['overall_accuracy']['年份'] == report_year) & 
                        (report['overall_accuracy']['月份'] == report_month)
                    ]
                    
                    if not current_accuracy.empty:
                        overall_acc = current_accuracy['预测准确率'].iloc[0]
                        summary_data.append(['整体预测准确率', f"{overall_acc:.2f}%"])
                    
                # 添加产品数量
                summary_data.append(['分析产品数量', len(report['comparison_data']['物料编号'].unique())])
                
                # 创建摘要DataFrame
                summary_df = pd.DataFrame(summary_data, columns=['指标', '值'])
                summary_df.to_excel(writer, sheet_name='报告摘要', index=False)
            
            logger.info(f"成功导出Excel报告至 {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出Excel报告失败: {str(e)}")
            return False
    
    def export_pdf_report(self, output_path):
        """
        导出PDF格式的分析报告
        
        参数:
            output_path: 输出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.analysis_result is None:
            logger.error("未生成分析报告，无法导出PDF")
            return False
        
        try:
            report = self.analysis_result
            
            # 创建PDF文件
            with PdfPages(output_path) as pdf:
                # 添加报告标题页
                report_year, report_month = report['report_period']
                plt.figure(figsize=(8.5, 11))
                plt.text(0.5, 0.8, "预测需求与实际需求对比分析报告", 
                         horizontalalignment='center', fontsize=20, weight='bold')
                plt.text(0.5, 0.7, f"{report_year}年{report_month}月", 
                         horizontalalignment='center', fontsize=16)
                plt.text(0.5, 0.6, f"生成日期: {datetime.now().strftime('%Y-%m-%d')}", 
                         horizontalalignment='center', fontsize=12)
                plt.axis('off')
                pdf.savefig()
                plt.close()
                
                # 添加趋势图
                if report['trend_charts'] is not None:
                    for _, fig in report['trend_charts'].items():
                        pdf.savefig(fig)
                        plt.close(fig)
                
                # 添加准确率表格
                plt.figure(figsize=(8.5, 11))
                plt.text(0.5, 0.95, "预测准确率统计", 
                         horizontalalignment='center', fontsize=16, weight='bold')
                
                if report['overall_accuracy'] is not None and not report['overall_accuracy'].empty:
                    table_data = report['overall_accuracy'].sort_values(['年份', '月份'])
                    
                    # 创建表格
                    plt.table(cellText=table_data.values, 
                            colLabels=table_data.columns, 
                            loc='center', 
                            cellLoc='center')
                
                plt.axis('off')
                pdf.savefig()
                plt.close()
                
                # 添加偏差分析表格
                if report['bias_analysis'] is not None and not report['bias_analysis'].empty:
                    plt.figure(figsize=(8.5, 11))
                    plt.text(0.5, 0.95, "预测偏差分析", 
                            horizontalalignment='center', fontsize=16, weight='bold')
                    
                    # 限制显示的行数，防止表格过大
                    display_data = report['bias_analysis'].head(20)
                    
                    # 创建表格
                    plt.table(cellText=display_data.values, 
                            colLabels=display_data.columns, 
                            loc='center', 
                            cellLoc='center')
                    
                    plt.axis('off')
                    pdf.savefig()
                    plt.close()
                
                # 添加模型建议表格
                if report['model_recommendations'] is not None and not report['model_recommendations'].empty:
                    plt.figure(figsize=(8.5, 11))
                    plt.text(0.5, 0.95, "预测模型调整建议", 
                            horizontalalignment='center', fontsize=16, weight='bold')
                    
                    # 限制显示的行数
                    display_data = report['model_recommendations'].head(20)
                    
                    # 创建表格
                    plt.table(cellText=display_data.values, 
                            colLabels=display_data.columns, 
                            loc='center', 
                            cellLoc='center')
                    
                    plt.axis('off')
                    pdf.savefig()
                    plt.close()
                
                # 添加置信区间表格
                if report['confidence_intervals'] is not None and not report['confidence_intervals'].empty:
                    plt.figure(figsize=(8.5, 11))
                    plt.text(0.5, 0.95, "下月预测置信区间", 
                            horizontalalignment='center', fontsize=16, weight='bold')
                    
                    # 限制显示的行数
                    display_data = report['confidence_intervals'].head(20)
                    
                    # 创建表格
                    plt.table(cellText=display_data.values, 
                            colLabels=display_data.columns, 
                            loc='center', 
                            cellLoc='center')
                    
                    plt.axis('off')
                    pdf.savefig()
                    plt.close()
            
            logger.info(f"成功导出PDF报告至 {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出PDF报告失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False