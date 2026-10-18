export type Lead = {
  id: string;
  name: string;
  phone: string;
  email: string;
  service_type: string;
  service_label: string;
  stage: string;
  stage_label: string;
  owner_name: string | null;
  source: string;
  received_at: string;
};
export type LeadDetail = Lead & {
  location: string;
  requirements: string;
  created_at: string;
  updated_at: string;
  version: number;
  activity: { id: string; event_type: string; occurred_at: string }[];
};
export type LeadPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Lead[];
};
