"""
Gengyve USA outreach sequence presets.

Three pre-built sequences targeting dental offices and DSOs:
1. Cold Outreach — Multi-channel introduction to decision-makers
2. Post-Meeting Follow-up — After trade shows, conferences, or sales meetings
3. Re-engagement — Nurture cold leads back to warm

All templates use {{variable}} interpolation.
"""



# ─────────────────────────────────────────────────────────────
# SEQUENCE 1: COLD OUTREACH
# Target: Dental office managers, practice owners, DSO procurement
# Cadence: 14 days, 6 touches across email + LinkedIn + SMS
# ─────────────────────────────────────────────────────────────

COLD_OUTREACH_SEQUENCE = {
    "name": "Gengyve — Cold Outreach (Dental Offices & DSOs)",
    "description": (
        "6-step multi-channel sequence for introducing Gengyve to dental practices. "
        "Leads with education-first value, follows up across email, LinkedIn, and SMS."
    ),
    "category": "cold_outreach",
    "steps": [
        # Step 1: Email — Educational hook
        {
            "step_type": "email",
            "position": 0,
            "delay_hours": 0,
            "template": {
                "name": "Cold — Email 1: The Oral-Systemic Connection",
                "channel": "email",
                "category": "cold_outreach",
                "subject": "{{first_name}}, quick question about your patients' mouthwash",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>I wanted to reach out because most dental offices we talk to are still recommending chlorhexidine or alcohol-based rinses — despite the growing body of evidence linking them to microbiome disruption and patient non-compliance.</p>

<p>We developed <strong>Gengyve</strong> specifically for practices like {{company}}: a 4-ingredient, all-natural mouthwash formulated by practicing oral surgeons that:</p>

<ul style="padding-left: 20px;">
<li>Reduces gingival inflammation <strong>without</strong> staining or taste alteration</li>
<li>Is safe for unlimited daily use (no 2-week restrictions)</li>
<li>Supports post-surgical healing and periodontal maintenance</li>
<li>Is HSA/FSA eligible for your patients</li>
</ul>

<p>Over 1,000 dental professionals already recommend it. Would it make sense for me to send you a complimentary sample kit for your team to evaluate?</p>

<p>Best,<br/>
{{sender_name}}<br/>
<span style="color: #6b7280;">{{sender_title}}, {{sender_company}}</span></p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "I wanted to reach out because most dental offices we talk to are still recommending "
                    "chlorhexidine or alcohol-based rinses — despite the growing evidence linking them to "
                    "microbiome disruption and patient non-compliance.\n\n"
                    "We developed Gengyve specifically for practices like {{company}}: a 4-ingredient, "
                    "all-natural mouthwash formulated by practicing oral surgeons that:\n\n"
                    "- Reduces gingival inflammation without staining or taste alteration\n"
                    "- Is safe for unlimited daily use (no 2-week restrictions)\n"
                    "- Supports post-surgical healing and periodontal maintenance\n"
                    "- Is HSA/FSA eligible for your patients\n\n"
                    "Over 1,000 dental professionals already recommend it. Would it make sense for me to "
                    "send you a complimentary sample kit for your team to evaluate?\n\n"
                    "Best,\n{{sender_name}}\n{{sender_title}}, {{sender_company}}"
                ),
                "variables": ["first_name", "company", "sender_name", "sender_title", "sender_company"],
            },
        },
        # Step 2: Wait 2 days
        {
            "step_type": "wait",
            "position": 1,
            "delay_hours": 48,
            "template": None,
        },
        # Step 3: LinkedIn connection request
        {
            "step_type": "linkedin",
            "position": 2,
            "delay_hours": 0,
            "template": {
                "name": "Cold — LinkedIn: Personalized Connection Request",
                "channel": "linkedin",
                "category": "cold_outreach",
                "linkedin_action": "connection_request",
                "plain_body": (
                    "Hi {{first_name}} — I'm the founder of Gengyve, a natural mouthwash developed by "
                    "oral surgeons. I noticed {{company}} is focused on quality patient care. "
                    "Would love to connect and share how 1,000+ practices are replacing CHX rinses. "
                    "No pitch, just a conversation."
                ),
                "variables": ["first_name", "company"],
            },
        },
        # Step 4: Wait 3 days
        {
            "step_type": "wait",
            "position": 3,
            "delay_hours": 72,
            "template": None,
        },
        # Step 5: Email — Value-add follow-up
        {
            "step_type": "email",
            "position": 4,
            "delay_hours": 0,
            "template": {
                "name": "Cold — Email 2: Clinical Evidence + Free Sample",
                "channel": "email",
                "category": "cold_outreach",
                "subject": "The data on natural vs. CHX rinses (for {{company}})",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>Following up on my earlier note. I wanted to share something your clinical team might find valuable:</p>

<p>Recent research shows that chlorhexidine-based rinses, while effective short-term, can disrupt the oral microbiome within 7 days of use — shifting bacterial populations in ways that may actually increase caries risk long-term.</p>

<p>Gengyve takes a different approach: using hyaluronic acid and just 3 other natural ingredients to reduce inflammation and support tissue healing without the collateral damage. Some key outcomes practices are seeing:</p>

<ul style="padding-left: 20px;">
<li><strong>Patient compliance up 3x</strong> (no staining, no taste issues, no time limits)</li>
<li><strong>Post-op healing improvement</strong> in extraction and implant cases</li>
<li><strong>Wholesale pricing</strong> available for in-office dispensing</li>
</ul>

<p>I'd love to send a sample kit to {{company}} — completely free, no strings. Would that be helpful?</p>

<p>— {{sender_name}}</p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "Following up on my earlier note. I wanted to share something your clinical team "
                    "might find valuable:\n\n"
                    "Recent research shows that chlorhexidine-based rinses, while effective short-term, "
                    "can disrupt the oral microbiome within 7 days of use — shifting bacterial populations "
                    "in ways that may increase caries risk long-term.\n\n"
                    "Gengyve takes a different approach: using hyaluronic acid and just 3 other natural "
                    "ingredients to reduce inflammation and support tissue healing without the collateral "
                    "damage. Some key outcomes practices are seeing:\n\n"
                    "- Patient compliance up 3x (no staining, no taste issues, no time limits)\n"
                    "- Post-op healing improvement in extraction and implant cases\n"
                    "- Wholesale pricing available for in-office dispensing\n\n"
                    "I'd love to send a sample kit to {{company}} — completely free, no strings. "
                    "Would that be helpful?\n\n"
                    "— {{sender_name}}"
                ),
                "variables": ["first_name", "company", "sender_name"],
            },
        },
        # Step 6: Wait 4 days, then SMS
        {
            "step_type": "wait",
            "position": 5,
            "delay_hours": 96,
            "template": None,
        },
        # Step 7: SMS — Brief + direct
        {
            "step_type": "sms",
            "position": 6,
            "delay_hours": 0,
            "template": {
                "name": "Cold — SMS: Quick Check-in",
                "channel": "sms",
                "category": "cold_outreach",
                "plain_body": (
                    "Hi {{first_name}}, this is {{sender_name}} from Gengyve. "
                    "I sent over some info about our natural mouthwash for dental practices. "
                    "Happy to send a free sample kit to {{company}} if interested. "
                    "Reply STOP to opt out."
                ),
                "variables": ["first_name", "sender_name", "company"],
            },
        },
        # Step 8: Wait 3 days, final email
        {
            "step_type": "wait",
            "position": 7,
            "delay_hours": 72,
            "template": None,
        },
        # Step 9: Email — Breakup email
        {
            "step_type": "email",
            "position": 8,
            "delay_hours": 0,
            "template": {
                "name": "Cold — Email 3: The Breakup (Permission to Close)",
                "channel": "email",
                "category": "cold_outreach",
                "subject": "Should I close your file, {{first_name}}?",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>I've reached out a couple of times about Gengyve for {{company}} and haven't heard back — which is totally fine. Everyone's inbox is a warzone.</p>

<p>I don't want to be that person who keeps following up, so I'll leave it here. If the timing ever makes sense to explore a natural, surgeon-developed mouthwash for your practice, I'm an email away.</p>

<p>In the meantime, here's a link to our clinical resources page if your team ever wants to dig in: <a href="https://www.gengyveusa.com">gengyveusa.com</a></p>

<p>Wishing {{company}} continued success.</p>

<p>— {{sender_name}}</p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "I've reached out a couple of times about Gengyve for {{company}} and haven't "
                    "heard back — which is totally fine. Everyone's inbox is a warzone.\n\n"
                    "I don't want to be that person who keeps following up, so I'll leave it here. "
                    "If the timing ever makes sense to explore a natural, surgeon-developed mouthwash "
                    "for your practice, I'm an email away.\n\n"
                    "In the meantime, here's a link to our clinical resources page if your team ever "
                    "wants to dig in: gengyveusa.com\n\n"
                    "Wishing {{company}} continued success.\n\n"
                    "— {{sender_name}}"
                ),
                "variables": ["first_name", "company", "sender_name"],
            },
        },
    ],
}


