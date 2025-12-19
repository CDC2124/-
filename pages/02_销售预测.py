import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys
from datetime import datetime
import io

# 添加路径以导入自定义模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.forecaster import Forecaster
from models.data_processor import DataProcessor

# 页面配置
st.set_page_config(
    page_title="销售预测 - 生产需求系统",
    page_icon="📈",
    layout="wide"
)

# 初始化会话状态
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = DataProcessor()

if 'forecaster' not in st.session_state:
    st.session_state.forecaster = Forecaster()

if 'monthly_data' not in st.session_state:
    st.session_state.monthly_data = None

if 'forecast_data' not in st.session_state:
    st.session_state.forecast_data = None

if 'forecast_charts' not in st.session_state:
    st.session_state.forecast_charts = {}

# 页面标题
st.title("销售预测")

# 页面描述
st.markdown("""
此页面基于历史出货数据生成销售预测，并提供可视化展示和交互式调整功能。

### 预测功能:
- 多种预测算法选择（ARIMA、指数平滑、移动平均等）
- 自动选择最佳预测方法
- 预测结果可视化
- 交互式预测值调整
- 预测结果导出
""")

# 创建标签页
tab1, tab2, tab3, tab4 = st.tabs(["数据准备", "预测生成", "预测调整", "导出预测"])

with tab1:
    st.subheader("数据准备")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 历史数据")
        
        # 显示数据上传按钮，如果数据尚未上传
        if 'monthly_data' not in st.session_state or st.session_state.monthly_data is None:
            st.info("请先在'数据上传与分析'页面上传并处理历史出货数据")
            
            if st.button("前往数据上传页面"):
                st.switch_page("pages/01_数据上传与分析.py")
        else:
            st.success(f"已加载月度历史数据，包含 {len(st.session_state.monthly_data)} 条记录")
            
            # 显示数据预览
            st.write("月度历史数据预览：")
            st.dataframe(st.session_state.monthly_data.head())
    
    with col2:
        st.write("### 预测参数")
        
        # 预测期数
        forecast_periods = st.slider(
            "预测期数（月）", 
            min_value=1, 
            max_value=24, 
            value=12,
            help="设置要预测的月份数量"
        )
        
        # 预测方法选择
        forecast_method = st.selectbox(
            "预测方法",
            [
                "自动选择最佳方法",
                "ARIMA",
                "指数平滑",
                "移动平均"
            ],
            index=0,
            help="选择预测算法，或让系统自动为每种产品选择最合适的方法"
        )
        
        # 将选择的预测方法转换为算法参数
        method_param = None
        if forecast_method != "自动选择最佳方法":
            method_dict = {
                "ARIMA": "arima",
                "指数平滑": "exp_smoothing",
                "移动平均": "moving_average"
            }
            method_param = method_dict.get(forecast_method)
        
        # 更新Forecaster参数
        st.session_state.forecaster.forecast_periods = forecast_periods

