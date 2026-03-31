#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动备份脚本
支持数据库备份和应用文件备份，可传输到指定位置
每天凌晨4点自动执行（通过cron）
"""

import os
import sys
import subprocess
import shutil
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import tarfile

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from database.connection import get_connection
    from core.logger import get_logger
except ImportError:
    # 如果导入失败，使用简单的日志
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
else:
    logger = get_logger(__name__)


class BackupManager:
    """备份管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化备份管理器
        
        Args:
            config_file: 配置文件路径，默认使用 scripts/backup_config.json
        """
        self.project_root = PROJECT_ROOT
        self.config_file = config_file or (self.project_root / "scripts" / "backup_config.json")
        self.config = self._load_config()
        
        # 备份目录
        self.backup_dir = Path(self.config.get("backup_dir", "backups"))
        if not self.backup_dir.is_absolute():
            self.backup_dir = self.project_root / self.backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志目录
        self.log_dir = self.backup_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # 获取数据库配置
        self.db_config = self._get_database_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "backup_dir": "backups",
            "backup_database": True,
            "backup_app_files": True,
            "app_files_to_backup": [
                "config",
                "core",
                "application",
                "database",
                "oddsmind.env",
                "requirements.txt"
            ],
            "app_files_to_exclude": [
                "__pycache__",
                "*.pyc",
                "*.pyo",
                ".git",
                "venv",
                "node_modules",
                "logs",
                "backups",
                "data/checkpoints",
                "*.log"
            ],
            "compress_backup": True,
            "keep_days": 30,
            "transfer": {
                "enabled": False,
                "type": "local",  # local, remote, s3
                "destination": ""
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
                logger.info(f"✅ 已加载配置文件: {self.config_file}")
            except Exception as e:
                logger.warning(f"⚠️ 配置文件加载失败，使用默认配置: {e}")
        else:
            logger.info("📝 使用默认配置，建议创建配置文件: scripts/backup_config.json")
        
        return default_config
    
    def _get_database_config(self) -> Dict[str, str]:
        """获取数据库配置"""
        config = {}
        
        # 从环境变量读取
        config['host'] = os.getenv("MYSQL_HOST", "localhost")
        config['port'] = os.getenv("MYSQL_PORT", "3306")
        config['user'] = os.getenv("MYSQL_USER", "root")
        config['password'] = os.getenv("MYSQL_PASSWORD", "")
        config['database'] = os.getenv("MYSQL_DATABASE", "oddsmind")
        
        # 如果环境变量没有，尝试从数据库连接获取
        if not config['password']:
            try:
                from database.connection import get_connection
                db = get_connection()
                if hasattr(db, 'config'):
                    config.update(db.config)
            except Exception as e:
                logger.warning(f"无法从数据库连接获取配置: {e}")
        
        return config
    
    def backup_database(self) -> Optional[Path]:
        """
        备份数据库
        
        Returns:
            备份文件路径，失败返回None
        """
        if not self.config.get("backup_database", True):
            logger.info("⏭️ 数据库备份已禁用")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"database_{timestamp}.sql"
        
        logger.info(f"🗄️ 开始备份数据库: {self.db_config['database']}")
        logger.info(f"   目标文件: {backup_file}")
        
        # 构建mysqldump命令
        # 注意：密码参数需要单独传递，避免在命令行中暴露
        cmd = [
            "mysqldump",
            f"-h{self.db_config['host']}",
            f"-P{self.db_config['port']}",
            f"-u{self.db_config['user']}",
            f"-p{self.db_config['password']}" if self.db_config['password'] else "",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--set-gtid-purged=OFF",
            "--default-character-set=utf8mb4",
            self.db_config['database']
        ]
        # 移除空字符串参数
        cmd = [arg for arg in cmd if arg]
        
        try:
            with open(backup_file, 'wb') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    check=False
                )
            
            if result.returncode == 0:
                file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"✅ 数据库备份成功!")
                logger.info(f"   文件: {backup_file}")
                logger.info(f"   大小: {file_size:.2f} MB")
                
                # 如果需要压缩
                if self.config.get("compress_backup", True):
                    compressed_file = self._compress_file(backup_file)
                    if compressed_file:
                        backup_file.unlink()  # 删除未压缩文件
                        backup_file = compressed_file
                        logger.info(f"✅ 已压缩备份文件: {backup_file}")
                
                return backup_file
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"❌ 数据库备份失败: {error_msg}")
                if backup_file.exists():
                    backup_file.unlink()
                return None
                
        except FileNotFoundError:
            logger.error("❌ mysqldump 命令未找到，请确保MySQL客户端已安装")
            return None
        except Exception as e:
            logger.error(f"❌ 数据库备份异常: {e}")
            if backup_file.exists():
                backup_file.unlink()
            return None
    
    def backup_app_files(self) -> Optional[Path]:
        """
        备份应用文件
        
        Returns:
            备份文件路径，失败返回None
        """
        if not self.config.get("backup_app_files", True):
            logger.info("⏭️ 应用文件备份已禁用")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"app_files_{timestamp}.tar.gz"
        
        logger.info(f"📦 开始备份应用文件")
        logger.info(f"   目标文件: {backup_file}")
        
        files_to_backup = self.config.get("app_files_to_backup", [])
        files_to_exclude = self.config.get("app_files_to_exclude", [])
        
        try:
            with tarfile.open(backup_file, 'w:gz') as tar:
                for item in files_to_backup:
                    item_path = self.project_root / item
                    if item_path.exists():
                        # 检查是否在排除列表中
                        should_exclude = False
                        for exclude_pattern in files_to_exclude:
                            if exclude_pattern in str(item_path):
                                should_exclude = True
                                break
                        
                        if not should_exclude:
                            logger.info(f"   添加: {item}")
                            tar.add(item_path, arcname=item, recursive=True)
                        else:
                            logger.debug(f"   跳过（排除）: {item}")
                    else:
                        logger.warning(f"⚠️ 文件/目录不存在: {item}")
            
            file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"✅ 应用文件备份成功!")
            logger.info(f"   文件: {backup_file}")
            logger.info(f"   大小: {file_size:.2f} MB")
            
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ 应用文件备份异常: {e}")
            if backup_file.exists():
                backup_file.unlink()
            return None
    
    def _compress_file(self, file_path: Path) -> Optional[Path]:
        """压缩文件"""
        compressed_file = file_path.with_suffix(file_path.suffix + '.gz')
        
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return compressed_file
        except Exception as e:
            logger.error(f"压缩文件失败: {e}")
            return None
    
    def transfer_backup(self, backup_files: List[Path]) -> bool:
        """
        传输备份文件到指定位置
        
        Args:
            backup_files: 备份文件列表
            
        Returns:
            是否成功
        """
        transfer_config = self.config.get("transfer", {})
        
        if not transfer_config.get("enabled", False):
            logger.info("⏭️ 备份传输已禁用")
            return True
        
        transfer_type = transfer_config.get("type", "local")
        destination = transfer_config.get("destination", "")
        
        if not destination:
            logger.warning("⚠️ 传输目标未配置，跳过传输")
            return False
        
        logger.info(f"📤 开始传输备份文件到: {destination} (类型: {transfer_type})")
        
        try:
            if transfer_type == "local":
                return self._transfer_to_local(backup_files, destination)
            elif transfer_type == "remote":
                return self._transfer_to_remote(backup_files, destination, transfer_config)
            elif transfer_type == "s3":
                return self._transfer_to_s3(backup_files, destination, transfer_config)
            else:
                logger.error(f"❌ 不支持的传输类型: {transfer_type}")
                return False
        except Exception as e:
            logger.error(f"❌ 传输备份文件失败: {e}")
            return False
    
    def _transfer_to_local(self, backup_files: List[Path], destination: str) -> bool:
        """传输到本地目录"""
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        for backup_file in backup_files:
            try:
                dest_file = dest_path / backup_file.name
                shutil.copy2(backup_file, dest_file)
                logger.info(f"✅ 已复制到本地: {dest_file}")
            except Exception as e:
                logger.error(f"❌ 复制文件失败 {backup_file}: {e}")
                return False
        
        return True
    
    def _transfer_to_remote(self, backup_files: List[Path], destination: str, config: Dict) -> bool:
        """传输到远程服务器（使用rsync或scp，支持密码认证）"""
        # 解析目标：user@host:/path
        if '@' not in destination or ':' not in destination:
            logger.error("❌ 远程目标格式错误，应为: user@host:/path")
            return False
        
        user_host, remote_path = destination.rsplit(':', 1)
        
        # 获取密码（如果配置了）
        password = config.get("password") or os.getenv("BACKUP_REMOTE_PASSWORD")
        use_password = bool(password)
        
        # 使用rsync（如果可用）
        if shutil.which('rsync'):
            for backup_file in backup_files:
                if use_password and shutil.which('sshpass'):
                    # 使用sshpass传递密码
                    cmd = [
                        "sshpass",
                        "-p", password,
                        "rsync",
                        "-avz",
                        "--progress",
                        "-e", "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                        str(backup_file),
                        f"{user_host}:{remote_path}/"
                    ]
                else:
                    cmd = [
                        "rsync",
                        "-avz",
                        "--progress",
                        "-e", "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                        str(backup_file),
                        f"{user_host}:{remote_path}/"
                    ]
                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE
                    )
                    logger.info(f"✅ 已传输到远程: {user_host}:{remote_path}/{backup_file.name}")
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
                    logger.error(f"❌ rsync传输失败: {error_msg}")
                    if use_password and 'sshpass' not in error_msg:
                        logger.warning("💡 提示: 如果使用密码认证，请安装sshpass: sudo apt-get install sshpass")
                    return False
        else:
            # 使用scp
            for backup_file in backup_files:
                if use_password and shutil.which('sshpass'):
                    # 使用sshpass传递密码
                    cmd = [
                        "sshpass",
                        "-p", password,
                        "scp",
                        "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        str(backup_file),
                        f"{user_host}:{remote_path}/"
                    ]
                else:
                    cmd = [
                        "scp",
                        "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        str(backup_file),
                        f"{user_host}:{remote_path}/"
                    ]
                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE
                    )
                    logger.info(f"✅ 已传输到远程: {user_host}:{remote_path}/{backup_file.name}")
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
                    logger.error(f"❌ scp传输失败: {error_msg}")
                    if use_password and 'sshpass' not in error_msg:
                        logger.warning("💡 提示: 如果使用密码认证，请安装sshpass: sudo apt-get install sshpass")
                    return False
        
        return True
    
    def _transfer_to_s3(self, backup_files: List[Path], destination: str, config: Dict) -> bool:
        """传输到S3（需要boto3）"""
        try:
            import boto3
        except ImportError:
            logger.error("❌ boto3未安装，无法传输到S3。请运行: pip install boto3")
            return False
        
        # 解析S3路径：s3://bucket/path
        if not destination.startswith("s3://"):
            logger.error("❌ S3路径格式错误，应为: s3://bucket/path")
            return False
        
        s3_path = destination[5:]  # 移除 s3://
        if '/' in s3_path:
            bucket, prefix = s3_path.split('/', 1)
        else:
            bucket = s3_path
            prefix = ""
        
        # 获取AWS凭证
        aws_access_key = config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = config.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = config.get("aws_region") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if not aws_access_key or not aws_secret_key:
            logger.error("❌ AWS凭证未配置")
            return False
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        for backup_file in backup_files:
            try:
                s3_key = f"{prefix}/{backup_file.name}" if prefix else backup_file.name
                s3_client.upload_file(str(backup_file), bucket, s3_key)
                logger.info(f"✅ 已上传到S3: s3://{bucket}/{s3_key}")
            except Exception as e:
                logger.error(f"❌ S3上传失败 {backup_file}: {e}")
                return False
        
        return True
    
    def cleanup_old_backups(self) -> int:
        """
        清理旧备份文件
        
        Returns:
            删除的文件数量
        """
        keep_days = self.config.get("keep_days", 30)
        logger.info(f"🧹 清理 {keep_days} 天前的备份文件...")
        
        current_time = datetime.now()
        removed_count = 0
        cutoff_time = current_time - timedelta(days=keep_days)
        
        for backup_file in self.backup_dir.glob("*"):
            if backup_file.is_file() and backup_file.suffix in ['.sql', '.gz', '.tar.gz']:
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                if file_time < cutoff_time:
                    try:
                        backup_file.unlink()
                        removed_count += 1
                        logger.info(f"   删除旧备份: {backup_file.name} (已存在 {(current_time - file_time).days} 天)")
                    except Exception as e:
                        logger.warning(f"   删除文件失败 {backup_file.name}: {e}")
        
        if removed_count > 0:
            logger.info(f"✅ 已清理 {removed_count} 个旧备份文件")
        else:
            logger.info("✅ 没有需要清理的旧备份文件")
        
        return removed_count
    
    def run_backup(self) -> bool:
        """
        执行完整备份流程
        
        Returns:
            是否成功
        """
        logger.info("=" * 60)
        logger.info("🚀 开始自动备份任务")
        logger.info(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        backup_files = []
        
        # 备份数据库
        db_backup = self.backup_database()
        if db_backup:
            backup_files.append(db_backup)
        
        # 备份应用文件
        app_backup = self.backup_app_files()
        if app_backup:
            backup_files.append(app_backup)
        
        if not backup_files:
            logger.error("❌ 没有生成任何备份文件")
            return False
        
        # 传输备份
        transfer_success = self.transfer_backup(backup_files)
        
        # 清理旧备份
        self.cleanup_old_backups()
        
        logger.info("=" * 60)
        logger.info("✅ 备份任务完成!")
        logger.info(f"   生成备份文件: {len(backup_files)} 个")
        logger.info(f"   传输状态: {'成功' if transfer_success else '失败'}")
        logger.info("=" * 60)
        
        return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OddsMind 自动备份工具")
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径（默认: scripts/backup_config.json）"
    )
    parser.add_argument(
        "--database-only",
        action="store_true",
        help="仅备份数据库"
    )
    parser.add_argument(
        "--app-only",
        action="store_true",
        help="仅备份应用文件"
    )
    
    args = parser.parse_args()
    
    # 创建备份管理器
    manager = BackupManager(config_file=args.config)
    
    # 根据参数调整配置
    if args.database_only:
        manager.config["backup_app_files"] = False
    if args.app_only:
        manager.config["backup_database"] = False
    
    # 执行备份
    success = manager.run_backup()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

