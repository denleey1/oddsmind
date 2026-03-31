-- MySQL dump 10.13  Distrib 8.0.44, for Linux (x86_64)
--
-- Host: localhost    Database: oddsmind
-- ------------------------------------------------------
-- Server version	8.0.44-0ubuntu0.22.04.2

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `miniprogram_users`
--

DROP TABLE IF EXISTS `miniprogram_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `miniprogram_users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `openid` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '微信OpenID',
  `unionid` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '微信UnionID（可选）',
  `nickname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户昵称',
  `avatar_url` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '头像URL',
  `is_activated` tinyint(1) DEFAULT '0' COMMENT '是否已激活',
  `activated_at` datetime DEFAULT NULL COMMENT '激活时间',
  `expires_at` datetime DEFAULT NULL COMMENT '账号过期时间',
  `invite_code_used` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '使用的邀请码',
  `last_login_at` datetime DEFAULT NULL COMMENT '最后登录时间',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `openid` (`openid`),
  KEY `idx_openid` (`openid`),
  KEY `idx_activated` (`is_activated`),
  KEY `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB AUTO_INCREMENT=1279 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `miniprogram_users`
--
-- WHERE:  is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW()

LOCK TABLES `miniprogram_users` WRITE;
/*!40000 ALTER TABLE `miniprogram_users` DISABLE KEYS */;
INSERT INTO `miniprogram_users` VALUES (721,'oQUNz5evK8UaFwHFucf4v-HSfcUI',NULL,NULL,NULL,1,'2026-01-18 12:03:26','2026-02-17 12:03:26','BKTYFB9N','2026-02-14 11:04:04','2026-01-18 03:49:33','2026-02-14 03:04:04'),(727,'oQUNz5UIUnDfwZIYnnneH3uURiF4',NULL,NULL,NULL,1,'2026-01-18 17:10:29','2026-02-17 17:10:29','RQV1FS93','2026-02-16 19:53:47','2026-01-18 09:10:23','2026-02-16 11:53:47'),(737,'oQUNz5VE-m29QEzpNoQ7NkEOkQvA',NULL,NULL,NULL,1,'2026-01-18 20:33:36','2026-02-17 20:33:36','6BSMVI6U','2026-02-13 23:20:12','2026-01-18 12:33:31','2026-02-13 15:20:12'),(750,'oQUNz5bOYuvd3c5NNMg6oJ_UEzfY',NULL,NULL,NULL,1,'2026-01-19 15:57:43','2026-02-18 15:57:44','U3HNS47F','2026-02-17 21:23:24','2026-01-19 07:57:40','2026-02-17 13:23:24'),(759,'oQUNz5VX9Dn7By_1w1M0B99uodrE',NULL,NULL,NULL,1,'2026-01-19 19:29:12','2026-02-18 19:29:12','BNB4C9LG','2026-02-13 14:07:37','2026-01-19 10:12:45','2026-02-13 06:07:37'),(787,'oQUNz5dpzc-QI2fUo_kKPkL89gJk',NULL,NULL,NULL,1,'2026-01-20 11:40:46','2026-02-19 11:40:47','X6888ZHV','2026-02-18 22:46:54','2026-01-20 03:39:46','2026-02-18 14:46:54');
/*!40000 ALTER TABLE `miniprogram_users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-19 19:59:25
