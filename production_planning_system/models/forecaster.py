import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
import warnings

# 忽略警告信息，避免在预测中显示过多的警告
warnings.filterwarnings("ignore")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Forecaster:
    """
    销售预测模块，支持多种预测算法和参数调整
    """
    
    def __init__(self):
        """初始化预测器"""
        self.historical_data = None
        self.forecast_data = None
        self.forecast_models = {}
        self.forecast_accuracy = {}
        self.forecast_periods = 12  # 默认预测12个月
        
    def load_data(self, monthly_data):
        """
        加载月度历史数据
        
        参数:
            monthly_data: 包含年份、月份、物料编号和批次数量的DataFrame
            
        返回:
            bool: 是否成功加载数据
        """
        try:
            if not isinstance(monthly_data, pd.DataFrame):
                logger.error("输入数据类型错误，需要DataFrame")
                return False
            
            # 验证必要字段
            required_cols = ['年份', '月份', '物料编号', '批次数量']
            if not all(col in monthly_data.columns for col in required_cols):
                missing_cols = [col for col in required_cols if col not in monthly_data.columns]
                logger.error(f"数据缺少必要字段: {missing_cols}")
                return False
            
            # 创建时间序列索引
            monthly_data['日期'] = pd.to_datetime(monthly_data['年份'].astype(str) + '-' + 
                                               monthly_data['月份'].astype(str) + '-01')
            
            self.historical_data = monthly_data
            logger.info(f"成功加载历史数据，包含 {len(monthly_data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"加载数据失败: {str(e)}")
            return False
    
    def prepare_time_series(self, material_id):
        """
        为特定物料准备时间序列数据
        
        参数:
            material_id: 物料编号
            
        返回:
            Series: 时间序列数据，如果失败则返回None
        """
        if self.historical_data is None:
            logger.error("未加载历史数据")
            return None
        
        try:
            # 筛选特定物料的数据
            material_data = self.historical_data[self.historical_data['物料编号'] == material_id]
            
            if len(material_data) == 0:
                logger.error(f"未找到物料 {material_id} 的历史数据")
                return None
            
            # 按日期排序
            material_data = material_data.sort_values('日期')
            
            # 创建时间序列
            time_series = material_data.set_index('日期')['批次数量']
            
            # 确保索引是日期类型
            time_series.index = pd.DatetimeIndex(time_series.index).to_period('M')
            
            # 检查数据连续性，填充缺失月份
            date_range = pd.period_range(start=time_series.index.min(), 
                                        end=time_series.index.max(), 
                                        freq='M')
            
            if len(date_range) > len(time_series):
                # 有缺失的月份，进行填充
                full_idx_series = pd.Series(index=date_range, dtype=float)
                time_series = time_series.combine_first(full_idx_series).fillna(0)
                logger.info(f"填充了 {len(date_range) - len(material_data)} 个缺失的月份")
            
            return time_series
            
        except Exception as e:
            logger.error(f"准备时间序列失败: {str(e)}")
            return None
    
    def forecast_arima(self, time_series, periods=None, order=(1,1,1)):
        """
        使用ARIMA模型进行预测
        
        参数:
            time_series: 时间序列数据
            periods: 预测期数，如果为None，则使用默认值
            order: ARIMA模型的参数 (p,d,q)
            
        返回:
            DataFrame: 预测结果，包含预测值和置信区间
        """
        if time_series is None or len(time_series) < 12:
            logger.error("时间序列数据不足，无法用ARIMA预测")
            return None
        
        periods = periods or self.forecast_periods
        
        try:
            # 转换为浮点类型
            time_series = time_series.astype(float)
            
            # 训练ARIMA模型
            model = ARIMA(time_series, order=order)
            model_fit = model.fit()
            
            # 预测
            forecast_result = model_fit.forecast(steps=periods)
            
            # 获取置信区间
            forecast_ci = model_fit.get_forecast(steps=periods).conf_int(alpha=0.05)
            
            # 创建预测结果DataFrame
            last_date = time_series.index[-1]
            forecast_dates = [last_date + i + 1 for i in range(periods)]
            
            forecast_df = pd.DataFrame({
                '预测值': forecast_result,
                '下限': forecast_ci.iloc[:, 0].values,
                '上限': forecast_ci.iloc[:, 1].values
            }, index=forecast_dates)
            
            logger.info(f"ARIMA预测完成，预测 {periods} 期")
            return forecast_df
            
        except Exception as e:
            logger.error(f"ARIMA预测失败: {str(e)}")
            return None
    
    def forecast_exponential_smoothing(self, time_series, periods=None, seasonal_periods=12,
                                     trend=None, seasonal=None, damped_trend=False):
        """
        使用指数平滑法进行预测
        
        参数:
            time_series: 时间序列数据
            periods: 预测期数，如果为None，则使用默认值
            seasonal_periods: 季节周期，默认为12(月度数据)
            trend: 趋势类型 - 'add'(加法)或'mul'(乘法)或None(无趋势)
            seasonal: 季节性类型 - 'add'(加法)或'mul'(乘法)或None(无季节性)
            damped_trend: 是否使用阻尼趋势
            
        返回:
            DataFrame: 预测结果，包含预测值
        """
        if time_series is None or len(time_series) < 12:
            logger.error("时间序列数据不足，无法用指数平滑法预测")
            return None
        
        periods = periods or self.forecast_periods
        
        try:
            # 转换为浮点类型
            time_series = time_series.astype(float)
            
            # 自动检测趋势和季节性类型
            if trend is None or seasonal is None:
                # 对数据进行简单分析
                decomposition = seasonal_decompose(time_series, model='multiplicative', period=seasonal_periods)
                
                # 检测趋势
                trend_strength = abs(decomposition.trend).std() / abs(time_series).std()
                if trend is None:
                    trend = 'add' if trend_strength > 0.3 else None
                
                # 检测季节性
                season_strength = abs(decomposition.seasonal).std() / abs(time_series).std()
                if seasonal is None:
                    seasonal = 'mul' if season_strength > 0.3 else None
            
            # 创建并训练模型
            model = ExponentialSmoothing(
                time_series,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=seasonal_periods,
                damped_trend=damped_trend
            )
            model_fit = model.fit(optimized=True)
            
            # 预测
            forecast_result = model_fit.forecast(periods)
            
            # 创建预测结果DataFrame
            last_date = time_series.index[-1]
            forecast_dates = [last_date + i + 1 for i in range(periods)]
            
            # 计算简单的置信区间(基于预测值的一定比例)
            forecast_std = time_series.std()
            lower_bound = forecast_result - 1.96 * forecast_std
            upper_bound = forecast_result + 1.96 * forecast_std
            
            forecast_df = pd.DataFrame({
                '预测值': forecast_result,
                '下限': lower_bound,
                '上限': upper_bound
            }, index=forecast_dates)
            
            logger.info(f"指数平滑预测完成，预测 {periods} 期")
            return forecast_df
            
        except Exception as e:
            logger.error(f"指数平滑预测失败: {str(e)}")
            return None
    
    def forecast_moving_average(self, time_series, periods=None, window=3):
        """
        使用移动平均法进行预测
        
        参数:
            time_series: 时间序列数据
            periods: 预测期数，如果为None，则使用默认值
            window: 移动平均窗口大小
            
        返回:
            DataFrame: 预测结果，包含预测值
        """
        if time_series is None or len(time_series) < window:
            logger.error(f"时间序列数据不足，无法用移动平均法预测(需要至少 {window} 期)")
            return None
        
        periods = periods or self.forecast_periods
        
        try:
            # 计算近期平均值
            last_values = time_series[-window:].values
            avg_value = np.mean(last_values)
            
            # 生成预测值(简单重复平均值)
            forecast_values = np.repeat(avg_value, periods)
            
            # 计算简单的置信区间
            std_value = np.std(last_values)
            lower_bound = forecast_values - 1.96 * std_value
            upper_bound = forecast_values + 1.96 * std_value
            
            # 创建预测结果DataFrame
            last_date = time_series.index[-1]
            forecast_dates = [last_date + i + 1 for i in range(periods)]
            
            forecast_df = pd.DataFrame({
                '预测值': forecast_values,
                '下限': lower_bound,
                '上限': upper_bound
            }, index=forecast_dates)
            
            logger.info(f"移动平均预测完成，预测 {periods} 期")
            return forecast_df
            
        except Exception as e:
            logger.error(f"移动平均预测失败: {str(e)}")
            return None
    
    def select_best_method(self, time_series, material_id):
        """
        为指定物料选择最佳预测方法
        
        参数:
            time_series: 时间序列数据
            material_id: 物料编号
            
        返回:
            str: 最佳预测方法名称
        """
        if time_series is None or len(time_series) < 12:
            logger.warning("历史数据不足12期，使用简单移动平均法")
            return "moving_average"
        
        try:
            # 进行训练集和测试集划分
            train_size = len(time_series) - 3  # 留出3期作为测试
            train, test = time_series[:train_size], time_series[train_size:]
            
            methods = {
                "arima": {"func": self.forecast_arima, "kwargs": {"order": (1,1,1)}},
                "exp_smoothing": {"func": self.forecast_exponential_smoothing, 
                               "kwargs": {"seasonal_periods": 12, "trend": 'add', "seasonal": 'mul'}},
                "moving_average": {"func": self.forecast_moving_average, "kwargs": {"window": 3}}
            }
            
            errors = {}
            
            # 测试各种方法
            for name, method in methods.items():
                try:
                    # 用训练集预测测试集区间
                    forecast = method["func"](train, periods=len(test), **method["kwargs"])
                    if forecast is not None:
                        # 计算平均绝对百分比误差(MAPE)
                        forecast_values = forecast['预测值'].values
                        actual_values = test.values
                        
                        # 防止除以零
                        valid_indices = actual_values != 0
                        if not any(valid_indices):
                            errors[name] = float('inf')
                            continue
                            
                        mape = np.mean(np.abs((actual_values[valid_indices] - 
                                             forecast_values[valid_indices]) / 
                                             actual_values[valid_indices])) * 100
                        errors[name] = mape
                except Exception as e:
                    logger.warning(f"测试 {name} 方法时出错: {str(e)}")
                    errors[name] = float('inf')
            
            # 选择误差最小的方法
            if errors:
                best_method = min(errors, key=errors.get)
                logger.info(f"物料 {material_id} 的最佳预测方法: {best_method}，MAPE: {errors[best_method]:.2f}%")
                
                # 保存准确率信息
                self.forecast_accuracy[material_id] = {
                    'method': best_method,
                    'mape': errors[best_method]
                }
                
                return best_method
            else:
                logger.warning("无法确定最佳方法，使用移动平均法")
                return "moving_average"
                
        except Exception as e:
            logger.error(f"选择最佳预测方法时出错: {str(e)}")
            return "moving_average"  # 默认方法
    
    def generate_forecast(self, material_id=None, periods=None, method=None):
        """
        生成预测
        
        参数:
            material_id: 物料编号，如果为None则预测所有物料
            periods: 预测期数，如果为None则使用默认值
            method: 指定预测方法，如果为None则自动选择
            
        返回:
            DataFrame: 预测结果
        """
        if self.historical_data is None:
            logger.error("未加载历史数据，无法预测")
            return None
        
        periods = periods or self.forecast_periods
        
        try:
            all_forecasts = []
            
            # 确定要预测的物料列表
            if material_id:
                materials = [material_id]
            else:
                materials = self.historical_data['物料编号'].unique()
            
            # 最后一个历史日期
            max_date = self.historical_data['日期'].max()
            forecast_start_date = pd.to_datetime(max_date) + pd.DateOffset(months=1)
            
            # 预测每个物料
            for mat_id in materials:
                # 准备时间序列
                ts = self.prepare_time_series(mat_id)
                
                if ts is None or len(ts) < 4:  # 至少需要4期数据
                    logger.warning(f"物料 {mat_id} 的历史数据不足，跳过预测")
                    continue
                
                # 选择预测方法
                if method:
                    chosen_method = method
                else:
                    chosen_method = self.select_best_method(ts, mat_id)
                
                # 根据选择的方法进行预测
                forecast_result = None
                
                if chosen_method == "arima":
                    forecast_result = self.forecast_arima(ts, periods)
                elif chosen_method == "exp_smoothing":
                    forecast_result = self.forecast_exponential_smoothing(ts, periods)
                else:  # 默认移动平均
                    forecast_result = self.forecast_moving_average(ts, periods)
                
                if forecast_result is not None:
                    # 添加物料信息
                    forecast_result['物料编号'] = mat_id
                    forecast_result['预测方法'] = chosen_method
                    
                    # 将索引转换为日期列
                    forecast_result.reset_index(inplace=True)
                    forecast_result.rename(columns={'index': '日期'}, inplace=True)
                    
                    # 提取年份和月份
                    forecast_result['年份'] = forecast_result['日期'].dt.year
                    forecast_result['月份'] = forecast_result['日期'].dt.month
                    
                    # 保存模型
                    self.forecast_models[mat_id] = chosen_method
                    
                    all_forecasts.append(forecast_result)
            
            # 合并所有预测结果
            if all_forecasts:
                final_forecast = pd.concat(all_forecasts, ignore_index=True)
                self.forecast_data = final_forecast
                
                logger.info(f"成功生成 {len(materials)} 种物料的预测，共 {len(final_forecast)} 行")
                return final_forecast
            else:
                logger.error("没有生成任何预测结果")
                return None
                
        except Exception as e:
            logger.error(f"生成预测失败: {str(e)}")
            return None
    
    def adjust_forecast(self, material_id, year, month, new_value):
        """
        手动调整预测值
        
        参数:
            material_id: 物料编号
            year: 年份
            month: 月份
            new_value: 新的预测值
            
        返回:
            bool: 是否成功调整
        """
        if self.forecast_data is None:
            logger.error("未生成预测，无法调整")
            return False
        
        try:
            # 定位需要调整的行
            mask = ((self.forecast_data['物料编号'] == material_id) & 
                  (self.forecast_data['年份'] == year) & 
                  (self.forecast_data['月份'] == month))
            
            if not any(mask):
                logger.error(f"未找到要调整的预测: 物料={material_id}, 年月={year}-{month}")
                return False
            
            # 调整预测值
            self.forecast_data.loc[mask, '预测值'] = new_value
            
            # 标记为手动调整
            self.forecast_data.loc[mask, '预测方法'] = '手动调整'
            
            logger.info(f"已手动调整预测值: 物料={material_id}, 年月={year}-{month}, 新值={new_value}")
            return True
            
        except Exception as e:
            logger.error(f"调整预测值失败: {str(e)}")
            return False
    
    def export_forecast(self, file_path):
        """
        导出预测结果
        
        参数:
            file_path: 导出文件路径
            
        返回:
            bool: 是否成功导出
        """
        if self.forecast_data is None:
            logger.error("没有预测结果可供导出")
            return False
        
        try:
            _, file_extension = os.path.splitext(file_path)
            
            if file_extension.lower() == '.csv':
                self.forecast_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_extension.lower() in ['.xls', '.xlsx']:
                self.forecast_data.to_excel(file_path, index=False)
            else:
                logger.error(f"不支持的导出文件类型: {file_extension}")
                return False
            
            logger.info(f"预测结果成功导出至 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出预测结果失败: {str(e)}")
            return False