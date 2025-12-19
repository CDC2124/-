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
from models.bom_manager import BOMManager
from models.mrp_calculator import MRPCalculator

# 页面配置
st.set_page_config(
    page_title="原材料需求计划 - 生产需求系统",
    page_icon="🧰",
    layout="wide"
)

# 初始化会话状态
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = DataProcessor()

if 'forecaster' not in st.session_state:
    st.session_state.forecaster = Forecaster()

if 'production_planner' not in st.session_state:
    st.session_state.production_planner = ProductionPlanner()

if 'bom_manager' not in st.session_state:
    st.session_state.bom_manager = BOMManager()

if 'mrp_calculator' not in st.session_state:
    st.session_state.mrp_calculator = MRPCalculator(st.session_state.bom_manager)

if 'production_plan' not in st.session_state:
    st.session_state.production_plan = None

if 'bom_data' not in st.session_state:
    st.session_state.bom_data = None

if 'raw_material_requirements' not in st.session_state:
    st.session_state.raw_material_requirements = None

if 'semifinished_requirements' not in st.session_state:
    st.session_state.semifinished_requirements = None

if 'purchase_plan' not in st.session_state:
    st.session_state.purchase_plan = None

# 页面标题
st.title("原材料需求计划(MRP)")

# 页面描述
st.markdown("""
此页面基于生产计划和物料清单(BOM)生成优化的原材料需求计划，使用OR-Tools进行优化计算。

### MRP功能:
- 自动计算基础原料和半成品的需求
- 考虑多级BOM结构
- 基于OR-Tools的采购优化
- 优化供应商选择和订单合并
- 交互式结果可视化
- 采购计划导出
""")

# 创建标签页
tab1, tab2, tab3, tab4 = st.tabs(["数据准备", "MRP参数", "需求计算", "导出结果"])

