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
from models.production_planner import ProductionPlanner

# 页面配置
st.set_page_config(
    page_title="生产计划 - 生产需求系统",
    page_icon="🏭",
    layout="wide"
)

# 初始化会话状态
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = DataProcessor()

if 'forecaster' not in st.session_state:
    st.session_state.forecaster = Forecaster()

if 'production_planner' not in st.session_state:
    st.session_state.production_planner = ProductionPlanner()

if 'forecast_data' not in st.session_state:
    st.session_state.forecast_data = None

if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = None

if 'capacity_data' not in st.session_state:
    st.session_state.capacity_data = None

if 'production_plan' not in st.session_state:
    st.session_state.production_plan = None

if 'production_charts' not in st.session_state:
    st.session_state.production_charts = {}

if 'sales_orders' not in st.session_state:
    st.session_state.sales_orders = None

# 页面标题
st.title("生产计划")

# 页面描述
st.markdown("""
此页面基于销售预测或销售订单生成优化的生产计划，并提供可视化展示和交互式调整功能。

### 生产计划功能:
- 基于OR-Tools的生产计划优化
- 多种优化目标选择（成本最小化、生产平滑、库存优化）
- 考虑产能约束、安全库存、最小批量等
- 支持销售订单调整
- 交互式计划调整
- 计划可视化和导出
""")

# 创建标签页
tab1, tab2, tab3, tab4, tab5 = st.tabs(["数据准备", "约束设置", "计划生成", "计划调整", "导出计划"])

