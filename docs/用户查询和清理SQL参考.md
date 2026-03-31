# 鐢ㄦ埛鏌ヨ鍜屾竻鐞?SQL 鍙傝€?
## 馃搳 鏌ヨ宸叉縺娲荤敤鎴?
### 1. 鏌ョ湅鎵€鏈夊凡婵€娲荤敤鎴?
```sql
SELECT 
    id,
    SUBSTRING(openid, 1, 20) as openid,
    nickname,
    invite_code_used,
    DATE_FORMAT(activated_at, '%Y-%m-%d %H:%i') as activated_at,
    DATE_FORMAT(expires_at, '%Y-%m-%d') as expires_at,
    CASE 
        WHEN expires_at IS NULL THEN '姘镐笉杩囨湡'
        WHEN expires_at > NOW() THEN CONCAT('鏈夋晥(杩樺墿', TIMESTAMPDIFF(DAY, NOW(), expires_at), '澶?')
        ELSE '宸茶繃鏈?
    END as status
FROM miniprogram_users 
WHERE is_activated = 1
ORDER BY activated_at DESC;
```

### 2. 鏌ョ湅鏈繃鏈熺殑鐢ㄦ埛

```sql
SELECT 
    id,
    openid,
    nickname,
    invite_code_used,
    expires_at,
    TIMESTAMPDIFF(DAY, NOW(), expires_at) as days_remaining
FROM miniprogram_users 
WHERE is_activated = 1 
  AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY expires_at ASC;
```

### 3. 鏌ョ湅宸茶繃鏈熺殑鐢ㄦ埛

```sql
SELECT 
    id,
    openid,
    nickname,
    invite_code_used,
    expires_at,
    TIMESTAMPDIFF(DAY, expires_at, NOW()) as days_expired
FROM miniprogram_users 
WHERE is_activated = 1 
  AND expires_at IS NOT NULL 
  AND expires_at < NOW()
ORDER BY expires_at DESC;
```

### 4. 鏌ョ湅鍗冲皢杩囨湡鐨勭敤鎴凤紙7澶╁唴锛?
```sql
SELECT 
    id,
    openid,
    nickname,
    invite_code_used,
    expires_at,
    TIMESTAMPDIFF(DAY, NOW(), expires_at) as days_remaining
FROM miniprogram_users 
WHERE is_activated = 1 
  AND expires_at IS NOT NULL 
  AND expires_at > NOW() 
  AND expires_at < DATE_ADD(NOW(), INTERVAL 7 DAY)
ORDER BY expires_at ASC;
```

### 5. 缁熻淇℃伅

```sql
SELECT 
    COUNT(*) as total_activated,
    SUM(CASE WHEN expires_at IS NULL OR expires_at > NOW() THEN 1 ELSE 0 END) as active_users,
    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 ELSE 0 END) as expired_users,
    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at > NOW() AND expires_at < DATE_ADD(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as expiring_soon
FROM miniprogram_users 
WHERE is_activated = 1;
```

### 6. 鎸夋縺娲荤爜鍒嗙粍缁熻

```sql
SELECT 
    invite_code_used as '婵€娲荤爜',
    COUNT(*) as '浣跨敤浜烘暟',
    SUM(CASE WHEN expires_at IS NULL OR expires_at > NOW() THEN 1 ELSE 0 END) as '鏈夋晥鐢ㄦ埛',
    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 ELSE 0 END) as '宸茶繃鏈?
FROM miniprogram_users 
WHERE is_activated = 1 
  AND invite_code_used IS NOT NULL
GROUP BY invite_code_used
ORDER BY COUNT(*) DESC;
```

### 7. 鏌ョ湅闀挎湡鏈櫥褰曠敤鎴凤紙30澶╋級

```sql
SELECT 
    id,
    openid,
    nickname,
    invite_code_used,
    last_login_at,
    TIMESTAMPDIFF(DAY, last_login_at, NOW()) as days_since_login
FROM miniprogram_users 
WHERE is_activated = 1 
  AND last_login_at IS NOT NULL
  AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY last_login_at ASC;
```

---

## 馃棏锔?娓呯悊鐢ㄦ埛锛堣皑鎱庢搷浣滐紒锛?
### 鈿狅笍 璀﹀憡

