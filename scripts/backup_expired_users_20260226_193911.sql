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
) ENGINE=InnoDB AUTO_INCREMENT=1316 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `miniprogram_users`
--
-- WHERE:  is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW()

LOCK TABLES `miniprogram_users` WRITE;
/*!40000 ALTER TABLE `miniprogram_users` DISABLE KEYS */;
INSERT INTO `miniprogram_users` VALUES (916,'oQUNz5aes1r4K_QCtLChoFQWmL5k',NULL,NULL,NULL,1,'2026-01-25 23:02:17','2026-02-24 23:02:17','HX1GPHE5','2026-02-24 20:04:33','2026-01-25 08:09:51','2026-02-24 12:04:33'),(1183,'oQUNz5YRF2SywCUdJPXqeaxT25Z8',NULL,NULL,NULL,1,'2026-02-10 18:19:17','2026-02-25 18:19:17','KHUH6EM4','2026-02-23 03:33:10','2026-02-10 09:23:49','2026-02-22 19:33:10'),(1305,'oQUNz5V0l94tlwV8WSYigWJH-olE',NULL,NULL,NULL,1,'2026-02-24 20:13:22','2026-02-25 20:13:23','5LRPETJ1','2026-02-25 18:52:54','2026-02-24 12:13:03','2026-02-25 10:52:54'),(944,'oQUNz5VXqSRorcM2lxbCR07p04LE',NULL,NULL,NULL,1,'2026-01-27 11:03:28','2026-02-26 11:03:29','M69NPF3B','2026-02-22 08:47:46','2026-01-27 02:59:10','2026-02-22 00:47:46');
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

-- Dump completed on 2026-02-26 19:39:11
