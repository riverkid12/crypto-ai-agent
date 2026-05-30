-- Default control values (spec section 6 seed list)
INSERT INTO control (key, value, updated_at) VALUES
  ('kill_switch', 'false', datetime('now')),
  ('max_per_trade_usdt', '500', datetime('now')),
  ('max_daily_loss_usdt', '300', datetime('now')),
  ('max_open_positions', '3', datetime('now')),
  ('max_position_per_symbol', '1', datetime('now')),
  ('api_fail_threshold', '3', datetime('now')),
  ('slippage_max_pct', '0.01', datetime('now')),
  ('signal_default_expiry_hours', '24', datetime('now')),
  ('cowork_decision_time_tw', '21:00', datetime('now')),
  ('bridge_run_time_tw', '21:05', datetime('now')),
  ('daily_report_time_tw', '23:55', datetime('now')),
  ('exec_tick_interval_minutes', '5', datetime('now')),
  ('notify_dedup_window_minutes', '10', datetime('now'));
