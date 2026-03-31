# 澳超赔率问题修复记录 - 2025-12-27

## 问题描述

澳超比赛（如 match_id: 2871705）在分析页面没有显示赔率数据。

## 问题原因

**位置：** `odds_analysis/main_analyzer.py` (第95-96行)

**错误：**
```python
round_number = match_info.get('round_number')
if round_number <= 4:  # ❌ 错误：round_number 可能为 None
    # ...
```

**问题分析：**
1. `match_info.get('round_number')` 可能返回 `None`
2. 直接比较 `None <= 4` 会导致 `TypeError: '<=' not supported between instances of 'NoneType' and 'int'`
3. 当 `round_number` 为 `None` 时，代码抛出异常，导致赔率分析失败

## 解决方案

**修复代码：**
```python
round_number = match_info.get('round_number')
if round_number is not None and round_number <= 4:  # ✅ 正确：先检查 None
    self.logger.warning(f"联赛初期 (第 {round_number} 轮): 公司 {company_id} 缺少广义实力数据，使用默认值继续分析。")
    # 提供安全的默认值
    odds_with_power[company_id].update({
        'home_power': None,
        'away_power': None,
        'power_diff': 0.0
    })
else:
    # 如果不是联赛初期或 round_number 为 None，则跳过这家公司
    self.logger.warning(f"非联赛初期 (第 {round_number} 轮): 公司 {company_id} 缺少广义实力数据，跳过分析。")
    del odds_with_power[company_id]
```

**修复内容：**
1. 添加 `None` 检查：`if round_number is not None and round_number <= 4`
2. 修复代码缩进问题，确保逻辑正确

## 修复效果

- ✅ 修复了 `TypeError` 异常
- ✅ 当 `round_number` 为 `None` 时，正确处理（跳过分析）
- ✅ 当 `round_number <= 4` 时，使用默认值继续分析
- ✅ 确保澳超等联赛的赔率数据能正常显示

## 测试验证

**测试用例：** match_id 2871705 (澳超比赛)

**修复前：**
- 抛出 `TypeError` 异常
- 赔率分析失败
- 分析页面无赔率数据

**修复后：**
- 正常处理 `round_number` 为 `None` 的情况
- 赔率分析成功
- 分析页面正常显示赔率数据

## 修改文件

- `odds_analysis/main_analyzer.py` (第95-107行)

## 注意事项

1. 当 `round_number` 为 `None` 时，会跳过该公司的分析（因为无法判断是否为联赛初期）
2. 如果希望处理 `round_number` 为 `None` 的情况，可以考虑：
   - 使用默认值（如假设为联赛初期）
   - 或者从其他数据源获取轮次信息

---

**修复日期：** 2025-12-27  
**修复人员：** AI Assistant  
**状态：** ✅ 已修复并重启应用
















