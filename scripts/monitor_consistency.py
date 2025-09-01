#!/usr/bin/env python3
"""
生产环境一致性监控脚本
定期检查所有Service的并行测试统计，生成监控报告
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import os
import sys

# 添加项目路径
sys.path.append('/home/tg_bot_picture_v1')

# 🔧 加载.env文件
from dotenv import load_dotenv
load_dotenv('/home/tg_bot_picture_v1/.env')

from src.core.container import setup_container
from src.utils.config.settings import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/consistency_monitor.log'),
        logging.StreamHandler()
    ]
)

class ConsistencyMonitor:
    """一致性监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.container = None
        self.services = [
            'action_record_service',
            'user_service',
            'image_service', 
            'payment_service',
            'session_service'
        ]
    
    async def initialize(self):
        """初始化监控器"""
        try:
            settings = get_settings()
            self.container = setup_container(settings)
            
            # 初始化数据库
            db_manager = self.container.get("database_manager")
            await db_manager.initialize()
            
            self.logger.info("一致性监控器初始化完成")
        except Exception as e:
            self.logger.error(f"监控器初始化失败: {e}")
            raise
    
    def get_service_stats(self) -> Dict[str, Any]:
        """获取所有Service的测试统计"""
        stats = {}
        
        for service_name in self.services:
            try:
                service = self.container.get(service_name)
                if hasattr(service, 'get_test_stats'):
                    service_stats = service.get_test_stats()
                    if service_stats:  # 只记录启用了parallel_test的Service
                        stats[service_name] = service_stats
            except Exception as e:
                self.logger.error(f"获取{service_name}统计失败: {e}")
                stats[service_name] = {"error": str(e)}
        
        return stats
    
    def calculate_overall_consistency(self, stats: Dict[str, Any]) -> Dict[str, float]:
        """计算整体一致性率"""
        overall = {
            'total_operations': 0,
            'total_success': 0,
            'total_failed': 0,
            'overall_consistency_rate': 0.0
        }
        
        for service_name, service_stats in stats.items():
            if isinstance(service_stats, dict) and 'total' in service_stats:
                overall['total_operations'] += service_stats.get('total', 0)
                overall['total_success'] += service_stats.get('success', 0)
                overall['total_failed'] += service_stats.get('failed', 0)
        
        if overall['total_operations'] > 0:
            overall['overall_consistency_rate'] = (
                overall['total_success'] / overall['total_operations'] * 100
            )
        
        return overall
    
    def generate_report(self, stats: Dict[str, Any], overall: Dict[str, float]) -> str:
        """生成监控报告"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = []
        report.append("="*60)
        report.append(f"🔧 并行测试一致性监控报告 - {timestamp}")
        report.append("="*60)
        
        # 整体统计
        report.append(f"\n📊 整体统计:")
        report.append(f"  总操作次数: {overall['total_operations']}")
        report.append(f"  成功验证: {overall['total_success']}")
        report.append(f"  失败验证: {overall['total_failed']}")
        report.append(f"  整体一致性率: {overall['overall_consistency_rate']:.2f}%")
        
        # 目标检查
        target_rate = 95.0
        status_icon = "✅" if overall['overall_consistency_rate'] >= target_rate else "⚠️"
        report.append(f"  目标达成状态: {status_icon} (目标: {target_rate}%)")
        
        # 各Service详情
        report.append(f"\n📋 各Service详情:")
        for service_name, service_stats in stats.items():
            if isinstance(service_stats, dict) and 'total' in service_stats:
                total = service_stats.get('total', 0)
                success = service_stats.get('success', 0)
                failed = service_stats.get('failed', 0)
                rate = (success / total * 100) if total > 0 else 0
                
                service_icon = "✅" if rate >= target_rate else "⚠️" if rate >= 90 else "❌"
                report.append(f"  {service_icon} {service_name}:")
                report.append(f"      操作: {total}, 成功: {success}, 失败: {failed}")
                report.append(f"      一致性率: {rate:.2f}%")
            elif isinstance(service_stats, dict) and 'error' in service_stats:
                report.append(f"  ❌ {service_name}: 获取统计失败 - {service_stats['error']}")
            else:
                report.append(f"  ⭕ {service_name}: 未启用并行测试")
        
        # 建议
        report.append(f"\n💡 建议:")
        if overall['overall_consistency_rate'] >= 98:
            report.append("  🎉 一致性率优秀！可考虑切换到migrated模式")
        elif overall['overall_consistency_rate'] >= 95:
            report.append("  👍 一致性率良好，继续观察")
        elif overall['overall_consistency_rate'] >= 90:
            report.append("  ⚠️  一致性率需要关注，检查失败原因")
        else:
            report.append("  🚨 一致性率过低，需要立即排查问题")
        
        report.append("\n" + "="*60)
        
        return "\n".join(report)
    
    async def run_monitor_cycle(self):
        """执行一次监控周期"""
        try:
            # 获取统计数据
            stats = self.get_service_stats()
            overall = self.calculate_overall_consistency(stats)
            
            # 生成报告
            report = self.generate_report(stats, overall)
            
            # 输出报告
            self.logger.info("\n" + report)
            
            # 保存到文件
            report_file = f"/var/log/consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # 如果一致性率过低，发送告警
            if overall['overall_consistency_rate'] < 90 and overall['total_operations'] > 100:
                self.logger.error(f"🚨 一致性率过低告警: {overall['overall_consistency_rate']:.2f}%")
                # 这里可以添加发送邮件/钉钉等告警逻辑
            
            return stats, overall
            
        except Exception as e:
            self.logger.error(f"监控周期执行失败: {e}")
            raise

async def main():
    """主函数"""
    monitor = ConsistencyMonitor()
    
    try:
        await monitor.initialize()
        
        # 支持不同的运行模式
        mode = sys.argv[1] if len(sys.argv) > 1 else "once"
        
        if mode == "once":
            # 执行一次监控
            await monitor.run_monitor_cycle()
        elif mode == "daemon":
            # 守护进程模式，每10分钟监控一次
            while True:
                await monitor.run_monitor_cycle()
                await asyncio.sleep(600)  # 10分钟
        else:
            print("Usage: python monitor_consistency.py [once|daemon]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n监控程序被中断")
    except Exception as e:
        print(f"监控程序异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 