with tab1:
    st.subheader("数据准备")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 销售预测/订单数据")
        
        forecast_source = st.radio(
            "数据来源",
            ["使用销售预测", "使用销售订单", "手动输入"],
            index=0
        )
        
        if forecast_source == "使用销售预测":
            # 尝试从会话状态中获取预测数据
            if 'forecast_data' in st.session_state and st.session_state.forecast_data is not None:
                st.success(f"已加载预测数据，包含 {len(st.session_state.forecast_data)} 条记录")
                
                # 显示数据预览
                st.write("预测数据预览：")
                st.dataframe(st.session_state.forecast_data.head())
            else:
                st.info("请先在'销售预测'页面生成预测数据")
                
                if st.button("前往销售预测页面"):
                    st.switch_page("pages/02_销售预测.py")
        
        elif forecast_source == "使用销售订单":
            # 检查是否已加载销售订单
            if 'sales_orders' in st.session_state and st.session_state.sales_orders is not None:
                st.success(f"已加载销售订单，包含 {len(st.session_state.sales_orders)} 条记录")
                
                # 显示数据预览
                st.write("销售订单预览：")
                st.dataframe(st.session_state.sales_orders.head())
            else:
                # 提供上传销售订单功能
                st.write("请上传销售订单数据")
                
                order_file = st.file_uploader("选择销售订单文件", type=['csv', 'xlsx', 'xls'])
                
                if order_file is not None:
                    try:
                        if order_file.name.endswith('.csv'):
                            orders_data = pd.read_csv(order_file)
                        else:
                            orders_data = pd.read_excel(order_file)
                        
                        st.success(f"销售订单上传成功，包含 {len(orders_data)} 条记录")
                        
                        # 显示数据预览
                        st.write("销售订单预览：")
                        st.dataframe(orders_data.head())
                        
                        # 检查必要字段
                        required_fields = ['物料编号', '订单数量', '要求交期']
                        missing_fields = [field for field in required_fields if field not in orders_data.columns]
                        
                        if missing_fields:
                            st.error(f"订单数据缺少必要字段: {', '.join(missing_fields)}")
                        else:
                            # 处理日期格式
                            if isinstance(orders_data['要求交期'].iloc[0], str):
                                orders_data['要求交期'] = pd.to_datetime(orders_data['要求交期'])
                            
                            # 添加年月字段
                            orders_data['年份'] = orders_data['要求交期'].dt.year
                            orders_data['月份'] = orders_data['要求交期'].dt.month
                            
                            # 按物料和年月汇总订单
                            order_summary = orders_data.groupby(['物料编号', '年份', '月份'])['订单数量'].sum().reset_index()
                            
                            # 重命名列以与预测数据格式兼容
                            order_summary = order_summary.rename(columns={'订单数量': '预测值'})
                            
                            # 保存到会话状态
                            st.session_state.forecast_data = order_summary
                            st.session_state.sales_orders = orders_data
                            
                            st.info("销售订单已处理为生产计划可用格式")
                    except Exception as e:
                        st.error(f"处理订单文件时出错: {str(e)}")
        
        else:  # 手动输入
            st.write("请手动输入计划数据")
            
            # 创建输入表单
            with st.form("manual_plan_form"):
                # 获取物料编号
                material_id = st.text_input("物料编号")
                
                # 获取预测期间和数量
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    year = st.number_input("年份", min_value=2020, max_value=2030, value=datetime.now().year)
                
                with col2:
                    month = st.number_input("月份", min_value=1, max_value=12, value=datetime.now().month)
                
                with col3:
                    quantity = st.number_input("数量", min_value=0, value=100)
                
                # 提交按钮
                submitted = st.form_submit_button("添加数据")
                
                if submitted:
                    # 创建预测数据
                    if 'manual_forecast' not in st.session_state:
                        st.session_state.manual_forecast = pd.DataFrame(columns=['物料编号', '年份', '月份', '预测值'])
                    
                    # 添加新行
                    new_row = pd.DataFrame({
                        '物料编号': [material_id],
                        '年份': [year],
                        '月份': [month],
                        '预测值': [quantity]
                    })
                    
                    # 合并数据
                    st.session_state.manual_forecast = pd.concat([st.session_state.manual_forecast, new_row], ignore_index=True)
                    
                    # 更新预测数据
                    st.session_state.forecast_data = st.session_state.manual_forecast
            
            # 显示手动输入的数据
            if 'manual_forecast' in st.session_state and not st.session_state.manual_forecast.empty:
                st.write("已输入的数据：")
                st.dataframe(st.session_state.manual_forecast)
                
                # 添加清除按钮
                if st.button("清除所有手动输入的数据"):
                    st.session_state.manual_forecast = pd.DataFrame(columns=['物料编号', '年份', '月份', '预测值'])
                    st.session_state.forecast_data = None
    
    with col2:
        st.write("### 库存与产能数据")
        
        # 切换到标签页
        inventory_tab, capacity_tab = st.tabs(["库存数据", "产能数据"])
        
        with inventory_tab:
            inventory_source = st.radio(
                "库存数据来源",
                ["上传库存文件", "手动输入"],
                index=0
            )
            
            if inventory_source == "上传库存文件":
                inventory_file = st.file_uploader("选择库存数据文件", type=['csv', 'xlsx', 'xls'])
                
                if inventory_file is not None:
                    try:
                        if inventory_file.name.endswith('.csv'):
                            inventory_data = pd.read_csv(inventory_file)
                        else:
                            inventory_data = pd.read_excel(inventory_file)
                        
                        st.success(f"库存数据上传成功，包含 {len(inventory_data)} 条记录")
                        
                        # 显示数据预览
                        st.write("库存数据预览：")
                        st.dataframe(inventory_data.head())
                        
                        # 检查必要字段
                        required_fields = ['物料编号', '库存数量']
                        missing_fields = [field for field in required_fields if field not in inventory_data.columns]
                        
                        if missing_fields:
                            st.error(f"库存数据缺少必要字段: {', '.join(missing_fields)}")
                        else:
                            # 保存到会话状态
                            st.session_state.inventory_data = inventory_data
                    except Exception as e:
                        st.error(f"处理库存文件时出错: {str(e)}")
            else:
                st.write("请手动输入库存数据")
                
                # 只有在有预测数据时才允许手动输入库存
                if 'forecast_data' in st.session_state and st.session_state.forecast_data is not None:
                    # 获取所有物料编号
                    materials = st.session_state.forecast_data['物料编号'].unique()
                    
                    # 创建一个DataFrame用于编辑
                    if 'manual_inventory' not in st.session_state:
                        # 初始化为所有物料的库存为0
                        st.session_state.manual_inventory = pd.DataFrame({
                            '物料编号': materials,
                            '库存数量': np.zeros(len(materials))
                        })
                    
                    # 显示编辑表
                    edited_df = st.data_editor(
                        st.session_state.manual_inventory,
                        num_rows="fixed",
                        key="inventory_editor"
                    )
                    
                    # 当用户编辑表格时更新会话状态
                    if st.button("更新库存数据"):
                        st.session_state.manual_inventory = edited_df
                        st.session_state.inventory_data = edited_df
                        st.success("库存数据已更新")
                else:
                    st.info("请先加载预测数据，才能手动输入库存")
        
        with capacity_tab:
            capacity_source = st.radio(
                "产能数据来源",
                ["上传产能文件", "手动设置"],
                index=1
            )
            
            if capacity_source == "上传产能文件":
                capacity_file = st.file_uploader("选择产能数据文件", type=['csv', 'xlsx', 'xls'])
                
                if capacity_file is not None:
                    try:
                        if capacity_file.name.endswith('.csv'):
                            capacity_data = pd.read_csv(capacity_file)
                        else:
                            capacity_data = pd.read_excel(capacity_file)
                        
                        st.success(f"产能数据上传成功，包含 {len(capacity_data)} 条记录")
                        
                        # 显示数据预览
                        st.write("产能数据预览：")
                        st.dataframe(capacity_data.head())
                        
                        # 检查必要字段
                        required_fields = ['年份', '月份', '产线', '最大产能']
                        missing_fields = [field for field in required_fields if field not in capacity_data.columns]
                        
                        if missing_fields:
                            st.error(f"产能数据缺少必要字段: {', '.join(missing_fields)}")
                        else:
                            # 保存到会话状态
                            st.session_state.capacity_data = capacity_data
                    except Exception as e:
                        st.error(f"处理产能文件时出错: {str(e)}")
            else:
                st.write("请设置全局产能约束")
                
                # 简化的产能设置，使用单一产能值
                global_capacity = st.number_input(
                    "全局月产能上限",
                    min_value=0,
                    value=10000,
                    help="设置所有产品所有月份的总产能上限"
                )
                
                if st.button("应用产能设置"):
                    # 如果有预测数据，创建对应的产能数据
                    if 'forecast_data' in st.session_state and st.session_state.forecast_data is not None:
                        # 获取所有年月组合
                        periods = st.session_state.forecast_data[['年份', '月份']].drop_duplicates()
                        
                        # 创建产能数据
                        capacity_data = []
                        
                        for _, row in periods.iterrows():
                            capacity_data.append({
                                '年份': row['年份'],
                                '月份': row['月份'],
                                '产线': 'ALL',  # 使用单一产线代表所有
                                '最大产能': global_capacity
                            })
                        
                        # 转换为DataFrame
                        capacity_df = pd.DataFrame(capacity_data)
                        
                        # 保存到会话状态
                        st.session_state.capacity_data = capacity_df
                        st.success("产能设置已应用")
                    else:
                        st.error("请先加载预测数据，才能设置产能")

