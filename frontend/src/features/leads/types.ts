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
  owner_id: number | null;
  source: string;
  archived_at: string | null;
  received_at: string;
};
export type LeadDetail = Lead & {
  location: string;
  requirements: string;
  created_at: string;
  updated_at: string;
  version: number;
  first_contact_at: string | null;
  quote_amount: string | null;
  loss_reason: string;
  closed_at: string | null;
  activity: {
    id: string;
    event_type: string;
    occurred_at: string;
    actor_name: string | null;
    summary: string;
  }[];
  tasks: FollowUpTask[];
};
export type FollowUpTask = {
  id: string;
  lead_id: string;
  lead_name: string;
  lead_stage: string;
  lead_version: number;
  owner_name: string | null;
  title: string;
  details: string;
  due_at: string;
  status: 'pending' | 'completed' | 'cancelled';
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  is_overdue: boolean;
};
export type LeadPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Lead[];
};
