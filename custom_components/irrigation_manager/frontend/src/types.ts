export interface HassEntity {
  entity_id: string;
  state: string;
  last_changed?: string;
  attributes: Record<string, unknown> & {
    friendly_name?: string;
    unit_of_measurement?: string;
  };
}

export interface HomeAssistant {
  language: string;
  states: Record<string, HassEntity>;
  callService(domain: string, service: string, data?: Record<string, unknown>): Promise<unknown>;
  formatEntityState?(state: HassEntity): string;
}

export type DisplayMode = "compact" | "detailed";
export type ConfigurationMode = "simple" | "expert";

export interface OverviewCardConfig {
  type: string;
  name?: string;
  configuration_mode?: ConfigurationMode;
  installation?: string;
  status_entity?: string;
  emergency_entity?: string;
  lock_entity?: string;
  active_zone_entity?: string;
  dose_entity?: string;
  pending_entity?: string;
  next_entity?: string;
  today_consumption_entity?: string;
  month_consumption_entity?: string;
  model_quality_entity?: string;
  winter_entity?: string;
  maintenance_entity?: string;
  automation_release_entity?: string;
  maintenance_due_entity?: string;
  display_mode?: DisplayMode;
  visible_metrics?: string[];
  visible_actions?: string[];
}

export interface ZoneCardConfig {
  type: string;
  name?: string;
  configuration_mode?: ConfigurationMode;
  zone?: string;
  zone_entity?: string;
  automation_needed_entity?: string;
  safety_lock_entity?: string;
  installation_safety_lock_entity?: string;
  deficit_entity?: string;
  target_entity?: string;
  planning_reason_entity?: string;
  next_window_entity?: string;
  active_zone_entity?: string;
  request_entity?: string;
  last_delivered_entity?: string;
  last_duration_entity?: string;
  quality_entity?: string;
  status_entity?: string;
  automation_release_entity?: string;
  archived_entity?: string;
  coverage_entity?: string;
  expected_flow_entity?: string;
  actual_flow_entity?: string;
  flow_deviation_entity?: string;
  calculation_entity?: string;
  display_mode?: DisplayMode;
  visible_metrics?: string[];
  visible_actions?: string[];
}

declare global {
  interface Window {
    customCards?: Array<{
      type: string;
      name: string;
      description: string;
      preview?: boolean;
    }>;
  }
}
