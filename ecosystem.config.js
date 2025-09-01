module.exports = {
  apps: [
    {
      name: 'tg-bot-picture',
      script: 'python3',
      args: 'main.py',
      cwd: '/home/tg_bot_picture_v1',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_file: './logs/pm2-combined.log',
      time: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      // 重启策略
      restart_delay: 4000,
      min_uptime: '10s',
      max_restarts: 10,
      // 停止配置
      kill_timeout: 3000,
      wait_ready: true,
      listen_timeout: 3000,
      // 进程健康检查
      health_check_grace_period: 3000
    }
  ]
} 