**鍒犻櫎鎿嶄綔涓嶅彲閫嗭紒鎵ц鍓嶈锛?*
1. 鉁?澶囦唤鏁版嵁搴?2. 鉁?鍏堟墽琛?SELECT 鏌ョ湅灏嗚鍒犻櫎鐨勬暟鎹?3. 鉁?纭鏃犺鍚庡啀鎵ц DELETE

### 1. 娓呯悊宸茶繃鏈熺敤鎴?
```sql
-- 鍏堟煡鐪嬪皢瑕佸垹闄ょ殑鐢ㄦ埛
SELECT 
    id,
    openid,
    invite_code_used,
    expires_at,
    TIMESTAMPDIFF(DAY, expires_at, NOW()) as days_expired
FROM miniprogram_users 
WHERE is_activated = 1 
  AND expires_at IS NOT NULL 
  AND expires_at < NOW();

-- 纭鏃犺鍚庢墽琛屽垹闄?DELETE FROM miniprogram_users 
WHERE is_activated = 1 
  AND expires_at IS NOT NULL 
  AND expires_at < NOW();
```

### 2. 娓呯悊闀挎湡鏈櫥褰曠敤鎴凤紙30澶╋級

```sql
-- 鍏堟煡鐪?SELECT 
    id,
    openid,
    last_login_at,
    TIMESTAMPDIFF(DAY, last_login_at, NOW()) as days_ago
FROM miniprogram_users 
WHERE is_activated = 1 
  AND last_login_at IS NOT NULL
  AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- 鍒犻櫎
DELETE FROM miniprogram_users 
WHERE is_activated = 1 
  AND last_login_at IS NOT NULL
  AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### 3. 娓呯悊娴嬭瘯鐢ㄦ埛

```sql
-- 鍏堟煡鐪?SELECT * FROM miniprogram_users 
WHERE openid LIKE '%test%' OR openid LIKE '%Test%';

-- 鍒犻櫎
DELETE FROM miniprogram_users 
WHERE openid LIKE '%test%' OR openid LIKE '%Test%';
```

### 4. 娓呯悊鐗瑰畾鐢ㄦ埛

```sql
-- 鍒犻櫎鎸囧畾鐢ㄦ埛ID
DELETE FROM miniprogram_users WHERE id = 123;

-- 鍒犻櫎鎸囧畾OpenID
DELETE FROM miniprogram_users WHERE openid = 'oQUNz5...';
```

### 5. 娓呯悊鏈縺娲荤敤鎴凤紙鍙€夛級

```sql
-- 娓呯悊娉ㄥ唽浣嗘湭婵€娲荤殑鐢ㄦ埛锛堣秴杩?澶╋級
DELETE FROM miniprogram_users 
WHERE is_activated = 0 
  AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY);
```

### 6. 娓呯悊鎵€鏈夌敤鎴凤紙鏋佸害鍗遍櫓锛侊級

```sql
-- 鈿狅笍鈿狅笍鈿狅笍 鏋佸害鍗遍櫓锛佷細鍒犻櫎鎵€鏈夌敤鎴锋暟鎹紒鈿狅笍鈿狅笍鈿狅笍
-- 鎵ц鍓嶅繀椤诲浠斤紒

-- 鍏堝浠?mysqldump -u root -p'<MYSQL_PASSWORD>' oddsmind miniprogram_users > backup_all_users_$(date +%Y%m%d_%H%M%S).sql

-- 鏌ョ湅鎵€鏈夌敤鎴?SELECT COUNT(*) as total FROM miniprogram_users;

-- 纭鍚庡垹闄わ紙涓嶅彲閫嗭紒锛?DELETE FROM miniprogram_users;
```

**鈿狅笍 寮虹儓寤鸿浣跨敤鑴氭湰锛?*
```bash
bash scripts/cleanup_expired_users.sh
# 閫夋嫨 6) 娓呯悊鎵€鏈夌敤鎴?# 鑴氭湰浼氳嚜鍔ㄥ浠藉苟闇€瑕佷笁閲嶇‘璁?```

---

## 馃摝 澶囦唤鐢ㄦ埛鏁版嵁

### 澶囦唤鎵€鏈夌敤鎴?
```bash
mysqldump -u root -p'<MYSQL_PASSWORD>' oddsmind miniprogram_users > backup_users_$(date +%Y%m%d).sql
```