with tab1:
    st.subheader("数据准备")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 生产计划数据")
        
        # 尝试从会话状态中获取生产计划数据
        if 'production_plan' in st.session_state and st.session_state.production_plan is not None:
            st.success(f"已加载生产计划数据，包含 {len(st.session_state.production_plan)} 条记录")
            
            # 显示数据预览
            st.write("生产计划数据预览：")
            st.dataframe(st.session_state.production_plan.head())
        else:
            st.info("请先在'生产计划'页面生成计划数据")
            
            if st.button("前往生产计划页面"):
                st.switch_page("pages/03_生产计划.py")
            
            # 提供上传生产计划功能
            st.write("或上传已有的生产计划数据")
            
            plan_file = st.file_uploader("选择生产计划文件", type=['csv', 'xlsx', 'xls'])
            
            if plan_file is not None:
                try:
                    if plan_file.name.endswith('.csv'):
                        plan_data = pd.read_csv(plan_file)
                    else:
                        plan_data = pd.read_excel(plan_file)
                    
                    st.success(f"生产计划上传成功，包含 {len(plan_data)} 条记录")
                    
                    # 显示数据预览
                    st.write("生产计划预览：")
                    st.dataframe(plan_data.head())
                    
                    # 检查必要字段
                    required_fields = ['年份', '月份', '物料编号', '计划产量']
                    missing_fields = [field for field in required_fields if field not in plan_data.columns]
                    
                    if missing_fields:
                        st.error(f"计划数据缺少必要字段: {', '.join(missing_fields)}")
                    else:
                        # 保存到会话状态
                        st.session_state.production_plan = plan_data
                        
                        # 加载到生产计划器
                        st.session_state.production_planner.production_plan = plan_data
                except Exception as e:
                    st.error(f"处理计划文件时出错: {str(e)}")
    
    with col2:
        st.write("### 物料清单(BOM)数据")
        
        # 尝试从会话状态中获取BOM数据
        if 'bom_data' in st.session_state and st.session_state.bom_data is not None:
            st.success(f"已加载BOM数据，包含 {len(st.session_state.bom_data)} 条记录")
            
            # 显示数据预览
            st.write("BOM数据预览：")
            st.dataframe(st.session_state.bom_data.head())
        else:
            st.write("请上传物料清单(BOM)数据")
            
            bom_file = st.file_uploader("选择BOM文件", type=['csv', 'xlsx', 'xls'])
            
            if bom_file is not None:
                try:
                    if bom_file.name.endswith('.csv'):
                        bom_data = pd.read_csv(bom_file)
                    else:
                        bom_data = pd.read_excel(bom_file)
                    
                    st.success(f"BOM数据上传成功，包含 {len(bom_data)} 条记录")
                    
                    # 显示数据预览
                    st.write("BOM数据预览：")
                    st.dataframe(bom_data.head())
                    
                    # 检查必要字段
                    required_fields = ['成品编号', '子件编号', '单位用量']
                    missing_fields = [field for field in required_fields if field not in bom_data.columns]
                    
                    if missing_fields:
                        st.error(f"BOM数据缺少必要字段: {', '.join(missing_fields)}")
                    else:
                        # 保存到会话状态
                        st.session_state.bom_data = bom_data
                        
                        # 加载到BOM管理器
                        st.session_state.bom_manager.load_bom_data(bom_data)
                        
                        # 构建BOM图
                        st.session_state.bom_manager.build_bom_graph()
                        
                        # 推断物料类型
                        st.session_state.bom_manager.infer_material_types()
                        
                        # 验证BOM结构
                        is_valid, message = st.session_state.bom_manager.validate_hierarchy()
                        
                        if is_valid:
                            st.success(message)
                        else:
                            st.warning(message)
                except Exception as e:
                    st.error(f"处理BOM文件时出错: {str(e)}")
    
    # 库存数据
    st.write("### 原材料库存数据（可选）")
    
    inventory_source = st.radio(
        "库存数据来源",
        ["上传库存文件", "手动输入", "不考虑库存"]
    )
    
    if inventory_source == "上传库存文件":
        raw_inventory_file = st.file_uploader("选择原材料库存数据文件", type=['csv', 'xlsx', 'xls'])
        
        if raw_inventory_file is not None:
            try:
                if raw_inventory_file.name.endswith('.csv'):
                    raw_inventory = pd.read_csv(raw_inventory_file)
                else:
                    raw_inventory = pd.read_excel(raw_inventory_file)
                
                st.success(f"原材料库存数据上传成功，包含 {len(raw_inventory)} 条记录")
                
                # 显示数据预览
                st.write("原材料库存数据预览：")
                st.dataframe(raw_inventory.head())
                
                # 检查必要字段
                required_fields = ['物料编号', '库存数量']
                missing_fields = [field for field in required_fields if field not in raw_inventory.columns]
                
                if missing_fields:
                    st.error(f"库存数据缺少必要字段: {', '.join(missing_fields)}")
                else:
                    # 保存到会话状态并加载到MRP计算器
                    st.session_state.raw_material_inventory = raw_inventory
                    st.session_state.mrp_calculator.load_raw_material_inventory(raw_inventory)
            except Exception as e:
                st.error(f"处理库存文件时出错: {str(e)}")
    
    elif inventory_source == "手动输入":
        st.write("请手动输入原材料库存数据")
        
        # 只有在有BOM数据时才允许手动输入库存
        if 'bom_data' in st.session_state and st.session_state.bom_data is not None:
            # 尝试获取基础原料清单
            raw_materials = set()
            
            for _, row in st.session_state.bom_data.iterrows():
                child_id = row['子件编号']
                # 检查此物料是否是基础原料（没有子件）
                is_raw = True
                for _, r in st.session_state.bom_data.iterrows():
                    if r['成品编号'] == child_id:
                        is_raw = False
                        break
                if is_raw:
                    raw_materials.add(child_id)
            
            # 创建一个DataFrame用于编辑
            if 'manual_raw_inventory' not in st.session_state:
                # 初始化为所有物料的库存为0
                st.session_state.manual_raw_inventory = pd.DataFrame({
                    '物料编号': list(raw_materials),
                    '库存数量': np.zeros(len(raw_materials))
                })
            
            # 显示编辑表
            edited_raw_df = st.data_editor(
                st.session_state.manual_raw_inventory,
                num_rows="fixed",
                key="raw_inventory_editor"
            )
            
            # 当用户编辑表格时更新会话状态
            if st.button("更新原材料库存数据"):
                st.session_state.manual_raw_inventory = edited_raw_df
                st.session_state.raw_material_inventory = edited_raw_df
                st.session_state.mrp_calculator.load_raw_material_inventory(edited_raw_df)
                st.success("原材料库存数据已更新")
        else:
            st.info("请先加载BOM数据，才能手动输入库存")
    
    # 供应商数据
    st.write("### 供应商数据（可选）")
    
    supplier_source = st.radio(
        "供应商数据来源",
        ["上传供应商文件", "使用默认供应商设置", "不使用供应商数据"]
    )
    
    if supplier_source == "上传供应商文件":
        supplier_file = st.file_uploader("选择供应商数据文件", type=['csv', 'xlsx', 'xls'])
        
        if supplier_file is not None:
            try:
                if supplier_file.name.endswith('.csv'):
                    supplier_data = pd.read_csv(supplier_file)
                else:
                    supplier_data = pd.read_excel(supplier_file)
                
                st.success(f"供应商数据上传成功，包含 {len(supplier_data)} 条记录")
                
                # 显示数据预览
                st.write("供应商数据预览：")
                st.dataframe(supplier_data.head())
                
                # 检查必要字段
                required_fields = ['物料编号', '供应商编号']
                missing_fields = [field for field in required_fields if field not in supplier_data.columns]
                
                if missing_fields:
                    st.error(f"供应商数据缺少必要字段: {', '.join(missing_fields)}")
                else:
                    # 保存到会话状态和BOM管理器
                    st.session_state.supplier_data = supplier_data
                    st.session_state.bom_manager.load_supplier_data(supplier_data)
                    
                    # 加载到MRP计算器
                    st.session_state.mrp_calculator.load_supplier_data(supplier_data)
            except Exception as e:
                st.error(f"处理供应商文件时出错: {str(e)}")
    
    elif supplier_source == "使用默认供应商设置":
        st.write("使用默认供应商参数")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_lead_time = st.number_input("默认采购提前期(天)", min_value=1, value=30)
            default_min_order = st.number_input("默认最小订购量", min_value=1, value=100)
        
        with col2:
            default_price = st.number_input("默认单价", min_value=0.1, value=1.0)
            
        if st.button("应用默认供应商设置"):
            # 只有在有BOM数据时才应用
            if 'bom_data' in st.session_state and st.session_state.bom_data is not None:
                # 尝试获取基础原料清单
                raw_materials = set()
                
                for _, row in st.session_state.bom_data.iterrows():
                    child_id = row['子件编号']
                    # 检查此物料是否是基础原料（没有子件）
                    is_raw = True
                    for _, r in st.session_state.bom_data.iterrows():
                        if r['成品编号'] == child_id:
                            is_raw = False
                            break
                    if is_raw:
                        raw_materials.add(child_id)
                
                # 创建默认供应商数据
                default_suppliers = []
                
                for material in raw_materials:
                    default_suppliers.append({
                        '物料编号': material,
                        '供应商编号': 'DEFAULT_SUPPLIER',
                        '单价': default_price,
                        '最小订购量': default_min_order,
                        '采购提前期': default_lead_time
                    })
                
                # 创建DataFrame
                supplier_df = pd.DataFrame(default_suppliers)
                
                # 保存到会话状态和加载到MRP计算器
                st.session_state.supplier_data = supplier_df
                st.session_state.mrp_calculator.load_supplier_data(supplier_df)
                
                st.success(f"已应用默认供应商设置，涵盖 {len(raw_materials)} 种原材料")
            else:
                st.error("请先加载BOM数据，才能应用默认供应商设置")

