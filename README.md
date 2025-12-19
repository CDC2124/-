# 生产需求规划系统

## 系统概述

生产需求规划系统是一个基于Python和Streamlit开发的综合性生产计划管理应用，旨在帮助制造企业基于历史出货数据生成月度销售预测、优化生产计划和计算原材料需求计划(MRP)。该系统采用模块化设计，集成了多种预测算法和优化技术，为制造企业提供端到端的生产规划解决方案。

## 系统功能

1. **数据分析与预处理**：处理历史出货数据，执行数据清洗、验证和转换
2. **销售预测**：使用多种算法生成月度销售预测
3. **生产计划优化**：基于销售预测生成优化的生产计划
4. **物料清单(BOM)管理**：管理产品的物料清单结构
5. **原材料需求计划(MRP)**：计算原材料需求和生成采购计划
6. **预测分析报告**：分析预测准确性并生成报告

## 安装与运行

### 系统要求

- Python 3.8或更高版本
- 所需Python库：streamlit, pandas, numpy, matplotlib, seaborn, statsmodels, plotly, openpyxl, xlsxwriter, networkx

### 运行方法

1. **使用启动脚本**：
   - 双击`启动应用.bat`文件即可启动应用程序

2. **手动启动**：
   - 打开命令提示符
   - 进入`production_planning_system`目录
   - 运行命令：`streamlit run app.py`

### 访问应用

应用启动后，可以通过浏览器访问以下地址：
- 本地访问：http://localhost:8501

## 示例数据

系统提供了一套完整的示例数据，包括：

1. **历史出货数据**：`data/samples/example_shipment_data.csv`
2. **BOM清单数据**：`data/samples/example_bom_data.csv`
3. **库存数据**：`data/samples/example_inventory_data.csv`
4. **供应商数据**：`data/samples/example_supplier_data.csv`
5. **产能数据**：`data/samples/example_capacity_data.csv`
6. **销售预测数据**：`data/samples/example_forecast_data.csv`
7. **生产计划数据**：`data/samples/example_production_plan.csv`
8. **MRP计划数据**：`data/samples/example_mrp_plan.csv`

在各功能页面中选择"使用示例数据"选项即可加载这些示例数据。

## 使用流程

1. 上传历史出货数据并进行分析
2. 生成销售预测并根据需要调整
3. 基于预测生成生产计划
4. 上传和管理BOM清单
5. 生成原材料需求计划
6. 分析预测准确性并生成报告

## 文件结构

- `production_planning_system/`: 主应用程序目录
  - `app.py`: 应用程序入口
  - `models/`: 业务逻辑模块
  - `pages/`: 应用页面
  - `data/`: 数据目录
    - `samples/`: 示例数据
    - `user_uploads/`: 用户上传数据
  - `utils/`: 工具函数
- `plans/`: 系统设计文档
- `requirements.txt`: 依赖库列表
- `启动应用.bat`: 启动脚本

## 故障排除

如果应用程序无法正常启动或运行，请检查：

1. Python版本是否为3.8或更高
2. 是否已安装所有必要的依赖库
3. 是否有足够的系统权限运行应用程序

如果遇到matplotlib相关错误，请确保已正确安装matplotlib库：
```
pip install matplotlib
```

## 联系与支持

如有任何问题或需要技术支持，请联系：
- 📧 prodplanning@example.com