with tab2:
    st.subheader("预测生成")
    
    if 'monthly_data' not in st.session_state or st.session_state.monthly_data is None:
        st.info("请先在'数据准备'标签页加载历史数据")
    else:
        # 选择要预测的物料
        all_materials = sorted(st.session_state.monthly_data['物料编号'].unique())
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("### 选择物料")
            
            forecast_option = st.radio(
                "预测范围",
                ["预测所有物料", "选择特定物料"],
                index=0
            )
            
            selected_material = None
            if forecast_option == "选择特定物料":
                selected_material = st.selectbox("选择物料", all_materials)
        
        with col2:
            st.write("### 生成预测")
            
            if st.button("开始预测"):
                with st.spinner("正在生成预测，请稍候..."):
                    # 确保数据已加载
                    if st.session_state.forecaster.historical_data is None:
                        # 加载月度数据
                        st.session_state.forecaster.load_data(st.session_state.monthly_data)
                    
                    # 生成预测
                    forecast_result = st.session_state.forecaster.generate_forecast(
                        material_id=selected_material,
                        method=method_param
                    )
                    
                    if forecast_result is not None:
                        st.session_state.forecast_data = forecast_result
                        st.success(f"预测生成成功，共 {len(forecast_result)} 条预测")
                        
                        # 创建图表
                        st.session_state.forecast_charts = {}
                        
                        # 获取要可视化的物料列表
                        materials_to_plot = [selected_material] if selected_material else all_materials[:min(5, len(all_materials))]
                        
                        for material in materials_to_plot:
                            fig, ax = plt.subplots(figsize=(10, 6))
                            
                            # 筛选该物料的历史数据和预测数据
                            hist_data = st.session_state.monthly_data[
                                st.session_state.monthly_data['物料编号'] == material
                            ].sort_values(['年份', '月份'])
                            
                            fore_data = st.session_state.forecast_data[
                                st.session_state.forecast_data['物料编号'] == material
                            ].sort_values(['年份', '月份'])
                            
                            if hist_data.empty or fore_data.empty:
                                continue
                            
                            # 创建时间标签
                            hist_labels = [f"{year}-{month}" for year, month in zip(hist_data['年份'], hist_data['月份'])]
                            fore_labels = [f"{year}-{month}" for year, month in zip(fore_data['年份'], fore_data['月份'])]
                            
                            # 绘制历史数据
                            ax.plot(hist_labels, hist_data['批次数量'], marker='o', label='历史数据')
                            
                            # 绘制预测数据
                            ax.plot(fore_labels, fore_data['预测值'], marker='x', label='预测值')
                            
                            # 绘制置信区间
                            if '下限' in fore_data.columns and '上限' in fore_data.columns:
                                ax.fill_between(
                                    fore_labels, 
                                    fore_data['下限'], 
                                    fore_data['上限'], 
                                    alpha=0.2, 
                                    label='预测区间'
                                )
                            
                            # 添加图表标题和标签
                            ax.set_title(f"物料 {material} 销售预测")
                            ax.set_xlabel('年月')
                            ax.set_ylabel('数量')
                            ax.legend()
                            
                            # 旋转x轴标签
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            
                            # 保存图表
                            st.session_state.forecast_charts[material] = fig
                    else:
                        st.error("预测生成失败，请检查历史数据格式是否正确")
            
            # 显示图表
            if 'forecast_data' in st.session_state and st.session_state.forecast_data is not None:
                st.write("### 预测可视化")
                
                if st.session_state.forecast_charts:
                    # 选择要显示的物料图表
                    chart_materials = list(st.session_state.forecast_charts.keys())
                    
                    if chart_materials:
                        selected_chart = st.selectbox("选择物料查看预测", chart_materials)
                        
                        if selected_chart in st.session_state.forecast_charts:
                            st.pyplot(st.session_state.forecast_charts[selected_chart])
                
                # 显示预测结果数据表
                st.write("### 预测结果数据")
                
                # 如果选择了特定物料，只显示该物料的预测
                if selected_material:
                    filtered_forecast = st.session_state.forecast_data[
                        st.session_state.forecast_data['物料编号'] == selected_material
                    ]
                    st.dataframe(filtered_forecast)
                else:
                    # 添加过滤选项
                    forecast_filter = st.multiselect(
                        "选择物料筛选预测结果",
                        all_materials,
                        default=[]
                    )
                    
                    if forecast_filter:
                        filtered_forecast = st.session_state.forecast_data[
                            st.session_state.forecast_data['物料编号'].isin(forecast_filter)
                        ]
                        st.dataframe(filtered_forecast)
                    else:
                        # 显示所有预测结果，但限制行数
                        st.dataframe(st.session_state.forecast_data.head(100))
                        
                        if len(st.session_state.forecast_data) > 100:
                            st.info(f"仅显示前100行，共 {len(st.session_state.forecast_data)} 行数据")

