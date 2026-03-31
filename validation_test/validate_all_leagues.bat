@echo off
echo ========================================
echo 七大联赛验证批量执行脚本
echo ========================================
echo.

echo 开始验证德甲...
python bundesliga_validator.py
echo 德甲验证完成
echo.

echo 开始验证法甲...
python ligue1_validator.py
echo 法甲验证完成
echo.

echo 开始验证韩国K联赛...
python kleague_validator.py
echo 韩国K联赛验证完成
echo.

echo 开始验证日职联...
python jleague_validator.py
echo 日职联验证完成
echo.

echo 开始验证西甲...
python laliga_validator.py
echo 西甲验证完成
echo.

echo 开始验证意甲...
python seriea_validator.py
echo 意甲验证完成
echo.

echo 开始验证英超...
python premier_validator.py
echo 英超验证完成
echo.

echo ========================================
echo 所有联赛验证完成！
echo ========================================
pause
