import requests
import logging
import time
import traceback

class MatchDataFetcher:
    """比赛数据抓取类"""
    
    def __init__(self):
        """初始化数据抓取器"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://zq.titan007.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Accept-Encoding': 'gzip, deflate, br',
            'sec-ch-ua': '"Chromium";v="122", "Google Chrome";v="122", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        self.session = requests.Session()
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(self.session)
        except ImportError:
            pass
        
    def fetch_match_analysis(self, match_id, callback_progress=None):
        """
        从球探网爬取比赛分析数据
        
        Args:
            match_id: 比赛ID
            callback_progress: 进度回调函数
            
        Returns:
            str: 成功返回HTML内容，失败返回None
        """
        try:
            # 构建URL
            url = f"https://zq.titan007.com/analysis/{match_id}cn.htm"
            
            # 先访问主页获取cookies
            try:
                logging.info("访问主页获取cookies")
                self.session.get('https://zq.titan007.com/', headers=self.headers, timeout=10)
            except Exception as e:
                logging.warning(f"访问主页获取cookies失败: {e}")
                # 继续执行，这不是致命错误
                
            # 添加重试逻辑
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    logging.info(f"尝试第 {retry_count+1} 次请求: {url}")
                    
                    # 进度回调
                    if callback_progress:
                        callback_progress(f"正在获取数据，尝试第 {retry_count+1} 次请求...")
                        
                    response = self.session.get(url, headers=self.headers, timeout=30)
                    
                    # 检查响应状态
                    if response.status_code == 200:
                        logging.info("请求成功，获取数据")
                        
                        # 尝试多种编码方式
                        html_content = self._decode_response(response)
                        
                        if html_content:
                            # 将HTML保存到文件以便调试
                            self._save_html_response(html_content)
                            return html_content
                        else:
                            logging.error("无法正确解码HTML内容")
                            retry_count += 1
                    else:
                        logging.error(f"请求失败，状态码: {response.status_code}，尝试重试...")
                        retry_count += 1
                        
                    # 添加延迟，避免频繁请求
                    time.sleep(2 * retry_count)
                    
                except requests.RequestException as e:
                    logging.error(f"请求异常: {e}")
                    retry_count += 1
                    time.sleep(2 * retry_count)
                    
            # 如果所有重试都失败
            error_msg = f"经过 {max_retries} 次尝试，仍然无法获取数据。请检查网络连接或稍后再试。"
            logging.error(error_msg)
            
            # 进度回调
            if callback_progress:
                callback_progress(f"获取失败: {error_msg}")
                
            return None
            
        except Exception as e:
            logging.error(f"爬取分析数据出错: {e}")
            logging.error(traceback.format_exc())
            return None
            
    def _decode_response(self, response):
        """
        尝试多种编码方式解码响应内容
        
        Args:
            response: 请求响应对象
            
        Returns:
            str: 解码后的HTML内容，解码失败则返回None
        """
        # 直接尝试GBK编码（球探网通常使用）
        try:
            content = response.content.decode('gbk')
            logging.info("成功使用GBK编码解码响应")
            return content
        except UnicodeDecodeError:
            pass
            
        # 尝试其他中文编码
        encodings = ['gb2312', 'gb18030', 'utf-8']
        for encoding in encodings:
            try:
                content = response.content.decode(encoding)
                logging.info(f"成功使用 {encoding} 解码响应")
                return content
            except UnicodeDecodeError:
                continue
                
        # 使用apparent_encoding作为最后尝试
        try:
            response.encoding = response.apparent_encoding
            content = response.text
            logging.info(f"使用自动检测的编码: {response.encoding}")
            return content
        except Exception:
            pass
            
        # 最后使用替换模式
        try:
            content = response.content.decode('utf-8', errors='replace')
            logging.warning("使用替换错误的方式解码响应")
            return content
        except Exception as e:
            logging.error(f"所有解码尝试均失败: {e}")
            return None
            
    def _save_html_response(self, html_content):
        """
        保存HTML响应到文件，用于调试
        
        Args:
            html_content: HTML内容
        """
        try:
            with open("logs/html_response.txt", "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("已保存HTML响应到logs/html_response.txt文件")
        except Exception as e:
            logging.error(f"保存HTML响应失败: {e}") 