with tab2:
    st.subheader("生产约束设置")
    
    # 检查是否已加载预测数据
    if 'forecast_data' not in st.session_state or st.session_state.forecast_data is None:
        st.info("请先在'数据准备'标签页加载预测或订单数据")
    else:
        st.write("在此设置生产计划的约束参数和优化目标")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 库存约束")
            
            safety_stock_days = st.slider(
                "安全库存天数",
                min_value=0,
                max_value=60,
                value=15,
                help="设置安全库存水平（以天为单位）"
            )
            
            max_inventory_days = st.slider(
                "最大库存天数",
                min_value=safety_stock_days,
                max_value=120,
                value=60,
                help="设置最大允许库存水平（以天为单位）"
            )
            
            min_service_level = st.slider(
                "最小服务水平",
                min_value=0.5,
                max_value=1.0,
                value=0.95,
                help="设置最小服务水平（满足需求的概率）"
            )
        
        with col2:
            st.write("### 生产约束")
            
            min_batch_size = st.number_input(
                "最小生产批量",
                min_value=1,
                value=100,
                help="设置最小生产批量"
            )
            
            production_smoothing = st.slider(
                "生产平滑系数",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                help="设置生产平滑系数（0-1，越大波动越小）"
            )
            
            optimization_horizon = st.slider(
                "优化期数",
                min_value=1,
                max_value=24,
                value=6,
                help="设置生产计划的优化期数（月）"
            )
        
        st.write("### 优化目标")
        
        optimization_objective = st.radio(
            "选择优化目标",
            ["最小化成本", "最大化生产平滑", "最小化库存"],
            index=0,
            help="选择生产计划的主要优化目标"
        )
        
        # 将优化目标转换为算法参数
        objective_param = {
            "最小化成本": "min_cost",
            "最大化生产平滑": "smooth_production",
            "最小化库存": "min_inventory"
        }.get(optimization_objective)
        
        # 汇总所有约束参数
        constraints = {
            'min_service_level': min_service_level,
            'min_batch_size': min_batch_size,
            'safety_stock_days': safety_stock_days,
            'max_inventory_days': max_inventory_days,
            'production_smoothing': production_smoothing
        }
        
        # 应用约束按钮
        if st.button("应用约束设置"):
            # 保存约束参数到会话状态
            st.session_state.production_constraints = constraints
            st.session_state.optimization_objective = objective_param
            st.session_state.optimization_horizon = optimization_horizon
            
            # 设置生产计划器的约束
            if st.session_state.production_planner.set_production_constraints(constraints):
                st.success("生产约束设置已应用")
            else:
                st.error("应用生产约束失败")

