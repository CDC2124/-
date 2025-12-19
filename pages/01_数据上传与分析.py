import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入自定义模块
from models.data_processor import DataProcessor

# 页面配置
st.set_page_config(
    page_title="数据上传与分析 - 生产需求系统",
    page_icon="📊",
    layout="wide"
)

# 初始化会话状态
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = DataProcessor()
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'monthly_data' not in st.session_state:
    st.session_state.monthly_data = None
if 'material_summary' not in st.session_state:
    st.session_state.material_summary = None

# 页面标题
st.title("数据上传与分析")

# 创建侧边栏
st.sidebar.header("数据操作")

# 数据上传部分
uploaded_file = st.sidebar.file_uploader("上传历史出货数据", type=["csv", "xlsx", "xls"])

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
    st.session_state.raw_data = st.session_state.data_processor.load_data(file_path)
    
    if st.session_state.raw_data is not None:
        st.sidebar.success(f"成功加载数据: {uploaded_file.name}")
    else:
        st.sidebar.error("数据加载失败，请检查文件格式")

elif use_example_data:
    # 加载示例数据
    example_file_path = os.path.join("data", "samples", "example_shipment_data.csv")
    
    if os.path.exists(example_file_path):
        st.session_state.raw_data = st.session_state.data_processor.load_data(example_file_path)
        st.sidebar.success("已加载示例数据")
    else:
        st.sidebar.error("示例数据文件不存在")
        # 创建示例数据目录
        os.makedirs(os.path.dirname(example_file_path), exist_ok=True)
        
        # 生成简单的示例数据
        example_data = {
            '销售请求日期': pd.date_range(start='2023-01-01', periods=100),
            '仓库实际日期': pd.date_range(start='2023-01-05', periods=100),
            '物料编号': ['M00' + str(i % 5 + 1) for i in range(100)],
            '批次数量': np.random.randint(100, 1000, size=100)
        }
        example_df = pd.DataFrame(example_data)
        
        # 保存示例数据
        example_df.to_csv(example_file_path, index=False)
        st.sidebar.info("已创建并加载示例数据")
        st.session_state.raw_data = example_df

# 数据处理按钮
if st.session_state.raw_data is not None:
    if st.sidebar.button("处理数据"):
        # 验证数据
        is_valid, message = st.session_state.data_processor.validate_data()
        
        if is_valid:
            # 处理数据
            st.session_state.processed_data = st.session_state.data_processor.preprocess_data()
            
            # 汇总月度数据
            st.session_state.monthly_data = st.session_state.data_processor.aggregate_monthly_data()
            
            # 分析物料数据
            st.session_state.material_summary = st.session_state.data_processor.analyze_material_data()
            
            st.sidebar.success("数据处理完成")
        else:
            st.sidebar.error(f"数据验证失败: {message}")

# 导出处理后的数据
if st.session_state.processed_data is not None:
    if st.sidebar.button("导出处理后的数据"):
        export_path = os.path.join("data", "user_uploads", "processed_data.xlsx")
        if st.session_state.data_processor.export_processed_data(export_path):
            st.sidebar.success(f"数据已导出至: {export_path}")
        else:
            st.sidebar.error("数据导出失败")

# 主界面内容
tab1, tab2, tab3, tab4 = st.tabs(["原始数据", "处理后数据", "月度汇总", "物料分析"])

with tab1:
    if st.session_state.raw_data is not None:
        st.subheader("原始数据预览")
        st.dataframe(st.session_state.raw_data.head(100))
        
        st.subheader("数据统计")
        st.write(f"总记录数: {len(st.session_state.raw_data)}")
        
        # 显示数据类型
        st.subheader("数据类型")
        st.write(st.session_state.raw_data.dtypes)
    else:
        st.info("请上传数据或使用示例数据")

with tab2:
    if st.session_state.processed_data is not None:
        st.subheader("处理后数据预览")
        st.dataframe(st.session_state.processed_data.head(100))
        
        st.subheader("数据处理统计")
        st.write(f"处理前记录数: {len(st.session_state.raw_data)}")
        st.write(f"处理后记录数: {len(st.session_state.processed_data)}")
        st.write(f"移除的记录数: {len(st.session_state.raw_data) - len(st.session_state.processed_data)}")
        
        # 显示处理后的数据分布
        st.subheader("批次数量分布")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(st.session_state.processed_data['批次数量'], bins=20, ax=ax)
        st.pyplot(fig)
    else:
        st.info("请先处理数据")