### 澶囦唤宸叉縺娲荤敤鎴?
```bash
mysqldump -u root -p'<MYSQL_PASSWORD>' oddsmind miniprogram_users \
  --where="is_activated = 1" > backup_activated_users_$(date +%Y%m%d).sql
```

### 澶囦唤鍗冲皢鍒犻櫎鐨勭敤鎴凤紙娓呯悊鍓嶏級

```bash
mysqldump -u root -p'<MYSQL_PASSWORD>' oddsmind miniprogram_users \
  --where="is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW()" \
  > backup_expired_users_$(date +%Y%m%d_%H%M%S).sql
```

---

## 馃攳 甯哥敤鏌ヨ

### 鏌ョ湅鐢ㄦ埛鎬绘暟

```sql
SELECT 
    COUNT(*) as total_users,
    SUM(CASE WHEN is_activated = 1 THEN 1 ELSE 0 END) as activated_users,
    SUM(CASE WHEN is_activated = 0 THEN 1 ELSE 0 END) as unactivated_users
FROM miniprogram_users;
```

### 鏌ョ湅鏈€杩戞縺娲荤殑鐢ㄦ埛

```sql
SELECT 
    id,
    openid,
    invite_code_used,
    activated_at
FROM miniprogram_users 
WHERE is_activated = 1
ORDER BY activated_at DESC
LIMIT 10;
```

### 鏌ョ湅鏈€杩戠櫥褰曠殑鐢ㄦ埛

```sql
SELECT 
    id,
    openid,
    nickname,
    last_login_at
FROM miniprogram_users 
WHERE is_activated = 1
  AND last_login_at IS NOT NULL
ORDER BY last_login_at DESC
LIMIT 10;
```

### 鏌ョ湅浣跨敤鏌愪釜婵€娲荤爜鐨勬墍鏈夌敤鎴?
```sql
SELECT 
    id,
    openid,
    nickname,
    activated_at,
    expires_at
FROM miniprogram_users 
WHERE invite_code_used = 'TEST1D'
ORDER BY activated_at DESC;
```

---

## 馃搳 鏁版嵁琛ㄧ粨鏋?
### miniprogram_users 琛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | INT | 鐢ㄦ埛ID锛堜富閿級 |
| openid | VARCHAR(128) | 寰俊OpenID锛堝敮涓€锛?|
| unionid | VARCHAR(128) | 寰俊UnionID锛堝彲閫夛級 |
| nickname | VARCHAR(100) | 鐢ㄦ埛鏄电О |
| avatar_url | TEXT | 澶村儚URL |
| is_activated | TINYINT(1) | 鏄惁宸叉縺娲?|
| activated_at | DATETIME | 婵€娲绘椂闂?|
| expires_at | DATETIME | 璐﹀彿杩囨湡鏃堕棿 |
| invite_code_used | VARCHAR(50) | 浣跨敤鐨勬縺娲荤爜 |
| last_login_at | DATETIME | 鏈€鍚庣櫥褰曟椂闂?|
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |
| updated_at | TIMESTAMP | 鏇存柊鏃堕棿 |

---

## 馃洜锔?浣跨敤鑴氭湰锛堟帹鑽愶級

### 鏌ョ湅宸叉縺娲荤敤鎴?
```bash
bash scripts/list_activated_users.sh
```

### 鏌ョ湅鐢ㄦ埛璇︽儏

```bash
bash scripts/check_user.sh <鐢ㄦ埛ID鎴朞penID>
```

### 娓呯悊杩囨湡鐢ㄦ埛

```bash
bash scripts/cleanup_expired_users.sh
```

---

## 鈿狅笍 娉ㄦ剰浜嬮」

1. **鍒犻櫎鍓嶅繀椤诲浠?*
2. **鍏堥瑙堝啀鍒犻櫎**锛堜娇鐢?SELECT锛?3. **璋ㄦ厧娓呯悊闀挎湡鏈櫥褰曠敤鎴?*锛堝彲鑳芥槸鐪熷疄鐢ㄦ埛锛?4. **娴嬭瘯鐢ㄦ埛鍙互瀹夊叏鍒犻櫎**
5. **宸茶繃鏈熺敤鎴峰缓璁繚鐣欎竴娈垫椂闂?*锛堝30澶╋級鍐嶅垹闄?
---

**鏇存柊鏃堕棿锛?* 2025-11-16