# ─────────────────────────────────────────────────────────────
# SEQUENCE 2: POST-MEETING FOLLOW-UP
# Target: Contacts met at trade shows, conferences, or sales calls
# Cadence: 10 days, 5 touches
# ─────────────────────────────────────────────────────────────

POST_MEETING_SEQUENCE = {
    "name": "Gengyve — Post-Meeting Follow-up",
    "description": (
        "5-step sequence for leads met at dental conferences, trade shows, "
        "or discovery calls. Capitalizes on warm relationship with fast follow-up."
    ),
    "category": "follow_up",
    "steps": [
        # Step 1: Email within 24h — Warm thank-you + next step
        {
            "step_type": "email",
            "position": 0,
            "delay_hours": 0,
            "template": {
                "name": "Follow-up — Email 1: Great Meeting You",
                "channel": "email",
                "category": "follow_up",
                "subject": "Great connecting, {{first_name}} — your Gengyve sample kit",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>It was a pleasure meeting you and learning more about what {{company}} is building. I really enjoyed our conversation about patient care and the role oral health plays in overall wellness.</p>

<p>As promised, I'm sending over a <strong>complimentary Gengyve sample kit</strong> for your team to try. You should receive it within 3-5 business days.</p>

<p>Quick recap on what makes Gengyve different:</p>

<ul style="padding-left: 20px;">
<li><strong>4 natural ingredients</strong> — no alcohol, no fluoride, no chlorhexidine</li>
<li><strong>Formulated by oral surgeons</strong> for post-op and daily maintenance</li>
<li><strong>No usage time limits</strong> — patients can use it every day, indefinitely</li>
<li><strong>Wholesale program</strong> available for in-office dispensing and patient retail</li>
</ul>

<p>Would next week work for a quick 15-minute call to walk through the wholesale program and see if it's a fit for {{company}}?</p>

<p>Looking forward to staying in touch.</p>

<p>— {{sender_name}}<br/>
<span style="color: #6b7280;">{{sender_title}}, {{sender_company}}</span></p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "It was a pleasure meeting you and learning more about what {{company}} is building. "
                    "I really enjoyed our conversation about patient care and the role oral health plays "
                    "in overall wellness.\n\n"
                    "As promised, I'm sending over a complimentary Gengyve sample kit for your team to try. "
                    "You should receive it within 3-5 business days.\n\n"
                    "Quick recap on what makes Gengyve different:\n"
                    "- 4 natural ingredients — no alcohol, no fluoride, no chlorhexidine\n"
                    "- Formulated by oral surgeons for post-op and daily maintenance\n"
                    "- No usage time limits — patients can use it every day, indefinitely\n"
                    "- Wholesale program available for in-office dispensing and patient retail\n\n"
                    "Would next week work for a quick 15-minute call to walk through the wholesale program "
                    "and see if it's a fit for {{company}}?\n\n"
                    "Looking forward to staying in touch.\n\n"
                    "— {{sender_name}}\n{{sender_title}}, {{sender_company}}"
                ),
                "variables": ["first_name", "company", "sender_name", "sender_title", "sender_company"],
            },
        },
        # Step 2: LinkedIn connection
        {
            "step_type": "linkedin",
            "position": 1,
            "delay_hours": 24,
            "template": {
                "name": "Follow-up — LinkedIn: Post-Meeting Connect",
                "channel": "linkedin",
                "category": "follow_up",
                "linkedin_action": "connection_request",
                "plain_body": (
                    "{{first_name}} — great meeting you! Enjoyed our conversation about {{company}}'s "
                    "approach to patient care. Sending your Gengyve samples over now. Let's stay connected."
                ),
                "variables": ["first_name", "company"],
            },
        },
        # Step 3: Wait 3 days
        {
            "step_type": "wait",
            "position": 2,
            "delay_hours": 72,
            "template": None,
        },
        # Step 4: Email — Check on samples + scheduling
        {
            "step_type": "email",
            "position": 3,
            "delay_hours": 0,
            "template": {
                "name": "Follow-up — Email 2: Sample Check-in",
                "channel": "email",
                "category": "follow_up",
                "subject": "Did the Gengyve samples arrive, {{first_name}}?",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>Just checking in — your Gengyve sample kit should have arrived by now. I hope your team has had a chance to try it out.</p>

<p>A few things practices typically notice right away:</p>

<ol style="padding-left: 20px;">
<li>The taste is clean and mild — patients actually <em>want</em> to use it daily</li>
<li>No staining, so hygienists aren't spending extra time on cleanup</li>
<li>Post-op patients report less sensitivity and faster comfort</li>
</ol>

<p>If you'd like to chat about wholesale pricing or how other practices are incorporating Gengyve into their workflow, I'm happy to set up a quick call anytime this week.</p>

<p>— {{sender_name}}</p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "Just checking in — your Gengyve sample kit should have arrived by now. "
                    "I hope your team has had a chance to try it out.\n\n"
                    "A few things practices typically notice right away:\n"
                    "1. The taste is clean and mild — patients actually want to use it daily\n"
                    "2. No staining, so hygienists aren't spending extra time on cleanup\n"
                    "3. Post-op patients report less sensitivity and faster comfort\n\n"
                    "If you'd like to chat about wholesale pricing or how other practices are "
                    "incorporating Gengyve into their workflow, I'm happy to set up a quick call "
                    "anytime this week.\n\n"
                    "— {{sender_name}}"
                ),
                "variables": ["first_name", "sender_name"],
            },
        },
        # Step 5: Wait 4 days, then SMS
        {
            "step_type": "wait",
            "position": 4,
            "delay_hours": 96,
            "template": None,
        },
        # Step 6: SMS — Casual + direct
        {
            "step_type": "sms",
            "position": 5,
            "delay_hours": 0,
            "template": {
                "name": "Follow-up — SMS: Quick Check-in",
                "channel": "sms",
                "category": "follow_up",
                "plain_body": (
                    "Hey {{first_name}}! {{sender_name}} from Gengyve here. "
                    "Hope you got the samples — any feedback from the team? "
                    "Happy to jump on a quick call about wholesale pricing whenever works. "
                    "Reply STOP to opt out."
                ),
                "variables": ["first_name", "sender_name"],
            },
        },
    ],
}


