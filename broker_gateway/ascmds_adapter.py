# -*- coding: utf-8 -*-
"""
券商适配：在运行时向 evolving.ascmds 注入额外券商映射，不修改 evolving 子模块文件。
支持财通证券(CTZQ)等，evolving_repo 可与远程完全一致。
"""
import logging

logger = logging.getLogger(__name__)

# 额外券商：(broker_code, 同花顺中显示的券商名称)
EXTRA_BROKERS = [
    ("CTZQ", "财通证券"),
]


def _inject_extra_brokers_into_login():
    import evolving.ascmds as ascmds

    s = ascmds.asloginBroker
    # 在「中泰证券」的 end if 前插入额外券商分支（缩进与 ascmds 内一致，5 个 \t）
    old = (
        'else if broker_code is "ZTZQ" then\n'
        "\t\t\t\t\t\tset brokerName to \"中泰证券\"\n"
        "\t\t\t\t\tend if"
    )
    extra_parts = [
        f'else if broker_code is "{code}" then\n\t\t\t\t\t\tset brokerName to "{name}"'
        for code, name in EXTRA_BROKERS
    ]
    new = (
        'else if broker_code is "ZTZQ" then\n'
        '\t\t\t\t\t\tset brokerName to "中泰证券"\n'
        "\t\t\t\t\t"
        + "\n\t\t\t\t\t".join(extra_parts)
        + "\n\t\t\t\t\tend if"
    )
    if old not in s:
        logger.warning("ascmds_adapter: 未找到 ZTZQ 锚点，可能 evolving 版本不同，跳过券商注入")
        return
    ascmds.asloginBroker = s.replace(old, new, 1)
    logger.debug("ascmds_adapter: 已注入券商 %s", [b[0] for b in EXTRA_BROKERS])


def install_broker_adapter():
    """在首次创建 Evolving 前调用，向 ascmds 注入 EXTRA_BROKERS。"""
    try:
        _inject_extra_brokers_into_login()
    except Exception as e:
        logger.warning("ascmds_adapter: 注入失败 %s", e)