with tab3:
    st.subheader("预测调整")
    
    if 'forecast_data' not in st.session_state or st.session_state.forecast_data is None:
        st.info("请先在'预测生成'标签页生成预测")
    else:
        st.write("在此页面可以手动调整预测值，以便根据业务知识和市场情况优化预测。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 选择要调整的预测")
            
            # 创建物料、年份和月份的选择器
            adj_materials = sorted(st.session_state.forecast_data['物料编号'].unique())
            adj_material = st.selectbox("选择物料", adj_materials, key="adj_material")
            
            # 筛选该物料的预测数据
            material_forecast = st.session_state.forecast_data[
                st.session_state.forecast_data['物料编号'] == adj_material
            ].sort_values(['年份', '月份'])
            
            # 创建年月选项
            adj_periods = [(row['年份'], row['月份']) for _, row in material_forecast.iterrows()]
            adj_period_labels = [f"{year}年{month}月" for year, month in adj_periods]
            
            selected_period_idx = st.selectbox(
                "选择年月", 
                range(len(adj_period_labels)),
                format_func=lambda i: adj_period_labels[i]
            )
            
            # 获取选择的年月
            adj_year, adj_month = adj_periods[selected_period_idx]
            
            # 获取当前预测值
            current_forecast = material_forecast[
                (material_forecast['年份'] == adj_year) & 
                (material_forecast['月份'] == adj_month)
            ]['预测值'].iloc[0]
            
            # 创建调整值输入框
            adj_value = st.number_input(
                "新预测值",
                min_value=0.0,
                value=float(current_forecast),
                step=10.0
            )
            
            # 添加调整按钮
            if st.button("应用调整"):
                with st.spinner("正在调整预测值..."):
                    # 调整预测值
                    success = st.session_state.forecaster.adjust_forecast(
                        adj_material, adj_year, adj_month, adj_value
                    )
                    
                    if success:
                        # 更新会话状态中的预测数据
                        st.session_state.forecast_data = st.session_state.forecaster.forecast_data
                        
                        # 更新图表
                        if adj_material in st.session_state.forecast_charts:
                            # 重新创建图表
                            fig, ax = plt.subplots(figsize=(10, 6))
                            
                            # 筛选该物料的历史数据和预测数据
                            hist_data = st.session_state.monthly_data[
                                st.session_state.monthly_data['物料编号'] == adj_material
                            ].sort_values(['年份', '月份'])
                            
                            fore_data = st.session_state.forecast_data[
                                st.session_state.forecast_data['物料编号'] == adj_material
                            ].sort_values(['年份', '月份'])
                            
                            # 创建时间标签
                            hist_labels = [f"{year}-{month}" for year, month in zip(hist_data['年份'], hist_data['月份'])]
                            fore_labels = [f"{year}-{month}" for year, month in zip(fore_data['年份'], fore_data['月份'])]
                            
                            # 绘制历史数据
                            ax.plot(hist_labels, hist_data['批次数量'], marker='o', label='历史数据')
                            
                            # 绘制预测数据
                            ax.plot(fore_labels, fore_data['预测值'], marker='x', label='预测值')
                            
                            # 绘制置信区间
                            if '下限' in fore_data.columns and '上限' in fore_data.columns:
                                ax.fill_between(
                                    fore_labels, 
                                    fore_data['下限'], 
                                    fore_data['上限'], 
                                    alpha=0.2, 
                                    label='预测区间'
                                )
                            
                            # 添加图表标题和标签
                            ax.set_title(f"物料 {adj_material} 销售预测 (含调整)")
                            ax.set_xlabel('年月')
                            ax.set_ylabel('数量')
                            ax.legend()
                            
                            # 旋转x轴标签
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            
                            # 更新图表
                            st.session_state.forecast_charts[adj_material] = fig
                        
                        st.success(f"成功调整 {adj_material} 在 {adj_year}年{adj_month}月 的预测值")
                    else:
                        st.error("调整预测值失败")
        
        with col2:
            st.write("### 调整后的预测")
            
            # 显示调整后的图表
            if adj_material in st.session_state.forecast_charts:
                st.pyplot(st.session_state.forecast_charts[adj_material])
            
            # 显示调整后的预测数据
            adj_forecast = st.session_state.forecast_data[
                st.session_state.forecast_data['物料编号'] == adj_material
            ].sort_values(['年份', '月份'])
            
            st.dataframe(adj_forecast)
            
            # 显示调整历史
            manual_adj = adj_forecast[adj_forecast['预测方法'] == '手动调整']
            
            if not manual_adj.empty:
                st.write("### 手动调整历史")
                st.dataframe(manual_adj)

