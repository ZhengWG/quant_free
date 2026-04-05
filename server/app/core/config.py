"""
应用配置
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用设置"""
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 3000
    DEBUG: bool = True
    
    # AI服务配置
    AI_PROVIDER: str = "deepseek"  # deepseek, openai, claude
    
    # DeepSeek配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # OpenAI配置
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    
    # Claude配置
    CLAUDE_API_KEY: Optional[str] = None
    
    # 行情数据API配置
    TUSHARE_TOKEN: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    
    # 交易模式：sim=模拟交易, live=实盘（需配置 BROKER_API_URL）
    TRADING_MODE: str = "sim"
    # 券商API配置（实盘时使用）
    BROKER_API_URL: Optional[str] = None
    BROKER_API_KEY: Optional[str] = None
    BROKER_API_SECRET: Optional[str] = None
    # 实盘时是否随后端自动启动券商网关（evolving，仅当 BROKER_API_URL 为本地 7070 时生效）
    AUTO_START_BROKER_GATEWAY: bool = False
    
    # 邮件通知配置（每日交易报告）
    EMAIL_ENABLED: bool = False
    EMAIL_SMTP_HOST: str = "smtp.qq.com"
    EMAIL_SMTP_PORT: int = 465              # QQ邮箱 SSL 端口
    EMAIL_SENDER: Optional[str] = None      # 发件邮箱（QQ号@qq.com）
    EMAIL_AUTH_CODE: Optional[str] = None   # SMTP授权码（非登录密码）
    EMAIL_RECEIVER: Optional[str] = None    # 收件邮箱（留空则与发件相同）
    EMAIL_SEND_HOUR: int = 16               # 每日发送时间（24时制，默认16:00）

    # 短信提醒配置（默认关闭）
    SMS_ENABLED: bool = False
    # 可选：webhook / twilio
    SMS_PROVIDER: str = "webhook"
    # webhook 方式：向指定 URL POST {"to","content","event","channel"}
    SMS_WEBHOOK_URL: Optional[str] = None
    SMS_WEBHOOK_TOKEN: Optional[str] = None
    # 通用接收号码（多个号码用英文逗号分隔）
    SMS_RECEIVERS: Optional[str] = None
    # Twilio 方式（可选）
    SMS_TWILIO_ACCOUNT_SID: Optional[str] = None
    SMS_TWILIO_AUTH_TOKEN: Optional[str] = None
    SMS_TWILIO_FROM: Optional[str] = None

    # 数据库配置
    DB_PATH: str = "./data/quant_free.db"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