with tab3:
    st.subheader("生产计划生成")
    
    # 检查是否已加载预测数据
    if 'forecast_data' not in st.session_state or st.session_state.forecast_data is None:
        st.info("请先在'数据准备'标签页加载预测或订单数据")
    elif 'production_constraints' not in st.session_state:
        st.info("请先在'约束设置'标签页设置生产约束")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("### 生成计划")
            
            # 添加生成计划按钮
            if st.button("​生成优化生产计划​"):
                with st.spinner("正在优化生产计划，请稍候..."):
                    try:
                        # 加载预测数据到生产计划器
                        if st.session_state.production_planner.load_forecast_data(st.session_state.forecast_data):
                            # 加载库存数据（如果有）
                            if 'inventory_data' in st.session_state and st.session_state.inventory_data is not None:
                                st.session_state.production_planner.load_inventory_data(st.session_state.inventory_data)
                            
                            # 加载产能数据（如果有）
                            if 'capacity_data' in st.session_state and st.session_state.capacity_data is not None:
                                st.session_state.production_planner.load_capacity_data(st.session_state.capacity_data)
                            
                            # 生成优化生产计划
                            plan = st.session_state.production_planner.optimize_production_plan(
                                horizon=st.session_state.optimization_horizon,
                                objective=st.session_state.optimization_objective
                            )
                            
                            if plan is not None:
                                st.session_state.production_plan = plan
                                st.success(f"生产计划生成成功，共 {len(plan)} 条记录")
                                
                                # 创建图表
                                st.session_state.production_charts = {}
                                
                                # 取所有物料的前5个进行可视化
                                materials_to_plot = st.session_state.production_plan['物料编号'].unique()[:min(5, len(st.session_state.production_plan['物料编号'].unique()))]
                                
                                for material in materials_to_plot:
                                    fig, ax = plt.subplots(figsize=(10, 6))
                                    
                                    # 筛选该物料的计划数据
                                    material_plan = st.session_state.production_plan[
                                        st.session_state.production_plan['物料编号'] == material
                                    ].sort_values(['年份', '月份'])
                                    
                                    # 创建时间标签
                                    date_labels = [f"{year}-{month}" for year, month in zip(material_plan['年份'], material_plan['月份'])]
                                    
                                    # 绘制生产计划、预测需求和库存
                                    ax.bar(date_labels, material_plan['计划产量'], alpha=0.7, label='计划产量')
                                    ax.plot(date_labels, material_plan['预测需求'], marker='o', color='red', label='预测需求')
                                    ax.plot(date_labels, material_plan['期末库存'], marker='s', color='green', label='期末库存')
                                    
                                    # 添加图表标题和标签
                                    ax.set_title(f"物料 {material} 生产计划")
                                    ax.set_xlabel('年月')
                                    ax.set_ylabel('数量')
                                    ax.legend()
                                    
                                    # 旋转x轴标签
                                    plt.xticks(rotation=45)
                                    plt.tight_layout()
                                    
                                    # 保存图表
                                    st.session_state.production_charts[material] = fig
                                
                                # 创建整体生产负载图
                                fig, ax = plt.subplots(figsize=(10, 6))
                                
                                # 按月份汇总生产量
                                total_production = st.session_state.production_plan.groupby(['年份', '月份'])['计划产量'].sum().reset_index()
                                total_demand = st.session_state.production_plan.groupby(['年份', '月份'])['预测需求'].sum().reset_index()
                                
                                # 创建时间标签
                                date_labels = [f"{year}-{month}" for year, month in zip(total_production['年份'], total_production['月份'])]
                                
                                # 绘制总生产量和总需求
                                ax.bar(date_labels, total_production['计划产量'], alpha=0.7, label='总计划产量')
                                ax.plot(date_labels, total_demand['预测需求'], marker='o', color='red', label='总预测需求')

                                # 如果有产能数据，显示产能上限
                                if 'capacity_data' in st.session_state and st.session_state.capacity_data is not None:
                                    # 尝试获取每月的产能上限
                                    capacity_by_month = {}
                                    for _, row in st.session_state.capacity_data.iterrows():
                                        key = (row['年份'], row['月份'])
                                        if key not in capacity_by_month:
                                            capacity_by_month[key] = 0
                                        capacity_by_month[key] += row['最大产能']
                                    
                                    # 添加产能线
                                    capacity_values = []
                                    for year, month in zip(total_production['年份'], total_production['月份']):
                                        capacity_values.append(capacity_by_month.get((year, month), 0))
                                    
                                    ax.plot(date_labels, capacity_values, linestyle='--', color='black', label='产能上限')
                                
                                # 添加图表标题和标签
                                ax.set_title("总体生产计划")
                                ax.set_xlabel('年月')
                                ax.set_ylabel('数量')
                                ax.legend()
                                
                                # 旋转x轴标签
                                plt.xticks(rotation=45)
                                plt.tight_layout()
                                
                                # 保存图表
                                st.session_state.production_charts['total'] = fig
                            else:
                                st.error("生产计划生成失败，请检查数据和约束设置")
                        else:
                            st.error("加载预测数据失败")
                    except Exception as e:
                        st.error(f"生成生产计划时出错: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
        
        with col2:
            st.write("### 计划可视化")
            
            # 显示生产计划图表
            if 'production_charts' in st.session_state and st.session_state.production_charts:
                # 选择要显示的图表
                chart_options = list(st.session_state.production_charts.keys())
                selected_chart = st.selectbox("选择图表", chart_options, index=0 if 'total' not in chart_options else chart_options.index('total'))
                
                # 显示选中的图表
                if selected_chart in st.session_state.production_charts:
                    st.pyplot(st.session_state.production_charts[selected_chart])
            
            # 显示生产计划数据表
            if 'production_plan' in st.session_state and st.session_state.production_plan is not None:
                st.write("### 生产计划数据")
                
                # 添加过滤选项
                plan_filter = st.multiselect(
                    "选择物料筛选计划",
                    st.session_state.production_plan['物料编号'].unique(),
                    default=[]
                )
                
                if plan_filter:
                    filtered_plan = st.session_state.production_plan[
                        st.session_state.production_plan['物料编号'].isin(plan_filter)
                    ]
                    st.dataframe(filtered_plan)
                else:
                    st.dataframe(st.session_state.production_plan)

with tab4:
    st.subheader("生产计划调整")
    
    # 检查是否已生成生产计划
    if 'production_plan' not in st.session_state or st.session_state.production_plan is None:
        st.info("请先在'生产计划生成'标签页生成计划")
    else:
        st.write("在此可以手动调整生产计划，调整后系统会自动重新计算库存")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 选择要调整的计划")
            
            # 创建物料、年份和月份的选择器
            adj_materials = sorted(st.session_state.production_plan['物料编号'].unique())
            adj_material = st.selectbox("选择物料", adj_materials, key="adj_plan_material")
            
            # 筛选该物料的计划数据
            material_plan = st.session_state.production_plan[
                st.session_state.production_plan['物料编号'] == adj_material
            ].sort_values(['年份', '月份'])
            
            # 创建年月选项
            adj_periods = [(row['年份'], row['月份']) for _, row in material_plan.iterrows()]
            adj_period_labels = [f"{year}年{month}月" for year, month in adj_periods]
            
            selected_period_idx = st.selectbox(
                "选择年月", 
                range(len(adj_period_labels)),
                format_func=lambda i: adj_period_labels[i],
                key="adj_plan_period"
            )
            
            # 获取选择的年月
            adj_year, adj_month = adj_periods[selected_period_idx]
            
            # 获取当前计划产量
            current_production = material_plan[
                (material_plan['年份'] == adj_year) & 
                (material_plan['月份'] == adj_month)
            ]['计划产量'].iloc[0]
            
            # 创建调整值输入框
            adj_production = st.number_input(
                "新计划产量",
                min_value=0,
                value=int(current_production),
                step=10
            )
            
            # 添加调整按钮
            if st.button("应用调整"):
                with st.spinner("正在调整计划..."):
                    try:
                        # 调整生产计划
                        success = st.session_state.production_planner.adjust_production_plan(
                            adj_material, adj_year, adj_month, adj_production
                        )
                        
                        if success:
                            # 更新会话状态中的生产计划
                            st.session_state.production_plan = st.session_state.production_planner.production_plan
                            
                            # 更新图表
                            if adj_material in st.session_state.production_charts:
                                # 重新创建图表
                                fig, ax = plt.subplots(figsize=(10, 6))
                                
                                # 筛选该物料的计划数据
                                updated_plan = st.session_state.production_plan[
                                    st.session_state.production_plan['物料编号'] == adj_material
                                ].sort_values(['年份', '月份'])
                                
                                # 创建时间标签
                                date_labels = [f"{year}-{month}" for year, month in zip(updated_plan['年份'], updated_plan['月份'])]
                                
                                # 绘制生产计划、预测需求和库存
                                ax.bar(date_labels, updated_plan['计划产量'], alpha=0.7, label='计划产量')
                                ax.plot(date_labels, updated_plan['预测需求'], marker='o', color='red', label='预测需求')
                                ax.plot(date_labels, updated_plan['期末库存'], marker='s', color='green', label='期末库存')
                                
                                # 添加图表标题和标签
                                ax.set_title(f"物料 {adj_material} 生产计划 (调整后)")
                                ax.set_xlabel('年月')
                                ax.set_ylabel('数量')
                                ax.legend()
                                
                                # 旋转x轴标签
                                plt.xticks(rotation=45)
                                plt.tight_layout()
                                
                                # 更新图表
                                st.session_state.production_charts[adj_material] = fig
                            
                            st.success(f"成功调整 {adj_material} 在 {adj_year}年{adj_month}月 的计划产量")
                        else:
                            st.error("调整计划产量失败")
                    except Exception as e:
                        st.error(f"调整计划时出错: {str(e)}")
        
        with col2:
            st.write("### 调整后的计划")
            
            # 显示调整后的图表
            if 'production_charts' in st.session_state and adj_material in st.session_state.production_charts:
                st.pyplot(st.session_state.production_charts[adj_material])
            
            # 显示调整后的计划数据
            if 'production_plan' in st.session_state and st.session_state.production_plan is not None:
                adj_plan = st.session_state.production_plan[
                    st.session_state.production_plan['物料编号'] == adj_material
                ].sort_values(['年份', '月份'])
                
                st.dataframe(adj_plan)

with tab5:
    st.subheader("导出计划")
    
    # 检查是否已生成生产计划
    if 'production_plan' not in st.session_state or st.session_state.production_plan is None:
        st.info("请先在'生产计划生成'标签页生成计划")
    else:
        st.write("在此页面可以导出生产计划结果，用于MRP计算和计划执行。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 导出格式选项")
            
            export_format = st.radio(
                "选择导出格式",
                ["Excel (.xlsx)", "CSV (.csv)"],
                index=0
            )
            
            include_charts = st.checkbox("包含计划图表(仅Excel格式)", value=True)
        
        with col2:
            st.write("### 导出计划")
            
            if st.button("生成导出文件"):
                with st.spinner("正在准备导出文件，请稍候..."):
                    try:
                        # 准备导出数据
                        export_data = st.session_state.production_plan.copy()
                        
                        # 确保导出目录存在
                        if not os.path.exists("data/exports"):
                            os.makedirs("data/exports", exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        
                        if export_format == "Excel (.xlsx)":
                            # 导出为Excel
                            file_path = f"data/exports/生产计划_{timestamp}.xlsx"
                            
                            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                                # 写入计划数据
                                export_data.to_excel(writer, sheet_name='生产计划', index=False)
                                
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
                                label="下载Excel计划文件",
                                data=excel_bytes,
                                file_name=f"生产计划_{timestamp}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            # 导出为CSV
                            file_path = f"data/exports/生产计划_{timestamp}.csv"
                            export_data.to_csv(file_path, index=False, encoding='utf-8-sig')
                            
                            # 读取CSV文件内容
                            with open(file_path, "rb") as file:
                                csv_bytes = file.read()
                            
                            # 提供下载链接
                            st.download_button(
                                label="下载CSV计划文件",
                                data=csv_bytes,
                                file_name=f"生产计划_{timestamp}.csv",
                                mime="text/csv"
                            )
                        
                        st.success("生产计划导出成功！")
                    except Exception as e:
                        st.error(f"导出生产计划失败: {str(e)}")
            
            # 添加按钮前往MRP页面
            st.write("### 下一步")
            if st.button("前往MRP计算页面"):
                st.switch_page("pages/05_原材料需求计划.py")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求系统 | 生产计划模块")