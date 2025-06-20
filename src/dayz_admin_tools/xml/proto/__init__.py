"""
DayZ Proto XML Tools

This package provides tools for working with DayZ proto XML files.
These files typically include mapgrouppos.xml and mapgroupproto.xml.
"""
from .compare_merge_lootmax_proto import LootmaxComparer
from .deathmatch_config_tool import DeathmatchConfigTool

__all__ = [
    'LootmaxComparer',
    'DeathmatchConfigTool',
]
