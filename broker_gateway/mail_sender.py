# -*- coding: utf-8 -*-
"""
网关侧邮件适配：不修改 evolving 子模块，在此实现 QQ/163/Gmail 等 465/SSL 发信。
evolving 内 mailMe() 会调用 helper.Mail(msg)，通过 install_mail_adapter() 替换为 GatewayMail。
"""

import logging
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class GatewayMail:
    """与 evolving.helper.Mail 同接口，发信时对 QQ/163/Gmail 使用 SMTP_SSL(465)。"""

    def __init__(self, msg):
        try:
            import evolving.helper as ev_helper
        except ImportError:
            logger.warning("mail_sender: evolving 未安装，跳过发信")
            return
        if not hasattr(msg, "subject") or not hasattr(msg, "body"):
            return
        mconfig = ev_helper.MConfig()
        host = mconfig.mail_host
        sender = mconfig.mail_sender
        license_ = mconfig.mail_license
        receivers = mconfig.mail_receivers
        if not host or not sender or not license_ or not receivers:
            logger.debug("mail_sender: mail 配置不完整，跳过发信")
            return
        try:
            if host and ("qq.com" in host or "163.com" in host or "gmail.com" in host):
                stp = smtplib.SMTP_SSL(host, 465)
            else:
                stp = smtplib.SMTP()
                stp.connect(host, 25)
            stp.ehlo()
            stp.login(sender, license_)
            mail = MIMEMultipart()
            mail["From"] = "zero<" + sender + ">"
            mail["To"] = "".join([y.split("@")[0] + "<" + y + ">;" for y in receivers])
            mail["Subject"] = Header(msg.subject, "utf-8")
            mail.attach(MIMEText(msg.body, "plain", "utf-8"))
            stp.sendmail(sender, receivers, mail.as_string())
            stp.quit()
        except Exception as e:
            logger.warning("mail_sender: 发信失败 %s", e)


def install_mail_adapter():
    """在首次创建 Evolving 前调用，将 evolving.helper.Mail 替换为 GatewayMail。"""
    try:
        import evolving.helper as ev_helper
        ev_helper.Mail = GatewayMail
    except ImportError:
        pass