# ─────────────────────────────────────────────────────────────
# SEQUENCE 3: RE-ENGAGEMENT / NURTURE
# Target: Leads who went cold after initial outreach
# Cadence: 21 days, 5 touches, education-heavy
# ─────────────────────────────────────────────────────────────

RE_ENGAGEMENT_SEQUENCE = {
    "name": "Gengyve — Re-engagement Nurture (Dental Offices)",
    "description": (
        "5-step education-first sequence to re-warm leads who didn't convert "
        "on initial outreach. Shares clinical insights and positions Gengyve "
        "as a thought leader in oral-systemic health."
    ),
    "category": "re_engagement",
    "steps": [
        # Step 1: Email — New research angle
        {
            "step_type": "email",
            "position": 0,
            "delay_hours": 0,
            "template": {
                "name": "Re-engage — Email 1: New Research on Oral-Systemic Link",
                "channel": "email",
                "category": "re_engagement",
                "subject": "{{first_name}}, new research your team should see",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>I know it's been a while since we last connected. I wanted to share something I think your clinical team at {{company}} would find genuinely interesting — no sales pitch.</p>

<p>A recent study published in <em>Frontiers in Cellular and Infection Microbiology</em> found that <strong>oral bacteria — particularly F. nucleatum and P. gingivalis — have direct pathways to systemic inflammation</strong>, contributing to cardiovascular disease, adverse pregnancy outcomes, and even certain cancers.</p>

<p>The implication for dental practices? The mouthwash you recommend matters more than ever. Products that indiscriminately kill oral bacteria (like alcohol-based rinses) may be doing more harm than good by disrupting the protective microbiome.</p>

<p>We've put together a quick clinical summary our partner practices have found useful. Want me to send it over?</p>

<p>— {{sender_name}}<br/>
<span style="color: #6b7280;">{{sender_title}}, {{sender_company}}</span></p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "I know it's been a while since we last connected. I wanted to share something "
                    "I think your clinical team at {{company}} would find genuinely interesting — "
                    "no sales pitch.\n\n"
                    "A recent study in Frontiers in Cellular and Infection Microbiology found that "
                    "oral bacteria — particularly F. nucleatum and P. gingivalis — have direct pathways "
                    "to systemic inflammation, contributing to cardiovascular disease, adverse pregnancy "
                    "outcomes, and even certain cancers.\n\n"
                    "The implication for dental practices? The mouthwash you recommend matters more "
                    "than ever. Products that indiscriminately kill oral bacteria may be doing more harm "
                    "than good by disrupting the protective microbiome.\n\n"
                    "We've put together a quick clinical summary our partner practices have found useful. "
                    "Want me to send it over?\n\n"
                    "— {{sender_name}}\n{{sender_title}}, {{sender_company}}"
                ),
                "variables": ["first_name", "company", "sender_name", "sender_title", "sender_company"],
            },
        },
        # Step 2: Wait 5 days
        {
            "step_type": "wait",
            "position": 1,
            "delay_hours": 120,
            "template": None,
        },
        # Step 3: Email — Case study / social proof
        {
            "step_type": "email",
            "position": 2,
            "delay_hours": 0,
            "template": {
                "name": "Re-engage — Email 2: How Practices Are Using Gengyve",
                "channel": "email",
                "category": "re_engagement",
                "subject": "How a 3-location DSO cut their CHX spend by 100%",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>Quick story I thought you'd appreciate:</p>

<p>A 3-location dental group in the Bay Area was spending over $2,400/year on chlorhexidine rinses and dealing with constant patient complaints about staining and taste. They switched to Gengyve for all post-op and perio maintenance patients 6 months ago.</p>

<p>The results:</p>
<ul style="padding-left: 20px;">
<li><strong>$0 CHX spend</strong> — replaced entirely with Gengyve wholesale</li>
<li><strong>Patient compliance jumped 3x</strong> — patients actually finish the bottle</li>
<li><strong>New revenue stream</strong> — selling Gengyve in their patient retail area</li>
<li><strong>Zero complaints</strong> about staining or taste</li>
</ul>

<p>If {{company}} is open to exploring something similar, I'd be happy to walk through how the wholesale program works. It's genuinely straightforward.</p>

<p>— {{sender_name}}</p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "Quick story I thought you'd appreciate:\n\n"
                    "A 3-location dental group in the Bay Area was spending over $2,400/year on "
                    "chlorhexidine rinses and dealing with constant patient complaints about staining "
                    "and taste. They switched to Gengyve for all post-op and perio maintenance patients "
                    "6 months ago.\n\n"
                    "The results:\n"
                    "- $0 CHX spend — replaced entirely with Gengyve wholesale\n"
                    "- Patient compliance jumped 3x — patients actually finish the bottle\n"
                    "- New revenue stream — selling Gengyve in their patient retail area\n"
                    "- Zero complaints about staining or taste\n\n"
                    "If {{company}} is open to exploring something similar, I'd be happy to walk through "
                    "how the wholesale program works. It's genuinely straightforward.\n\n"
                    "— {{sender_name}}"
                ),
                "variables": ["first_name", "company", "sender_name"],
            },
        },
        # Step 4: Wait 7 days
        {
            "step_type": "wait",
            "position": 3,
            "delay_hours": 168,
            "template": None,
        },
        # Step 5: LinkedIn message (if connected) or InMail
        {
            "step_type": "linkedin",
            "position": 4,
            "delay_hours": 0,
            "template": {
                "name": "Re-engage — LinkedIn: Value-Add Share",
                "channel": "linkedin",
                "category": "re_engagement",
                "linkedin_action": "message",
                "plain_body": (
                    "Hi {{first_name}} — hope things are going well at {{company}}! "
                    "I recently published an article on how oral bacteria drive systemic disease "
                    "that I thought your team might find useful. Happy to share it if you're interested. "
                    "Also, our wholesale program has some new pricing tiers that could work well for your practice."
                ),
                "variables": ["first_name", "company"],
            },
        },
        # Step 6: Wait 5 days
        {
            "step_type": "wait",
            "position": 5,
            "delay_hours": 120,
            "template": None,
        },
        # Step 7: Email — Gentle final touch
        {
            "step_type": "email",
            "position": 6,
            "delay_hours": 0,
            "template": {
                "name": "Re-engage — Email 3: Open Door",
                "channel": "email",
                "category": "re_engagement",
                "subject": "No pressure, {{first_name}} — just keeping the door open",
                "html_body": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
<p>Hi {{first_name}},</p>

<p>I know timing is everything in practice management, and switching anything in a busy dental office takes real bandwidth. No pressure at all.</p>

<p>I just wanted to leave you with two things in case the timing ever makes sense:</p>

<ol style="padding-left: 20px;">
<li><strong>Free sample kit</strong> — always available, just reply to this email</li>
<li><strong>Our clinical resources</strong> — peer-reviewed research on why natural mouthwash outperforms CHX for daily maintenance: <a href="https://www.gengyveusa.com">gengyveusa.com</a></li>
</ol>

<p>{{company}} is clearly doing great work for patients. If there's ever a way Gengyve can support that mission, I'm here.</p>

<p>All the best,<br/>
{{sender_name}}<br/>
<span style="color: #6b7280;">{{sender_title}}, {{sender_company}}</span></p>
</div>""",
                "plain_body": (
                    "Hi {{first_name}},\n\n"
                    "I know timing is everything in practice management, and switching anything in a "
                    "busy dental office takes real bandwidth. No pressure at all.\n\n"
                    "I just wanted to leave you with two things in case the timing ever makes sense:\n\n"
                    "1. Free sample kit — always available, just reply to this email\n"
                    "2. Our clinical resources — peer-reviewed research on why natural mouthwash "
                    "outperforms CHX for daily maintenance: gengyveusa.com\n\n"
                    "{{company}} is clearly doing great work for patients. If there's ever a way "
                    "Gengyve can support that mission, I'm here.\n\n"
                    "All the best,\n{{sender_name}}\n{{sender_title}}, {{sender_company}}"
                ),
                "variables": ["first_name", "company", "sender_name", "sender_title", "sender_company"],
            },
        },
    ],
}


# All presets
SEQUENCE_PRESETS = [
    COLD_OUTREACH_SEQUENCE,
    POST_MEETING_SEQUENCE,
    RE_ENGAGEMENT_SEQUENCE,
]
