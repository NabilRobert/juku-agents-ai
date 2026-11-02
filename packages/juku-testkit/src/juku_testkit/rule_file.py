"""A small, valid guardrails.yaml for the tests of what reads it.

Everything but the `fitness` section, which each test file adds itself,
because that section is what those tests are about.
"""

RULES_WITHOUT_FITNESS = """
version: 1
alerts:
  heartbeat_stale_seconds: 300
  tool_error_rate_per_hour: 0.05
privacy:
  min_learners_per_cell: 5
delegation:
  issuer: juku-app
  audience: juku-mcp
  token_ttl_seconds: 60
  max_agent_hops: 2
  require_gateway_caller: true
  allowed_delegations:
    - {from_agent: shiori, to_agent: keiko, via_tool: request_replan}
agents:
  shiori: [get_progress, request_replan]
  keiko: [get_progress]
replan:
  max_requests_per_day: 1
budget:
  input_usd_per_million: 0.25
  output_usd_per_million: 2.00
  reports_pool_usd: 0.90
  chat_pool_usd: 1.20
  chat_daily_global_usd: 0.20
  chat_daily_questions_per_learner: 20
  chat_run_request_limit: 6
  chat_run_total_tokens_limit: 20000
  report_run_request_limit: 8
  report_run_total_tokens_limit: 40000
  alert_fractions: [0.5, 0.8, 1.0]
memory:
  allowed_categories: [recurring_confusion, pace]
  forbidden_categories: [health]
  forbidden_text_markers: [sakit]
  min_evidence_events: 3
  evidence_max_age_days: 30
  contradicting_answers: 2
  suppress_after_removal_days: 30
  max_active_notes: 12
  max_text_chars: 160
pipeline:
  max_revisions: 2
  report_max_words: 300
  due_weekday: 6
  due_hour: 18
  run_lease_minutes: 30
  overdue_after_minutes: 60
  feedback_min_occurrences: 3

database:
  connection_limit: 20
  reserved_for_admin: 2
  app_pool: 3
  app_dict_pool: 2
  app_commands: 1
  mcp_pool: 3
  mcp_dict_pool: 2
  ops_connections: 2
  migrator_connections: 1
  dict_owner_connections: 1
  grafana_connections: 2
  mcp_backbone_connections: 1
"""