with tab4:
    st.subheader("导出预测")
    
    if 'forecast_data' not in st.session_state or st.session_state.forecast_data is None:
        st.info("请先在'预测生成'标签页生成预测")
    else:
        st.write("在此页面可以导出预测结果，用于生产计划和MRP计算。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 导出格式选项")
            
            export_format = st.radio(
                "选择导出格式",
                ["Excel (.xlsx)", "CSV (.csv)"],
                index=0
            )
            
            include_bounds = st.checkbox("包含预测上下限", value=True)
            include_charts = st.checkbox("包含预测图表(仅Excel格式)", value=True)
        
        with col2:
            st.write("### 导出预测")
            
            if st.button("生成导出文件"):
                with st.spinner("正在准备导出文件，请稍候..."):
                    try:
                        # 准备导出数据
                        export_data = st.session_state.forecast_data.copy()
                        
                        # 如果不包含上下限，则去除相关列
                        if not include_bounds and '下限' in export_data.columns and '上限' in export_data.columns:
                            export_data = export_data.drop(columns=['下限', '上限'])
                        
                        # 确保导出目录存在
                        if not os.path.exists("data/exports"):
                            os.makedirs("data/exports", exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        
                        if export_format == "Excel (.xlsx)":
                            # 导出为Excel
                            file_path = f"data/exports/销售预测_{timestamp}.xlsx"
                            
                            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                                # 写入预测数据
                                export_data.to_excel(writer, sheet_name='预测数据', index=False)
                                
                                # 如果包含图表，为每个物料创建单独的sheet
                                if include_charts:
                                    # 使用pandas的ExcelWriter不能直接添加图表
                                    # 这里我们只能将不同物料的数据分到不同sheet中
                                    for material in export_data['物料编号'].unique():
                                        material_data = export_data[export_data['物料编号'] == material]
                                        material_data.to_excel(writer, sheet_name=f'物料_{material}', index=False)
                            
                            # 读取Excel文件内容
                            with open(file_path, "rb") as file:
                                excel_bytes = file.read()
                            
                            # 提供下载链接
                            st.download_button(
                                label="下载Excel预测文件",
                                data=excel_bytes,
                                file_name=f"销售预测_{timestamp}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            # 导出为CSV
                            file_path = f"data/exports/销售预测_{timestamp}.csv"
                            export_data.to_csv(file_path, index=False, encoding='utf-8-sig')
                            
                            # 读取CSV文件内容
                            with open(file_path, "rb") as file:
                                csv_bytes = file.read()
                            
                            # 提供下载链接
                            st.download_button(
                                label="下载CSV预测文件",
                                data=csv_bytes,
                                file_name=f"销售预测_{timestamp}.csv",
                                mime="text/csv"
                            )
                        
                        st.success("预测数据导出成功！")
                    except Exception as e:
                        st.error(f"导出预测数据失败: {str(e)}")
                        
            # 添加按钮前往生产计划页面
            st.write("### 下一步")
            if st.button("前往生产计划页面"):
                st.switch_page("pages/03_生产计划.py")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求系统 | 销售预测模块")