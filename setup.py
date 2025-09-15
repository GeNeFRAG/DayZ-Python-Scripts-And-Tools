#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="dayz_admin_tools",
    version="1.0.0",
    description="Python tools for DayZ server config file administration and manipulation",
    author="GeNe FRAG",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.25.0",
        "numpy>=1.19.0",
        "pandas>=1.0.0",
        "openpyxl>=3.0.0",
        "matplotlib>=3.0.0",
        "Pillow>=8.0.0",
    ],
    extras_require={
        "xml": ["lxml>=4.6.0"],
    },
    entry_points={
        "console_scripts": [
            "dayz-download-logs=dayz_admin_tools.log.log_downloader:main",
            "dayz-position-finder=dayz_admin_tools.tools.position_finder:main",
            "dayz-search-overtime=dayz_admin_tools.tools.search_overtime_finder:main",
            "dayz-duping-detector=dayz_admin_tools.tools.duping_detector:main",
            "dayz-kill-tracker=dayz_admin_tools.tools.kill_tracker:main",
            "dayz-player-list-manager=dayz_admin_tools.tools.player_list_manager:main",
            "dayz-adm-analyzer=dayz_admin_tools.tools.adm_analyzer:main",
            "dayz-event-spawn-plotter=dayz_admin_tools.tools.event_spawn_plotter:main",
            # XML Types Tools
            "dayz-compare-types=dayz_admin_tools.xml.types.compare_types:main",
            "dayz-change-min-max=dayz_admin_tools.xml.types.change_min_max:main",
            "dayz-check-usage-tags=dayz_admin_tools.xml.types.check_usage_tags:main",
            "dayz-copy-types-values=dayz_admin_tools.xml.types.copy_types_values:main",
            "dayz-replace-usagevalue-tag-types=dayz_admin_tools.xml.types.replace_usagevalue_tag_types:main",
            "dayz-sort-types-usage=dayz_admin_tools.xml.types.sort_types_usage:main",
            "dayz-sum-staticbuilder-items=dayz_admin_tools.xml.types.sum_staticbuilder_items:main",
            "dayz-sum-staticmildrop-items=dayz_admin_tools.xml.types.sum_staticmildrop_items:main",
            "dayz-sync-csv-to-types=dayz_admin_tools.xml.types.sync_csv_to_types:main",
            "dayz-types-to-excel=dayz_admin_tools.xml.types.types_to_excel:main",
            # JSON Tools
            "dayz-calculate-3d-area=dayz_admin_tools.json.calculate_3d_area:main",
            "dayz-generate-spawner-entries=dayz_admin_tools.json.generate_spawner_entries:main",
            "dayz-sum-items-json=dayz_admin_tools.json.sum_items_json:main",
            "dayz-split-loot-structures=dayz_admin_tools.json.split_loot_structures:main",
            # Log Tools
            "dayz-log-filter-profiles=dayz_admin_tools.log.log_filter_profiles:main",
            # Proto XML Tools
            "dayz-compare-lootmax=dayz_admin_tools.xml.proto.compare_merge_lootmax_proto:main",
            "dayz-compare-missing-groups=dayz_admin_tools.xml.proto.compare_missing_groups:main",
            "dayz-deathmatch-config=dayz_admin_tools.xml.proto.deathmatch_config_tool:main",
        ],
    },
)
