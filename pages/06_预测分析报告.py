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
from models.analysis_reporter import AnalysisReporter

# 页面配置
st.set_page_config(
    page_title="预测分析报告 - 生产需求系统",
    page_icon="📊",
    layout="wide"
)

# 初始化会话状态
if 'analysis_reporter' not in st.session_state:
    st.session_state.analysis_reporter = AnalysisReporter()

if 'data_processor' not in st.session_state:
    st.session_state.data_processor = DataProcessor()

if 'forecaster' not in st.session_state:
    st.session_state.forecaster = Forecaster()

if 'analysis_report' not in st.session_state:
    st.session_state.analysis_report = None

# 页面标题
st.title("预测需求与实际需求对比分析报告")

# 页面描述
st.markdown("""
此页面生成预测与实际销售数据的对比分析报告，帮助您了解预测准确性并持续改进预测模型。

### 报告内容:
1. 各产品SKU的预测量与实际销售量对比数据表
2. 预测准确率计算（按产品类别和整体进行统计）
3. 预测偏差分析，识别偏差最大的产品及可能原因
4. 关键产品的预测vs实际需求趋势图
5. 基于历史偏差模式的预测模型调整建议
6. 下月需求预测的置信区间

报告可以导出为Excel和PDF格式，方便存档和分享。
""")

# 创建标签页
tab1, tab2, tab3, tab4 = st.tabs(["报告生成", "对比数据", "图表与分析", "导出报告"])

with tab1:
    st.subheader("生成分析报告")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 上传预测数据")
        forecast_file = st.file_uploader("选择预测数据文件", type=['csv', 'xlsx', 'xls'])
        
        if forecast_file is not None:
            try:
                if forecast_file.name.endswith('.csv'):
                    forecast_data = pd.read_csv(forecast_file)
                else:
                    forecast_data = pd.read_excel(forecast_file)
                
                st.success(f"预测数据上传成功，包含 {len(forecast_data)} 行记录")
                
                # 预览数据
                st.write("预测数据预览：")
                st.dataframe(forecast_data.head())
                
                # 保存到会话状态
                if st.session_state.analysis_reporter.load_forecast_data(forecast_data):
                    st.session_state.forecast_data = forecast_data
            except Exception as e:
                st.error(f"处理预测数据文件时出错: {str(e)}")
    
    with col2:
        st.write("### 上传实际销售数据")
        actual_file = st.file_uploader("选择实际销售数据文件", type=['csv', 'xlsx', 'xls'])
        
        if actual_file is not None:
            try:
                if actual_file.name.endswith('.csv'):
                    actual_data = pd.read_csv(actual_file)
                else:
                    actual_data = pd.read_excel(actual_file)
                
                st.success(f"实际销售数据上传成功，包含 {len(actual_data)} 行记录")
                
                # 预览数据
                st.write("实际销售数据预览：")
                st.dataframe(actual_data.head())
                
                # 保存到会话状态
                if st.session_state.analysis_reporter.load_actual_data(actual_data):
                    st.session_state.actual_data = actual_data
            except Exception as e:
                st.error(f"处理实际销售数据文件时出错: {str(e)}")
    
    # 可选：产品类别数据上传
    st.write("### 产品类别数据（可选）")
    category_file = st.file_uploader("选择产品类别映射文件（可选）", type=['csv', 'xlsx', 'xls'])
    
    if category_file is not None:
        try:
            if category_file.name.endswith('.csv'):
                category_data = pd.read_csv(category_file)
            else:
                category_data = pd.read_excel(category_file)
            
            st.success(f"产品类别数据上传成功，包含 {len(category_data)} 个产品")
            
            # 预览数据
            st.write("产品类别数据预览：")
            st.dataframe(category_data.head())
            
            # 保存到会话状态
            st.session_state.analysis_reporter.load_product_categories(category_data)
        except Exception as e:
            st.error(f"处理产品类别文件时出错: {str(e)}")
    
    # 报告期选择
    st.write("### 报告期设置")
    
    # 根据已上传数据自动获取可选的年份和月份
    available_periods = []
    if hasattr(st.session_state, 'forecast_data') and hasattr(st.session_state, 'actual_data'):
        # 合并两个数据集的年月信息
        if '年份' in st.session_state.forecast_data.columns and '月份' in st.session_state.forecast_data.columns:
            forecast_periods = set(zip(st.session_state.forecast_data['年份'], st.session_state.forecast_data['月份']))
            
            if '年份' in st.session_state.actual_data.columns and '月份' in st.session_state.actual_data.columns:
                actual_periods = set(zip(st.session_state.actual_data['年份'], st.session_state.actual_data['月份']))
                
                # 获取交集
                available_periods = sorted(list(forecast_periods.intersection(actual_periods)))
    
    if available_periods:
        # 默认选择最新的期间
        default_idx = len(available_periods) - 1
        selected_period = st.selectbox(
            "选择报告期（年月）", 
            [f"{year}年{month}月" for year, month in available_periods],
            index=default_idx
        )
        
        # 解析选择的年月
        selected_year = int(selected_period.split('年')[0])
        selected_month = int(selected_period.split('年')[1].split('月')[0])
        
        report_period = (selected_year, selected_month)
    else:
        st.warning("未找到匹配的报告期。请确保预测数据和实际数据包含相同的年月期间。")
        report_period = None
    
    # 关键产品选择
    st.write("### 关键产品设置")
    
    # 获取所有产品
    all_materials = []
    if hasattr(st.session_state, 'actual_data') and '物料编号' in st.session_state.actual_data.columns:
        all_materials = sorted(st.session_state.actual_data['物料编号'].unique())
    
    if all_materials:
        # 设置默认选择前5个产品
        default_selections = all_materials[:min(5, len(all_materials))]
        
        key_materials = st.multiselect(
            "选择要重点分析的关键产品",
            all_materials,
            default=default_selections
        )
    else:
        key_materials = None
        st.info("上传数据后可选择关键产品进行详细分析")
    
    # 生成报告按钮
    if st.button("生成分析报告", key="generate_report"):
        if not hasattr(st.session_state, 'forecast_data'):
            st.error("请先上传预测数据")
        elif not hasattr(st.session_state, 'actual_data'):
            st.error("请先上传实际销售数据")
        elif report_period is None:
            st.error("未找到有效的报告期")
        else:
            with st.spinner("正在生成分析报告，请稍候..."):
                # 生成报告
                report = st.session_state.analysis_reporter.generate_analysis_report(
                    report_period=report_period,
                    key_materials=key_materials
                )
                
                if report is not None:
                    st.session_state.analysis_report = report
                    st.success(f"成功生成 {report_period[0]}年{report_period[1]}月 的预测分析报告")
                    
                    # 计算总体准确率
                    overall_acc = report['overall_accuracy']
                    current_acc = overall_acc[
                        (overall_acc['年份'] == report_period[0]) & 
                        (overall_acc['月份'] == report_period[1])
                    ]
                    
                    if not current_acc.empty:
                        acc_value = current_acc['预测准确率'].iloc[0]
                        st.metric("本月整体预测准确率", f"{acc_value:.2f}%")
                else:
                    st.error("生成报告失败，请检查数据格式是否正确")