with tab2:
    st.subheader("MRP参数设置")
    
    # 检查是否已加载必要数据
    if 'production_plan' not in st.session_state or st.session_state.production_plan is None:
        st.info("请先在'数据准备'标签页加载生产计划数据")
    elif 'bom_data' not in st.session_state or st.session_state.bom_data is None:
        st.info("请先在'数据准备'标签页加载BOM数据")
    else:
        st.write("设置MRP计算的参数")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 库存参数")
            
            safety_stock_days = st.slider(
                "安全库存天数",
                min_value=0,
                max_value=60,
                value=15,
                help="设置原材料安全库存水平（以天为单位）"
            )
            
            max_inventory_days = st.slider(
                "最大库存天数",
                min_value=safety_stock_days,
                max_value=120,
                value=60,
                help="设置原材料最大允许库存水平（以天为单位）"
            )
        
        with col2:
            st.write("### 订单参数")
            
            order_multiple = st.number_input(
                "订单倍数",
                min_value=1,
                value=1,
                help="设置订单批量倍数，例如：如果最小订单量是100，订单倍数是5，则实际订单量必须是500的倍数"
            )
            
            planning_horizon = st.slider(
                "计划期数",
                min_value=1,
                max_value=24,
                value=6,
                help="设置MRP计划的期数（月）"
            )
        
        # 汇总所有MRP参数
        mrp_parameters = {
            'safety_stock_days': safety_stock_days,
            'max_inventory_days': max_inventory_days,
            'order_multiple': order_multiple,
            'planning_horizon': planning_horizon
        }
        
        # 应用参数按钮
        if st.button("应用MRP参数"):
            # 保存参数到会话状态
            st.session_state.mrp_parameters = mrp_parameters
            
            # 设置MRP计算器的参数
            if st.session_state.mrp_calculator.set_mrp_parameters(mrp_parameters):
                st.success("MRP参数设置已应用")
            else:
                st.error("应用MRP参数失败")

