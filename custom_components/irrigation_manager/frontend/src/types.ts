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
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: Record<string, unknown>,
    returnResponse?: boolean,
  ): Promise<unknown>;
  formatEntityState?(state: HassEntity): string;
}

export interface OverviewCardConfig {
  type?: string;
  entity?: string;
}

export interface ResolvedOverviewCardConfig extends OverviewCardConfig {
  status_entity?: string;
  pending_entity?: string;
  next_entity?: string;
  next_start_entity?: string;
  today_consumption_entity?: string;
  month_consumption_entity?: string;
  runtime_today_entity?: string;
  runtime_month_entity?: string;
  physical_meter_entity?: string;
}

export interface ZoneCardConfig {
  type?: string;
  entity?: string;
}

export interface ResolvedZoneCardConfig extends ZoneCardConfig {
  zone_entity?: string;
  status_entity?: string;
  water_today_entity?: string;
  water_month_entity?: string;
  runtime_today_entity?: string;
  runtime_month_entity?: string;
  next_irrigation_entity?: string;
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