with tab2:
    st.subheader("预测与实际数据对比")
    
    if st.session_state.analysis_report is not None:
        # 显示对比数据
        st.write("### 预测vs实际对比详情")
        
        comparison_data = st.session_state.analysis_report['comparison_data']
        
        # 添加数据筛选功能
        st.write("#### 数据筛选")
        col1, col2 = st.columns(2)
        
        with col1:
            # 按产品类别筛选
            categories = ['全部'] + sorted(comparison_data['产品类别'].unique().tolist())
            selected_category = st.selectbox("选择产品类别", categories)
        
        with col2:
            # 按偏差方向筛选
            bias_directions = ['全部', '预测过高', '预测过低', '无偏差']
            selected_direction = st.selectbox("选择偏差方向", bias_directions)
        
        # 应用筛选条件
        filtered_data = comparison_data.copy()
        
        if selected_category != '全部':
            filtered_data = filtered_data[filtered_data['产品类别'] == selected_category]
            
        if selected_direction != '全部':
            filtered_data = filtered_data[filtered_data['偏差方向'] == selected_direction]
        
        # 显示筛选结果
        st.write(f"符合条件的记录数: {len(filtered_data)}")
        st.dataframe(filtered_data)
        
        # 显示按类别和偏差方向的统计汇总
        st.write("### 统计汇总")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### 按产品类别汇总")
            category_summary = comparison_data.groupby('产品类别').agg({
                '预测值': 'sum',
                '实际值': 'sum',
                '预测准确率': 'mean',
                '物料编号': 'count'
            }).reset_index()
            
            category_summary.rename(columns={'物料编号': '产品数量'}, inplace=True)
            st.dataframe(category_summary)
        
        with col2:
            st.write("#### 按偏差方向汇总")
            direction_summary = comparison_data.groupby('偏差方向').agg({
                '物料编号': 'count',
                '相对偏差': 'mean'
            }).reset_index()
            
            direction_summary.rename(columns={
                '物料编号': '产品数量',
                '相对偏差': '平均相对偏差(%)'
            }, inplace=True)
            st.dataframe(direction_summary)
    else:
        st.info("请先在'报告生成'标签页上传数据并生成分析报告")

