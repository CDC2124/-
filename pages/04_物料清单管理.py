import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.colors import LinearSegmentedColormap

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入自定义模块
from models.bom_manager import BOMManager

# 页面配置
st.set_page_config(
    page_title="物料清单管理 - 生产需求系统",
    page_icon="🧰",
    layout="wide"
)

# 初始化会话状态
if 'bom_manager' not in st.session_state:
    st.session_state.bom_manager = BOMManager()
if 'bom_data' not in st.session_state:
    st.session_state.bom_data = None
if 'bom_graph' not in st.session_state:
    st.session_state.bom_graph = None
if 'material_types' not in st.session_state:
    st.session_state.material_types = {}
if 'selected_material' not in st.session_state:
    st.session_state.selected_material = None

# 页面标题
st.title("物料清单(BOM)管理")

# 创建侧边栏
st.sidebar.header("BOM操作")

# BOM上传部分
uploaded_file = st.sidebar.file_uploader("上传BOM数据", type=["csv", "xlsx", "xls"])

# 示例数据选项
use_example_data = st.sidebar.checkbox("使用示例数据")

# 处理上传的文件或使用示例数据
if uploaded_file is not None:
    # 保存上传的文件
    file_path = os.path.join("data", "user_uploads", uploaded_file.name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # 加载数据
    st.session_state.bom_data = st.session_state.bom_manager.load_bom_data(file_path)
    
    if st.session_state.bom_data is not None:
        st.sidebar.success(f"成功加载BOM数据: {uploaded_file.name}")
    else:
        st.sidebar.error("BOM数据加载失败，请检查文件格式")

elif use_example_data:
    # 加载示例数据
    example_file_path = os.path.join("data", "samples", "example_bom_data.csv")
    
    if os.path.exists(example_file_path):
        st.session_state.bom_data = st.session_state.bom_manager.load_bom_data(example_file_path)
        st.sidebar.success("已加载示例BOM数据")
    else:
        st.sidebar.error("示例BOM数据文件不存在")
        # 创建示例数据目录
        os.makedirs(os.path.dirname(example_file_path), exist_ok=True)
        
        # 生成简单的示例BOM数据
        example_data = {
            '成品编号': ['M001', 'M001', 'M001', 'M002', 'M002', 'M002', 'M003', 'M003', 'M003'],
            '成品描述': ['电子元件A', '电子元件A', '电子元件A', '电子元件B', '电子元件B', '电子元件B', '电子组件C', '电子组件C', '电子组件C'],
            '子件编号': ['R001', 'C001', 'PCB001', 'R002', 'C002', 'IC001', 'M001', 'M002', 'CAS001'],
            '子件描述': ['电阻', '电容', '电路板', '精密电阻', '高容量电容', '集成电路', '电子元件A', '电子元件B', '外壳'],
            '单位用量': [5, 3, 1, 8, 2, 1, 2, 1, 1],
            '单位': ['个', '个', '片', '个', '个', '个', '个', '个', '个'],
            '损耗率(%)': [2, 1.5, 5, 1, 2, 0.5, 1, 1, 3]
        }
        example_df = pd.DataFrame(example_data)
        
        # 保存示例数据
        example_df.to_csv(example_file_path, index=False)
        st.sidebar.info("已创建并加载示例BOM数据")
        st.session_state.bom_data = example_df

# BOM验证按钮
if st.session_state.bom_data is not None:
    if st.sidebar.button("验证BOM结构"):
        # 构建BOM图
        st.session_state.bom_graph = st.session_state.bom_manager.build_bom_graph()
        
        # 验证BOM数据
        is_valid, message = st.session_state.bom_manager.validate_bom_data()
        
        if is_valid:
            st.sidebar.success("BOM结构验证通过")
            
            # 获取物料类型
            st.session_state.material_types = st.session_state.bom_manager.material_types
            
            # 获取所有成品
            finished_products = [mat_id for mat_id, mat_type in st.session_state.material_types.items() 
                               if mat_type == "成品"]
            
            if finished_products:
                st.session_state.selected_material = finished_products[0]
        else:
            st.sidebar.error(f"BOM结构验证失败: {message}")

# 导出BOM数据
if st.session_state.bom_data is not None:
    if st.sidebar.button("导出BOM数据"):
        export_path = os.path.join("data", "user_uploads", "processed_bom.xlsx")
        if st.session_state.bom_manager.export_bom_data(export_path):
            st.sidebar.success(f"BOM数据已导出至: {export_path}")
        else:
            st.sidebar.error("BOM数据导出失败")

# 主界面内容
tab1, tab2, tab3, tab4 = st.tabs(["BOM数据", "BOM结构", "物料展开", "物料需求"])

with tab1:
    if st.session_state.bom_data is not None:
        st.subheader("BOM数据预览")
        st.dataframe(st.session_state.bom_data)
        
        st.subheader("数据统计")
        st.write(f"总记录数: {len(st.session_state.bom_data)}")
        
        # 显示物料类型统计
        if st.session_state.material_types:
            st.subheader("物料类型统计")
            
            # 计算各类型的数量
            type_counts = pd.Series(st.session_state.material_types).value_counts()
            
            # 创建饼图
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(type_counts, labels=type_counts.index, autopct='%1.1f%%', startangle=90)
            ax.set_title('物料类型分布')
            st.pyplot(fig)
    else:
        st.info("请上传BOM数据或使用示例数据")

with tab2:
    if st.session_state.bom_graph is not None:
        st.subheader("BOM结构可视化")
        
        # 获取所有成品
        finished_products = [mat_id for mat_id, mat_type in st.session_state.material_types.items() 
                           if mat_type == "成品"]
        
        # 选择要显示的成品
        selected_product = st.selectbox("选择成品", finished_products, 
                                      index=finished_products.index(st.session_state.selected_material) 
                                      if st.session_state.selected_material in finished_products else 0)
        
        # 更新选中的物料
        st.session_state.selected_material = selected_product
        
        # 创建子图
        subgraph = nx.DiGraph()
        
        # 使用BFS遍历获取所有相关节点和边
        nodes_to_visit = [selected_product]
        visited = set()
        
        while nodes_to_visit:
            current = nodes_to_visit.pop(0)
            if current in visited:
                continue
                
            visited.add(current)
            
            # 获取子件
            for _, child, data in st.session_state.bom_graph.out_edges(current, data=True):
                subgraph.add_edge(current, child, **data)
                nodes_to_visit.append(child)
        
        # 设置节点颜色
        node_colors = []
        for node in subgraph.nodes():
            if node in st.session_state.material_types:
                if st.session_state.material_types[node] == "成品":
                    node_colors.append('lightblue')
                elif st.session_state.material_types[node] == "半成品":
                    node_colors.append('lightgreen')
                else:  # 基础原料
                    node_colors.append('salmon')
            else:
                node_colors.append('gray')
        
        # 绘制图形
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # 使用分层布局
        pos = nx.nx_agraph.graphviz_layout(subgraph, prog='dot')
        
        # 绘制节点
        nx.draw_networkx_nodes(subgraph, pos, node_color=node_colors, node_size=2000, alpha=0.8)
        
        # 绘制边
        nx.draw_networkx_edges(subgraph, pos, edge_color='gray', arrows=True, arrowsize=20)
        
        # 绘制标签
        nx.draw_networkx_labels(subgraph, pos, font_size=10)
        
        # 绘制边标签（用量）
        edge_labels = {(u, v): f"{d['quantity']}" for u, v, d in subgraph.edges(data=True)}
        nx.draw_networkx_edge_labels(subgraph, pos, edge_labels=edge_labels, font_size=8)
        
        # 添加图例
        import matplotlib.patches as mpatches
        legend_elements = [
            mpatches.Patch(color='lightblue', label='成品'),
            mpatches.Patch(color='lightgreen', label='半成品'),
            mpatches.Patch(color='salmon', label='基础原料')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        # 设置图形边界
        ax.set_title(f'物料 {selected_product} 的BOM结构')
        ax.axis('off')
        
        # 显示图形
        st.pyplot(fig)
        
        # 显示物料信息
        if selected_product in st.session_state.material_types:
            st.subheader(f"物料 {selected_product} 信息")
            st.write(f"物料类型: {st.session_state.material_types[selected_product]}")
            
            # 获取物料描述
            material_info = st.session_state.bom_manager.material_info.get(selected_product, {})
            if 'description' in material_info:
                st.write(f"物料描述: {material_info['description']}")
    else:
        st.info("请先验证BOM结构")

with tab3:
    if st.session_state.bom_graph is not None and st.session_state.selected_material:
        st.subheader("物料展开")
        
        # 选择展开层级
        levels = st.slider("展开层级", min_value=1, max_value=5, value=3)
        
        # 选择物料类型
        material_type_options = ["全部", "成品", "半成品", "基础原料"]
        selected_type = st.selectbox("筛选物料类型", material_type_options)
        
        # 转换为BOM管理器使用的类型
        filter_type = None
        if selected_type != "全部":
            filter_type = selected_type
        
        # 展开BOM
        exploded_bom = st.session_state.bom_manager.explode_bom(
            st.session_state.selected_material, 
            levels=levels,
            material_type=filter_type
        )
        
        if exploded_bom is not None and not exploded_bom.empty:
            st.dataframe(exploded_bom)
            
            # 创建物料用量图表
            st.subheader("物料用量分析")
            
            # 按物料类型分组
            if '物料类型' in exploded_bom.columns:
                grouped_data = exploded_bom.groupby('物料类型')['总用量'].sum().reset_index()
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(grouped_data['物料类型'], grouped_data['总用量'])
                ax.set_title(f'物料 {st.session_state.selected_material} 的组件用量 (按类型)')
                ax.set_xlabel('物料类型')
                ax.set_ylabel('总用量')
                st.pyplot(fig)
            
            # 创建用量前10的物料图表
            top_materials = exploded_bom.sort_values('总用量', ascending=False).head(10)
            
            fig, ax = plt.subplots(figsize=(12, 6))
            bars = ax.barh(top_materials['组件编号'], top_materials['总用量'])
            
            # 为条形图添加颜色
            if '物料类型' in top_materials.columns:
                colors = {'成品': 'lightblue', '半成品': 'lightgreen', '基础原料': 'salmon'}
                for i, bar in enumerate(bars):
                    bar.set_color(colors.get(top_materials.iloc[i]['物料类型'], 'gray'))
            
            ax.set_title(f'物料 {st.session_state.selected_material} 的前10个组件用量')
            ax.set_xlabel('总用量')
            ax.set_ylabel('组件编号')
            
            # 反转Y轴，使最大值在顶部
            ax.invert_yaxis()
            
            st.pyplot(fig)
        else:
            st.info(f"物料 {st.session_state.selected_material} 没有符合条件的子组件")
    else:
        st.info("请先验证BOM结构并选择物料")

with tab4:
    if st.session_state.bom_graph is not None:
        st.subheader("物料需求计算")
        
        # 创建简单的生产计划输入
        st.write("输入生产计划数量:")
        
        # 获取所有成品
        finished_products = [mat_id for mat_id, mat_type in st.session_state.material_types.items() 
                           if mat_type == "成品"]
        
        # 创建输入表单
        with st.form("production_plan_form"):
            # 创建列表存储输入值
            production_inputs = []
            
            # 为每个成品创建输入字段
            for product in finished_products:
                # 获取物料描述
                material_info = st.session_state.bom_manager.material_info.get(product, {})
                description = material_info.get('description', product)
                
                # 创建输入字段
                quantity = st.number_input(f"{product} - {description}", min_value=0, value=100, step=10)
                production_inputs.append((product, quantity))
            
            # 提交按钮
            submitted = st.form_submit_button("计算物料需求")
        
        if submitted:
            # 创建生产计划DataFrame
            plan_data = {
                '物料编号': [p[0] for p in production_inputs],
                '计划产量': [p[1] for p in production_inputs]
            }
            production_plan = pd.DataFrame(plan_data)
            
            # 计算原材料需求
            raw_requirements = st.session_state.bom_manager.calculate_raw_material_requirements(production_plan)
            
            if raw_requirements is not None and not raw_requirements.empty:
                st.subheader("基础原料需求")
                st.dataframe(raw_requirements)
                
                # 创建原材料需求图表
                fig, ax = plt.subplots(figsize=(12, 6))
                bars = ax.barh(raw_requirements['物料编号'], raw_requirements['需求量'])
                
                ax.set_title('基础原料需求量')
                ax.set_xlabel('需求量')
                ax.set_ylabel('物料编号')
                
                # 反转Y轴，使最大值在顶部
                ax.invert_yaxis()
                
                st.pyplot(fig)
            else:
                st.info("未计算出任何基础原料需求")
            
            # 计算半成品需求
            semifinished_requirements = st.session_state.bom_manager.calculate_semifinished_requirements(production_plan)
            
            if semifinished_requirements is not None and not semifinished_requirements.empty:
                st.subheader("半成品需求")
                st.dataframe(semifinished_requirements)
                
                # 创建半成品需求图表
                fig, ax = plt.subplots(figsize=(12, 6))
                bars = ax.barh(semifinished_requirements['物料编号'], semifinished_requirements['需求量'])
                
                ax.set_title('半成品需求量')
                ax.set_xlabel('需求量')
                ax.set_ylabel('物料编号')
                
                # 反转Y轴，使最大值在顶部
                ax.invert_yaxis()
                
                st.pyplot(fig)
            else:
                st.info("未计算出任何半成品需求")
    else:
        st.info("请先验证BOM结构")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求规划系统 | 物料清单管理模块")