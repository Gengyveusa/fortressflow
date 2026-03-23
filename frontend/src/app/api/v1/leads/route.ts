import { NextResponse } from "next/server";

const mockLeads = [
  { id: "lead-001", email: "sarah.chen@acmetech.io", phone: "+1-555-0101", first_name: "Sarah", last_name: "Chen", company: "AcmeTech", title: "VP of Sales", source: "HubSpot Import", meeting_verified: true, proof_data: null, created_at: "2026-03-15T10:30:00Z", updated_at: "2026-03-20T14:22:00Z" },
  { id: "lead-002", email: "marcus.rivera@techcorp.com", phone: "+1-555-0102", first_name: "Marcus", last_name: "Rivera", company: "TechCorp", title: "Director of Engineering", source: "LinkedIn", meeting_verified: false, proof_data: null, created_at: "2026-03-14T08:15:00Z", updated_at: "2026-03-19T11:45:00Z" },
  { id: "lead-003", email: "emily.watson@growthio.co", phone: null, first_name: "Emily", last_name: "Watson", company: "GrowthIO", title: "Head of Marketing", source: "CSV Import", meeting_verified: true, proof_data: null, created_at: "2026-03-12T16:00:00Z", updated_at: "2026-03-18T09:30:00Z" },
  { id: "lead-004", email: "james.park@novadata.ai", phone: "+1-555-0104", first_name: "James", last_name: "Park", company: "NovaData AI", title: "CTO", source: "Referral", meeting_verified: false, proof_data: null, created_at: "2026-03-10T12:00:00Z", updated_at: "2026-03-17T15:20:00Z" },
  { id: "lead-005", email: "lisa.johnson@scaleup.io", phone: "+1-555-0105", first_name: "Lisa", last_name: "Johnson", company: "ScaleUp", title: "CEO", source: "Cold Outreach", meeting_verified: true, proof_data: null, created_at: "2026-03-09T09:45:00Z", updated_at: "2026-03-16T10:10:00Z" },
  { id: "lead-006", email: "david.kim@cloudpeak.com", phone: "+1-555-0106", first_name: "David", last_name: "Kim", company: "CloudPeak", title: "VP Operations", source: "LinkedIn", meeting_verified: false, proof_data: null, created_at: "2026-03-08T14:30:00Z", updated_at: "2026-03-15T16:45:00Z" },
  { id: "lead-007", email: "anna.müller@eurosoft.de", phone: "+49-555-0107", first_name: "Anna", last_name: "Müller", company: "EuroSoft GmbH", title: "Sales Director", source: "Event", meeting_verified: true, proof_data: null, created_at: "2026-03-07T11:20:00Z", updated_at: "2026-03-14T08:55:00Z" },
  { id: "lead-008", email: "raj.patel@fintechpro.in", phone: "+91-555-0108", first_name: "Raj", last_name: "Patel", company: "FinTechPro", title: "Managing Director", source: "Webinar", meeting_verified: false, proof_data: null, created_at: "2026-03-06T07:10:00Z", updated_at: "2026-03-13T12:30:00Z" },
  { id: "lead-009", email: "jessica.lee@brighthub.com", phone: "+1-555-0109", first_name: "Jessica", last_name: "Lee", company: "BrightHub", title: "Head of Partnerships", source: "HubSpot Import", meeting_verified: true, proof_data: null, created_at: "2026-03-05T15:50:00Z", updated_at: "2026-03-12T17:15:00Z" },
  { id: "lead-010", email: "tom.nguyen@rapidgrowth.co", phone: "+1-555-0110", first_name: "Tom", last_name: "Nguyen", company: "RapidGrowth", title: "COO", source: "CSV Import", meeting_verified: false, proof_data: null, created_at: "2026-03-04T10:00:00Z", updated_at: "2026-03-11T13:40:00Z" },
];

export async function GET() {
  return NextResponse.json({
    items: mockLeads,
    total: 2847,
    page: 1,
    page_size: 20,
  });
}

export async function POST() {
  return NextResponse.json(mockLeads[0], { status: 201 });
}