with tab3:
    st.subheader("图表和分析结果")
    
    if st.session_state.analysis_report is not None:
        report = st.session_state.analysis_report
        
        st.write("### 预测准确率趋势")
        
        if 'accuracy' in report['trend_charts']:
            st.pyplot(report['trend_charts']['accuracy'])
        
        st.write("### 预测vs实际总体趋势")
        
        if 'overall' in report['trend_charts']:
            st.pyplot(report['trend_charts']['overall'])
        
        st.write("### 关键产品趋势")
        
        # 展示单个产品趋势图
        product_charts = {k: v for k, v in report['trend_charts'].items() 
                         if k not in ['overall', 'accuracy']}
        
        if product_charts:
            selected_product = st.selectbox(
                "选择产品查看趋势",
                list(product_charts.keys())
            )
            
            st.pyplot(product_charts[selected_product])
        
        # 显示预测偏差分析
        st.write("### 预测偏差分析")
        
        if report['bias_analysis'] is not None:
            st.dataframe(report['bias_analysis'])
        
        # 显示预测模型调整建议
        st.write("### 预测模型调整建议")
        
        if report['model_recommendations'] is not None:
            st.dataframe(report['model_recommendations'])
        
        # 显示下月预测置信区间
        st.write("### 下月预测置信区间")
        
        if report['confidence_intervals'] is not None:
            st.dataframe(report['confidence_intervals'])
    else:
        st.info("请先在'报告生成'标签页上传数据并生成分析报告")

with tab4:
    st.subheader("导出报告")
    
    if st.session_state.analysis_report is not None:
        report = st.session_state.analysis_report
        report_year, report_month = report['report_period']
        
        st.write(f"### 导出 {report_year}年{report_month}月 预测分析报告")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### 导出为Excel")
            
            # 创建下载按钮
            if st.button("生成Excel报告"):
                with st.spinner("正在生成Excel报告，请稍候..."):
                    # 创建一个临时文件路径保存Excel
                    if not os.path.exists("data/reports"):
                        os.makedirs("data/reports", exist_ok=True)
                        
                    excel_path = f"data/reports/预测分析报告_{report_year}年{report_month}月_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
                    
                    # 导出Excel
                    if st.session_state.analysis_reporter.export_excel_report(excel_path):
                        # 读取Excel文件内容
                        with open(excel_path, "rb") as file:
                            excel_bytes = file.read()
                        
                        # 提供下载链接
                        st.download_button(
                            label="点击下载Excel报告",
                            data=excel_bytes,
                            file_name=f"预测分析报告_{report_year}年{report_month}月.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                        st.success("Excel报告生成成功！")
                    else:
                        st.error("Excel报告生成失败")
        
        with col2:
            st.write("#### 导出为PDF")
            
            # 创建下载按钮
            if st.button("生成PDF报告"):
                with st.spinner("正在生成PDF报告，请稍候..."):
                    # 创建一个临时文件路径保存PDF
                    if not os.path.exists("data/reports"):
                        os.makedirs("data/reports", exist_ok=True)
                        
                    pdf_path = f"data/reports/预测分析报告_{report_year}年{report_month}月_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                    
                    # 导出PDF
                    if st.session_state.analysis_reporter.export_pdf_report(pdf_path):
                        # 读取PDF文件内容
                        with open(pdf_path, "rb") as file:
                            pdf_bytes = file.read()
                        
                        # 提供下载链接
                        st.download_button(
                            label="点击下载PDF报告",
                            data=pdf_bytes,
                            file_name=f"预测分析报告_{report_year}年{report_month}月.pdf",
                            mime="application/pdf"
                        )
                        
                        st.success("PDF报告生成成功！")
                    else:
                        st.error("PDF报告生成失败")
    else:
        st.info("请先在'报告生成'标签页上传数据并生成分析报告")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求系统 | 预测分析报告模块")