with tab3:
    if st.session_state.monthly_data is not None:
        st.subheader("月度汇总数据")
        st.dataframe(st.session_state.monthly_data)
        
        # 按月份和物料显示趋势
        st.subheader("月度趋势分析")
        
        # 选择物料
        materials = st.session_state.monthly_data['物料编号'].unique()
        selected_material = st.selectbox("选择物料", materials)
        
        # 筛选数据
        material_data = st.session_state.monthly_data[st.session_state.monthly_data['物料编号'] == selected_material]
        
        # 创建时间序列
        material_data['日期'] = pd.to_datetime(material_data['年份'].astype(str) + '-' + material_data['月份'].astype(str) + '-01')
        material_data = material_data.sort_values('日期')
        
        # 绘制趋势图
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(material_data['日期'], material_data['批次数量'], marker='o')
        ax.set_title(f'物料 {selected_material} 月度出货量趋势')
        ax.set_xlabel('日期')
        ax.set_ylabel('批次数量')
        ax.grid(True)
        st.pyplot(fig)
        
        # 计算季节性
        if len(material_data) >= 12:
            st.subheader("季节性分析")
            seasonality = st.session_state.data_processor.calculate_seasonality(selected_material)
            
            if seasonality is not None:
                # 绘制季节性指数
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(seasonality['月份'], seasonality['季节性指数'])
                ax.axhline(y=1.0, color='r', linestyle='-')
                ax.set_title(f'物料 {selected_material} 季节性指数')
                ax.set_xlabel('月份')
                ax.set_ylabel('季节性指数')
                ax.set_xticks(range(1, 13))
                st.pyplot(fig)
    else:
        st.info("请先处理数据")

with tab4:
    if st.session_state.material_summary is not None:
        st.subheader("物料分析摘要")
        st.dataframe(st.session_state.material_summary)
        
        # ABC分析
        st.subheader("ABC分析")
        
        # 计算各类别的数量
        abc_counts = st.session_state.material_summary['ABC分类'].value_counts()
        
        # 绘制饼图
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # 数量饼图
        ax1.pie(abc_counts, labels=abc_counts.index, autopct='%1.1f%%', startangle=90)
        ax1.set_title('物料ABC分类 (按数量)')
        
        # 出货量饼图
        abc_volume = st.session_state.material_summary.groupby('ABC分类')['总出货量'].sum()
        ax2.pie(abc_volume, labels=abc_volume.index, autopct='%1.1f%%', startangle=90)
        ax2.set_title('物料ABC分类 (按出货量)')
        
        st.pyplot(fig)
        
        # 变异系数分析
        st.subheader("需求波动性分析")
        
        # 绘制变异系数散点图
        fig, ax = plt.subplots(figsize=(12, 8))
        scatter = ax.scatter(
            st.session_state.material_summary['月均出货量'], 
            st.session_state.material_summary['变异系数'],
            c=st.session_state.material_summary['ABC分类'].map({'A': 0, 'B': 1, 'C': 2}),
            cmap='viridis',
            alpha=0.7,
            s=100
        )
        
        # 添加图例
        legend1 = ax.legend(scatter.legend_elements()[0], ['A类', 'B类', 'C类'], title="ABC分类")
        ax.add_artist(legend1)
        
        ax.set_xlabel('月均出货量')
        ax.set_ylabel('变异系数 (CV)')
        ax.set_title('物料需求波动性分析')
        ax.grid(True)
        
        # 添加物料标签
        for i, row in st.session_state.material_summary.iterrows():
            if row['ABC分类'] == 'A' or row['变异系数'] > 1.5:
                ax.annotate(row['物料编号'], (row['月均出货量'], row['变异系数']))
        
        st.pyplot(fig)
    else:
        st.info("请先处理数据")

# 页脚
st.markdown("---")
st.markdown("© 2025 生产需求规划系统 | 数据上传与分析模块")