@echo off
echo 正在安装生产需求规划系统所需的依赖库...
echo 这可能需要几分钟时间，请耐心等待...

pip install -r requirements.txt

echo.
echo 依赖库安装完成！
echo 现在您可以运行"启动应用.bat"来启动应用程序。
echo.
pause