with tab3:
    st.subheader("需求计算")
    
    # 检查是否已加载必要数据
    if 'production_plan' not in st.session_state or st.session_state.production_plan is None:
        st.info("请先在'数据准备'标签页加载生产计划数据")
    elif 'bom_data' not in st.session_state or st.session_state.bom_data is None:
        st.info("请先在'数据准备'标签页加载BOM数据")
    elif 'mrp_parameters' not in st.session_state:
        st.info("请先在'MRP参数'标签页设置计算参数")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("### 计算MRP")
            
            # 添加计算按钮
            if st.button("​计算原材料需求​"):
                with st.spinner("正在计算原材料需求，请稍候..."):
                    try:
                        # 准备数据
                        # 1. 设置BOM管理器引用
                        st.session_state.mrp_calculator.set_bom_manager(st.session_state.bom_manager)
                        
                        # 2. 加载生产计划
                        st.session_state.mrp_calculator.load_production_plan(st.session_state.production_plan)
                        
                        # 3. 计算需求
                        raw_requirements, semifinished_requirements = st.session_state.mrp_calculator.calculate_requirements()
                        
                        if raw_requirements is not None and semifinished_requirements is not None:
                            # 保存计算结果
                            st.session_state.raw_material_requirements = raw_requirements
                            st.session_state.semifinished_requirements = semifinished_requirements
                            
                            st.success(f"需求计算成功，发现 {len(raw_requirements)} 种原材料和 {len(semifinished_requirements)} 种半成品")
                            
                            # 继续计算采购计划
                            if st.session_state.mrp_calculator.optimize_purchase_plan() is not None:
                                st.session_state.purchase_plan = st.session_state.mrp_calculator.purchase_plan
                                st.success("采购计划优化成功")
                                
                                # 继续计算半成品生产计划
                                semifinished_plan = st.session_state.mrp_calculator.generate_semifinished_production_plan()
                                
                                if semifinished_plan is not None:
                                    st.session_state.semifinished_plan = semifinished_plan
                                    st.success("半成品生产计划生成成功")
                                else:
                                    st.warning("半成品生产计划生成失败")
                            else:
                                st.error("采购计划优化失败")
                        else:
                            st.error("需求计算失败")
                    except Exception as e:
                        st.error(f"MRP计算出错: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
        
        with col2:
            st.write("### 计算结果")
            
            # 显示计算结果
            if 'raw_material_requirements' in st.session_state and st.session_state.raw_material_requirements is not None:
                # 创建结果标签页
                result_tab1, result_tab2, result_tab3 = st.tabs(["原材料需求", "半成品需求", "采购计划"])
                
                with result_tab1:
                    st.write("#### 原材料总需求")
                    
                    # 显示原材料需求
                    st.dataframe(st.session_state.raw_material_requirements)
                    
                    # 可视化
                    if len(st.session_state.raw_material_requirements) > 0:
                        # 取需求量最大的前8种原材料
                        top_materials = st.session_state.raw_material_requirements.nlargest(8, '需求量')
                        
                        fig, ax = plt.subplots(figsize=(10, 6))
                        ax.bar(top_materials['物料编号'], top_materials['需求量'])
                        ax.set_title('需求量最大的原材料')
                        ax.set_xlabel('物料编号')
                        ax.set_ylabel('需求量')
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        
                        st.pyplot(fig)
                
                with result_tab2:
                    if 'semifinished_requirements' in st.session_state and st.session_state.semifinished_requirements is not None:
                        st.write("#### 半成品需求")
                        
                        # 显示半成品需求
                        st.dataframe(st.session_state.semifinished_requirements)
                        
                        # 可视化
                        if len(st.session_state.semifinished_requirements) > 0:
                            # 取需求量最大的前8种半成品
                            top_semifinished = st.session_state.semifinished_requirements.nlargest(8, '需求量')
                            
                            fig, ax = plt.subplots(figsize=(10, 6))
                            ax.bar(top_semifinished['物料编号'], top_semifinished['需求量'])
                            ax.set_title('需求量最大的半成品')
                            ax.set_xlabel('物料编号')
                            ax.set_ylabel('需求量')
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            
                            st.pyplot(fig)
                    else:
                        st.info("未计算出半成品需求")
                
                with result_tab3:
                    if 'purchase_plan' in st.session_state and st.session_state.purchase_plan is not None:
                        st.write("#### 采购计划")
                        
                        # 显示采购计划
                        st.dataframe(st.session_state.purchase_plan)
                        
                        # 可视化
                        if len(st.session_state.purchase_plan) > 0:
                            # 按月份汇总采购量和成本
                            monthly_purchase = st.session_state.purchase_plan.groupby(['年份', '月份']).agg({
                                '计划采购量': 'sum',
                                '预计成本': 'sum'
                            }).reset_index()
                            
                            # 创建月份标签
                            monthly_labels = [f"{year}-{month}" for year, month in zip(monthly_purchase['年份'], monthly_purchase['月份'])]
                            
                            fig, ax1 = plt.subplots(figsize=(10, 6))
                            
                            # 绘制采购量
                            ax1.bar(monthly_labels, monthly_purchase['计划采购量'], color='blue', alpha=0.7)
                            ax1.set_xlabel('年月')
                            ax1.set_ylabel('采购量', color='blue')
                            ax1.tick_params(axis='y', labelcolor='blue')
                            
                            # 添加第二个Y轴显示成本
                            ax2 = ax1.twinx()
                            ax2.plot(monthly_labels, monthly_purchase['预计成本'], 'r-', marker='o')
                            ax2.set_ylabel('采购成本', color='red')
                            ax2.tick_params(axis='y', labelcolor='red')
                            
                            plt.title('月度采购计划')
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            
                            st.pyplot(fig)
                            
                            # 显示总成本
                            total_cost = st.session_state.purchase_plan['预计成本'].sum()
                            st.metric("采购总成本", f"{total_cost:.2f}")
                    else:
                        st.info("未生成采购计划")
            else:
                st.info("请点击'计算原材料需求'按钮进行计算")

with tab4:
    st.subheader("导出结果")
    
    # 检查是否已计算MRP
    if 'raw_material_requirements' not in st.session_state or st.session_state.raw_material_requirements is None:
        st.info("请先在'需求计算'标签页计算原材料需求")
    else:
        st.write("在此页面可以导出MRP计算结果，用于采购和生产执行。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 导出格式选项")
            
            export_format = st.radio(
                "选择导出格式",
                ["Excel (.xlsx)", "CSV (.csv)"],
                index=0
            )
            
            export_option = st.radio(
                "导出内容",
                ["导出所有结果", "仅导出采购计划", "仅导出原材料需求"]
            )
        
        with col2:
            st.write("### 导出结果")
            
            if st.button("生成导出文件"):
                with st.spinner("正在准备导出文件，请稍候..."):
                    try:
                        # 确保导出目录存在
                        if not os.path.exists("data/exports"):
                            os.makedirs("data/exports", exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        
                        if export_format == "Excel (.xlsx)":
                            # 导出为Excel
                            file_path = f"data/exports/MRP计算结果_{timestamp}.xlsx"
                            
                            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                                # 根据选项决定导出内容
                                if export_option in ["导出所有结果", "仅导出原材料需求"]:
                                    # 导出原材料需求
                                    st.session_state.raw_material_requirements.to_excel(
                                        writer, 
                                        sheet_name='原材料需求', 
                                        index=False
                                    )
                                    
                                    # 导出半成品需求（如果有）
                                    if 'semifinished_requirements' in st.session_state and st.session_state.semifinished_requirements is not None:
                                        st.session_state.semifinished_requirements.to_excel(
                                            writer, 
                                            sheet_name='半成品需求', 
                                            index=False
                                        )
                                
                                if export_option in ["导出所有结果", "仅导出采购计划"]:
                                    # 导出采购计划（如果有）
                                    if 'purchase_plan' in st.session_state and st.session_state.purchase_plan is not None:
                                        st.session_state.purchase_plan.to_excel(
                                            writer, 
                                            sheet_name='采购计划', 
                                            index=False
                                        )
                                    
                                    # 导出半成品生产计划（如果有）
                                    if 'semifinished_plan' in st.session_state and st.session_state.semifinished_plan is not None:
                                        st.session_state.semifinished_plan.to_excel(
                                            writer, 
                                            sheet_name='半成品生产计划', 
                                            index=False
                                        )
                            
                            # 读取Excel文件内容
                            with open(file_path, "rb") as file:
                                excel_bytes = file.read()
                            
                            # 提供下载链接
                            st.download_button(
                                label="下载Excel结果文件",
                                data=excel_bytes,
                                file_name=f"MRP计算结果_{timestamp}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            # 导出为CSV，由于CSV只能存一个表，因此根据选项决定导出内容
                            if export_option == "仅导出采购计划" and 'purchase_plan' in st.session_state and st.session_state.purchase_plan is not None:
                                file_path = f"data/exports/采购计划_{timestamp}.csv"
                                st.session_state.purchase_plan.to_csv(file_path, index=False, encoding='utf-8-sig')
                                
                                # 读取CSV文件内容
                                with open(file_path, "rb") as file:
                                    csv_bytes = file.read()
                                
                                # 提供下载链接
                                st.download_button(
                                    label="下载采购计划CSV文件",
                                    data=csv_bytes,
                                    file_name=f"采购计划_{timestamp}.csv",
                                    mime="text/csv"
                                )
                            elif export_option == "仅导出原材料需求":
                                file_path = f"data/exports/原材料需求_{timestamp}.csv"
                                st.session_state.raw_material_requirements.to_csv(file_path, index=False, encoding='utf-8-sig')
                                
                                # 读取CSV文件内容
                                with open(file_path, "rb") as file:
                                    csv_bytes = file.read()
                                
                                # 提供下载链接
                                st.download_button(
                                    label="下载原材料需求CSV文件",
                                    data=csv_bytes,
                                    file_name=f"原材料需求_{timestamp}.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.warning("CSV格式只能导出单个表。请选择'仅导出采购计划'或'仅导出原材料需求'选项，或者选择Excel格式导出所有结果。")
                        
                        st.success("MRP计算结果导出成功！")
                    except Exception as e:
                        st.error(f"导出结果失败: {str(e)}")
            
            # 添加按钮前往报告页面
            st.write("### 结果报告")
            if st.button("生成完整MRP报告"):
                if 'mrp_calculator' in st.session_state and st.session_state.mrp_calculator is not None:
                    with st.spinner("正在生成MRP报告，请稍候..."):
                        try:
                            # 创建报告目录
                            if not os.path.exists("data/reports"):
                                os.makedirs("data/reports", exist_ok=True)
                            
                            report_path = f"data/reports/MRP报告_{timestamp}"
                            
                            # 创建目录
                            if not os.path.exists(report_path):
                                os.makedirs(report_path)
                            
                            # 导出报告
                            if st.session_state.mrp_calculator.export_mrp_report(report_path):
                                st.success(f"MRP报告成功生成，并保存到 {report_path}")
                                
                                # 提供ZIP下载
                                # 注意：这里需要先将目录压缩成ZIP
                                # 由于我们没有ZIP库，所以只提示用户
                                st.info(f"您可以在以下位置找到完整MRP报告：{report_path}")
                            else:
                                st.error("MRP报告生成失败")
                        except Exception as e:
                            st.error(f"生成报告时出错: {str(e)}")
                else:
                    st.error("MRP计算器未初始化")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求系统 | 原材料需求计划模块")