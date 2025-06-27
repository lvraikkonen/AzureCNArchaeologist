def _should_filter_table(self, table_id: str) -> bool:
    """
    判断表格是否应该被过滤
    
    Returns:
        bool: True=过滤（隐藏），False=保留显示
    """
    try:
        # 基础验证
        if not table_id or not isinstance(table_id, str) or not self.active_region:
            return False

        # 规则1: 区域不在配置中 → 不过滤
        excluded_tables = self.region_filter_config.get(self.active_region)
        if excluded_tables is None:
            return False

        # 规则2: 排除列表为空 → 不过滤
        if not excluded_tables:
            return False

        # 规则3: 检查是否在排除列表中
        table_id_clean = table_id.strip()
        table_id_with_hash = f"#{table_id_clean}" if not table_id_clean.startswith('#') else table_id_clean
        table_id_without_hash = table_id_clean[1:] if table_id_clean.startswith('#') and len(table_id_clean) > 1 else table_id_clean

        return (table_id_clean in excluded_tables or
                table_id_with_hash in excluded_tables or
                table_id_without_hash in excluded_tables)
                
    except Exception:
        # 异常时保守处理：不过滤（显示表格）
        return False