module.exports = {
  apps: [
    {
      name: 'tg-bot-picture',
      script: 'main.py',                                 // 直接运行入口文件
      interpreter: '/home/tg_bot_picture_v1/venv/bin/python3', // 固定到同一 venv
      cwd: '/home/tg_bot_picture_v1',                    // 项目根目录（.env 在这）
      instances: 1,                                      // 单实例，避免端口冲突
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PYTHONUNBUFFERED: '1'                            // 立刻刷日志
        // 如需强制覆盖端口，也可在此放 PAYMENT_PORT/IMAGE_PORT
      },
      out_file: '/home/tg_bot_picture_v1/logs/pm2-out.log',
      error_file: '/home/tg_bot_picture_v1/logs/pm2-error.log',
      merge_logs: true,
      time: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      restart_delay: 4000,
      kill_timeout: 3000
      // ⚠️ 不要用 wait_ready / listen_timeout（那是 Node 专用的 ready 信号）
    }
  ]
}
